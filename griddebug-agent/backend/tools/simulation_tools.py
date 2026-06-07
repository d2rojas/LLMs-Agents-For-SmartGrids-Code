"""
Simulation tools for the agentic pipeline: run power flow, DC PF, N-1 contingency,
short-circuit analysis, OPF, and network snapshots.
"""
from __future__ import annotations

import copy
import math

import pandas as pd
import pandapower as pp
from tools.diagnostic_tools import DiagnosticTools


# Module-level snapshot storage (keyed by label)
_network_snapshots: dict[str, pp.pandapowerNet] = {}


TOOL_DEFINITIONS = [
    {
        "name": "run_power_flow",
        "description": "Run AC power flow. Returns convergence status and a short summary. Supports algorithm selection: 'nr' (Newton-Raphson, default), 'fdBX' (fast-decoupled), 'gs' (Gauss-Seidel).",
        "parameters": {
            "algorithm": {"type": "string", "description": "Solver algorithm: 'nr' (Newton-Raphson, default), 'fdBX' (fast-decoupled), 'gs' (Gauss-Seidel)."},
        },
    },
    {
        "name": "run_dc_power_flow",
        "description": "Run DC power flow (linear approximation). Often converges when AC fails.",
        "parameters": {},
    },
    {
        "name": "run_n1_contingency",
        "description": "Run N-1 contingency: outage one line or trafo and run power flow. Pass line_index or trafo_index.",
        "parameters": {
            "line_index": {"type": "integer", "description": "Line index to take out of service for N-1."},
            "trafo_index": {"type": "integer", "description": "Transformer index to take out of service for N-1."},
        },
    },
    {
        "name": "run_short_circuit",
        "description": "Run short-circuit analysis at a specific bus. Returns Ikss (steady-state SC current in kA), Skss (SC apparent power in MVA), and other SC quantities. Fault type can be '3ph' (three-phase) or '2ph' (two-phase).",
        "parameters": {
            "bus_index": {"type": "integer", "description": "Bus index where the fault occurs."},
            "fault_type": {"type": "string", "description": "Fault type: '3ph' (three-phase, default) or '2ph' (two-phase)."},
        },
    },
    {
        "name": "run_opf",
        "description": "Run AC Optimal Power Flow (OPF). Returns convergence status, total generation cost, and per-generator dispatch (p_mw, q_mvar). Requires cost functions defined in net.poly_cost or net.pwl_cost.",
        "parameters": {},
    },
    {
        "name": "save_network_snapshot",
        "description": "Save a deep copy of the current network state under a label. Use before making modifications so you can restore later.",
        "parameters": {
            "label": {"type": "string", "description": "Label for the snapshot (e.g. 'base_case', 'before_scenario2')."},
        },
    },
    {
        "name": "restore_network_snapshot",
        "description": "Restore the network to a previously saved snapshot. All tables (bus, line, gen, load, etc.) are restored. Returns success/failure.",
        "parameters": {
            "label": {"type": "string", "description": "Label of the snapshot to restore."},
        },
    },
]


class SimulationTools:
    TOOL_DEFINITIONS = TOOL_DEFINITIONS

    @staticmethod
    def run_power_flow(net: pp.pandapowerNet, algorithm: str | None = None, **kwargs) -> dict:
        algorithm = algorithm or kwargs.get("algorithm", "nr")
        valid_algorithms = {"nr", "fdBX", "fdbx", "gs"}
        if algorithm not in valid_algorithms:
            algorithm = "nr"
        try:
            pp.runpp(net, algorithm=algorithm)
            converged = bool(net.converged)
            algo_name = {"nr": "Newton-Raphson", "fdBX": "fast-decoupled", "fdbx": "fast-decoupled", "gs": "Gauss-Seidel"}.get(algorithm, algorithm)
            return {
                "converged": converged,
                "algorithm": algo_name,
                "message": f"AC power flow ({algo_name}) {'converged' if converged else 'did not converge'}.",
            }
        except pp.LoadflowNotConverged:
            return {"converged": False, "message": "AC power flow did not converge (LoadflowNotConverged)."}
        except Exception as e:
            return {"converged": False, "message": str(e), "error": str(e)}

    @staticmethod
    def run_dc_power_flow(net: pp.pandapowerNet) -> dict:
        try:
            pp.rundcpp(net)
            return {"converged": True, "message": "DC power flow completed (linear approximation)."}
        except Exception as e:
            return {"converged": False, "message": str(e), "error": str(e)}

    @staticmethod
    def run_n1_contingency(
        net: pp.pandapowerNet,
        line_index: int | None = None,
        trafo_index: int | None = None,
        **kwargs,
    ) -> dict:
        line_index = line_index if line_index is not None else kwargs.get("line_index")
        trafo_index = trafo_index if trafo_index is not None else kwargs.get("trafo_index")
        if line_index is None and trafo_index is None:
            return {"error": "Provide line_index or trafo_index for N-1 contingency."}
        net_copy = copy.deepcopy(net)
        element = "unknown"
        try:
            if line_index is not None:
                if line_index not in net_copy.line.index:
                    return {"error": f"Line index {line_index} not in network."}
                net_copy.line.at[line_index, "in_service"] = False
                element = f"line_{line_index}"
            else:
                if trafo_index not in net_copy.trafo.index:
                    return {"error": f"Trafo index {trafo_index} not in network."}
                net_copy.trafo.at[trafo_index, "in_service"] = False
                element = f"trafo_{trafo_index}"
            pp.runpp(net_copy)
            converged = bool(net_copy.converged)
            
            result = {
                "element_out": element,
                "converged": converged,
                "message": f"N-1 ({element} out): power flow {'converged' if converged else 'did not converge'}.",
            }
            
            if converged:
                violations = DiagnosticTools.check_voltage_violations(net_copy)
                overloads = DiagnosticTools.check_overloads(net_copy)
                # Filter out disconnected buses (0.0 pu or NaN voltage)
                under = [v for v in violations.get("undervoltage_buses", []) if v.get("vm_pu", 0) > 0.01]
                over = [v for v in violations.get("overvoltage_buses", []) if v.get("vm_pu", 0) > 0.01]
                result["voltage_violations"] = len(under) + len(over)
                result["undervoltage_buses"] = under
                result["overvoltage_buses"] = over
                result["overloaded_lines"] = overloads.get("overloaded_lines", [])
                result["overloaded_trafos"] = overloads.get("overloaded_trafos", [])
                
            return result
        except pp.LoadflowNotConverged:
            return {
                "element_out": element,
                "converged": False,
                "message": f"N-1 ({element} out): power flow did not converge.",
            }
        except Exception as e:
            return {"error": str(e), "element_out": element}

    @staticmethod
    def run_short_circuit(
        net: pp.pandapowerNet,
        bus_index: int | None = None,
        fault_type: str = "3ph",
        **kwargs,
    ) -> dict:
        bus_index = bus_index if bus_index is not None else kwargs.get("bus_index")
        fault_type = fault_type or kwargs.get("fault_type", "3ph")

        if bus_index is None:
            return {"error": "bus_index is required for short-circuit analysis."}

        if bus_index not in net.bus.index:
            return {"error": f"Bus index {bus_index} not in network."}

        net_copy = copy.deepcopy(net)
        try:
            import pandapower.shortcircuit as sc

            # Prepare network for short-circuit: all required SC columns
            # Generator SC parameters (all required by ppc_conversion.py)
            if len(net_copy.gen) > 0:
                gen = net_copy.gen
                # vn_kv: use bus rated voltage as default
                if "vn_kv" not in gen.columns:
                    gen["vn_kv"] = gen["bus"].map(net_copy.bus["vn_kv"])
                else:
                    mask = gen["vn_kv"].isna()
                    if mask.any():
                        gen.loc[mask, "vn_kv"] = gen.loc[mask, "bus"].map(net_copy.bus["vn_kv"])
                # sn_mva: rated apparent power
                if "sn_mva" not in gen.columns:
                    gen["sn_mva"] = (gen["p_mw"].abs() / 0.8).clip(lower=10.0)
                else:
                    gen["sn_mva"] = gen["sn_mva"].fillna((gen["p_mw"].abs() / 0.8).clip(lower=10.0))
                # xdss_pu: subtransient reactance
                if "xdss_pu" not in gen.columns:
                    gen["xdss_pu"] = 0.2
                else:
                    gen["xdss_pu"] = gen["xdss_pu"].fillna(0.2)
                # rdss_ohm: subtransient resistance
                if "rdss_ohm" not in gen.columns:
                    gen["rdss_ohm"] = 0.005
                else:
                    gen["rdss_ohm"] = gen["rdss_ohm"].fillna(0.005)
                # cos_phi: rated power factor
                if "cos_phi" not in gen.columns:
                    gen["cos_phi"] = 0.85
                else:
                    gen["cos_phi"] = gen["cos_phi"].fillna(0.85)

            # External grid SC parameters
            if len(net_copy.ext_grid) > 0:
                eg = net_copy.ext_grid
                for col, default in [("s_sc_max_mva", 1000.0), ("rx_max", 0.1),
                                     ("s_sc_min_mva", 800.0), ("rx_min", 0.1)]:
                    if col not in eg.columns:
                        eg[col] = default
                    else:
                        eg[col] = eg[col].fillna(default)

            # sgen SC parameters (if any exist)
            if len(net_copy.sgen) > 0:
                sg = net_copy.sgen
                if "sn_mva" not in sg.columns:
                    sg["sn_mva"] = (sg["p_mw"].abs() / 0.9).clip(lower=1.0)
                else:
                    sg["sn_mva"] = sg["sn_mva"].fillna((sg["p_mw"].abs() / 0.9).clip(lower=1.0))
                if "k" not in sg.columns:
                    sg["k"] = 1.0
                else:
                    sg["k"] = sg["k"].fillna(1.0)

            if fault_type == "2ph":
                sc.calc_sc(net_copy, fault="2ph", case="max")
            else:
                sc.calc_sc(net_copy, fault="3ph", case="max")
            res_key = "res_bus_sc"

            res = getattr(net_copy, res_key, None)
            if res is None or res.empty:
                return {"error": "Short-circuit calculation produced no results."}

            if bus_index not in res.index:
                return {"error": f"Bus {bus_index} not in short-circuit results."}

            row = res.loc[bus_index]
            result = {
                "bus_index": int(bus_index),
                "fault_type": fault_type,
            }

            # Extract available SC quantities
            for col in ["ikss_ka", "skss_mw", "ip_ka", "ith_ka", "rk_ohm", "xk_ohm"]:
                if col in res.columns:
                    val = row[col]
                    if not (isinstance(val, float) and math.isnan(val)):
                        result[col] = round(float(val), 4)

            # Also return full bus SC table summary (top 10 by ikss_ka)
            if "ikss_ka" in res.columns:
                top = res.nlargest(10, "ikss_ka")
                summary = []
                for idx, r in top.iterrows():
                    entry = {"bus": int(idx)}
                    for col in ["ikss_ka", "skss_mw"]:
                        if col in res.columns:
                            entry[col] = round(float(r[col]), 4)
                    summary.append(entry)
                result["top_10_buses_by_ikss"] = summary

            return result

        except ImportError:
            return {"error": "pandapower.shortcircuit module not available."}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def _ensure_opf_costs(net: pp.pandapowerNet) -> None:
        """Create default quadratic cost functions if none exist."""
        has_poly = hasattr(net, "poly_cost") and not net.poly_cost.empty
        has_pwl = hasattr(net, "pwl_cost") and not net.pwl_cost.empty
        if has_poly or has_pwl:
            return

        # Create quadratic cost functions for each generator: cost = cp1_eur_per_mw * p
        # Use a simple linear cost (cp2=0) with different marginal costs per gen
        for idx in net.gen.index:
            # Ensure gen has min/max limits for OPF
            if "min_p_mw" not in net.gen.columns or pd.isna(net.gen.at[idx, "min_p_mw"]):
                net.gen.at[idx, "min_p_mw"] = 0.0
            if "max_p_mw" not in net.gen.columns or pd.isna(net.gen.at[idx, "max_p_mw"]):
                net.gen.at[idx, "max_p_mw"] = net.gen.at[idx, "p_mw"] * 2.0 if net.gen.at[idx, "p_mw"] > 0 else 100.0
            if "min_q_mvar" not in net.gen.columns or pd.isna(net.gen.at[idx, "min_q_mvar"]):
                net.gen.at[idx, "min_q_mvar"] = -9999.0
            if "max_q_mvar" not in net.gen.columns or pd.isna(net.gen.at[idx, "max_q_mvar"]):
                net.gen.at[idx, "max_q_mvar"] = 9999.0

            # Quadratic cost: cost = cp2 * p^2 + cp1 * p + cp0
            pp.create_poly_cost(net, idx, "gen", cp1_eur_per_mw=40.0, cp0_eur=0.0, cp2_eur_per_mw2=0.02)

        # Also add cost for ext_grid (slack) to avoid unbounded solution
        for idx in net.ext_grid.index:
            if "min_p_mw" not in net.ext_grid.columns or pd.isna(net.ext_grid.at[idx, "min_p_mw"]):
                net.ext_grid.at[idx, "min_p_mw"] = -9999.0
            if "max_p_mw" not in net.ext_grid.columns or pd.isna(net.ext_grid.at[idx, "max_p_mw"]):
                net.ext_grid.at[idx, "max_p_mw"] = 9999.0
            if "min_q_mvar" not in net.ext_grid.columns or pd.isna(net.ext_grid.at[idx, "min_q_mvar"]):
                net.ext_grid.at[idx, "min_q_mvar"] = -9999.0
            if "max_q_mvar" not in net.ext_grid.columns or pd.isna(net.ext_grid.at[idx, "max_q_mvar"]):
                net.ext_grid.at[idx, "max_q_mvar"] = 9999.0
            pp.create_poly_cost(net, idx, "ext_grid", cp1_eur_per_mw=50.0, cp0_eur=0.0, cp2_eur_per_mw2=0.03)

    @staticmethod
    def run_opf(net: pp.pandapowerNet, **kwargs) -> dict:
        try:
            # Ensure cost functions exist before running OPF
            SimulationTools._ensure_opf_costs(net)
            pp.runopp(net)
            converged = bool(getattr(net, "OPF_converged", True))

            result: dict = {
                "converged": converged,
                "message": "AC OPF converged." if converged else "AC OPF did not converge.",
            }

            if not converged:
                return result

            # Total generation cost
            if hasattr(net, "res_cost") and net.res_cost is not None:
                result["total_cost"] = round(float(net.res_cost), 4)

            # Per-generator dispatch
            if hasattr(net, "res_gen") and not net.res_gen.empty:
                gens = []
                for idx, row in net.res_gen.iterrows():
                    entry = {"gen_index": int(idx)}
                    for col in ["p_mw", "q_mvar", "va_degree", "vm_pu"]:
                        if col in net.res_gen.columns:
                            entry[col] = round(float(row[col]), 4)
                    gens.append(entry)
                result["generators"] = gens

            # External grid dispatch
            if hasattr(net, "res_ext_grid") and not net.res_ext_grid.empty:
                ext = []
                for idx, row in net.res_ext_grid.iterrows():
                    entry = {"ext_grid_index": int(idx)}
                    for col in ["p_mw", "q_mvar"]:
                        if col in net.res_ext_grid.columns:
                            entry[col] = round(float(row[col]), 4)
                    ext.append(entry)
                result["ext_grids"] = ext

            return result

        except Exception as e:
            return {"converged": False, "message": str(e), "error": str(e)}

    @staticmethod
    def save_network_snapshot(
        net: pp.pandapowerNet,
        label: str = "default",
        **kwargs,
    ) -> dict:
        label = label or kwargs.get("label", "default")
        _network_snapshots[label] = copy.deepcopy(net)
        return {
            "success": True,
            "label": label,
            "message": f"Network snapshot saved as '{label}'.",
        }

    @staticmethod
    def restore_network_snapshot(
        net: pp.pandapowerNet,
        label: str = "default",
        **kwargs,
    ) -> dict:
        label = label or kwargs.get("label", "default")
        if label not in _network_snapshots:
            available = list(_network_snapshots.keys())
            return {
                "success": False,
                "error": f"No snapshot found with label '{label}'. Available: {available}",
            }

        saved = _network_snapshots[label]
        # Restore all dataframe attributes from the snapshot
        for attr in dir(saved):
            if attr.startswith("_"):
                continue
            try:
                val = getattr(saved, attr)
                if isinstance(val, pd.DataFrame):
                    setattr(net, attr, val.copy())
                elif isinstance(val, (bool, int, float, str, list, dict)):
                    setattr(net, attr, copy.deepcopy(val))
            except Exception:
                continue

        return {
            "success": True,
            "label": label,
            "message": f"Network restored from snapshot '{label}'.",
        }

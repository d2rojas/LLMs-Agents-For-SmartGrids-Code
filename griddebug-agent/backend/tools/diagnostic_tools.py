"""
Diagnostic tools for the agentic pipeline: overloads, voltage violations, disconnected areas.
"""
from __future__ import annotations

import pandas as pd
import pandapower as pp


def _safe_float(x) -> float:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return 0.0
    return float(x)


TOOL_DEFINITIONS = [
    {
        "name": "run_full_diagnostics",
        "description": "Run pandapower network diagnostic (checks topology, indices, etc.). Returns dict of test names to results.",
        "parameters": {},
    },
    {
        "name": "check_overloads",
        "description": "Check line and transformer loading above a threshold (default 100%). Returns overloaded elements.",
        "parameters": {
            "threshold_percent": {
                "type": "number",
                "description": "Loading threshold in percent (default 100).",
            }
        },
    },
    {
        "name": "check_voltage_violations",
        "description": "Check bus voltages outside [v_min, v_max] pu (default 0.95–1.05). Returns under/over voltage buses.",
        "parameters": {
            "v_min": {"type": "number", "description": "Minimum voltage pu (default 0.95)."},
            "v_max": {"type": "number", "description": "Maximum voltage pu (default 1.05)."},
        },
    },
    {
        "name": "find_disconnected_areas",
        "description": "Find buses not connected to the external grid (topology check).",
        "parameters": {},
    },
]


def _convert_to_native(obj):
    import numpy as np
    import pandas as pd
    if isinstance(obj, dict):
        return {k: _convert_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [_convert_to_native(i) for i in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return _convert_to_native(obj.tolist())
    elif isinstance(obj, pd.Series):
        return _convert_to_native(obj.tolist())
    elif isinstance(obj, pd.DataFrame):
        return _convert_to_native(obj.to_dict(orient="records"))
    elif pd.isna(obj):
        return None
    elif isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    else:
        return str(obj)

class DiagnosticTools:
    TOOL_DEFINITIONS = TOOL_DEFINITIONS

    @staticmethod
    def run_full_diagnostics(net: pp.pandapowerNet) -> dict:
        try:
            from pandapower.diagnostic import Diagnostic
            diag = Diagnostic()
            result = diag.diagnose_network(
                net, report_style=None, warnings_only=True, return_result_dict=True
            )
            if isinstance(result, dict):
                # Filter out empty results to keep output clean
                cleaned_result = {k: _convert_to_native(v) for k, v in result.items() if v}
                return {"ran": True, "results": cleaned_result}
            return {"ran": True, "results": _convert_to_native(result)}
        except Exception as e:
            return {"ran": False, "error": str(e)}

    @staticmethod
    def check_overloads(
        net: pp.pandapowerNet,
        threshold_percent: float | None = None,
        **kwargs,
    ) -> dict:
        threshold = _safe_float(threshold_percent if threshold_percent is not None else kwargs.get("threshold_percent", 100))
        if threshold <= 0:
            threshold = 100.0
        overloaded_lines = []
        overloaded_trafos = []
        if getattr(net, "converged", False):
            if hasattr(net, "res_line") and not net.res_line.empty and "loading_percent" in net.res_line.columns:
                for idx, row in net.res_line[net.res_line["loading_percent"] > threshold].iterrows():
                    overloaded_lines.append({
                        "line_index": int(idx),
                        "loading_percent": round(_safe_float(row["loading_percent"]), 1),
                        "from_bus": int(net.line.at[idx, "from_bus"]),
                        "to_bus": int(net.line.at[idx, "to_bus"]),
                    })
            if len(net.trafo) and hasattr(net, "res_trafo") and not net.res_trafo.empty and "loading_percent" in net.res_trafo.columns:
                for idx, row in net.res_trafo[net.res_trafo["loading_percent"] > threshold].iterrows():
                    overloaded_trafos.append({
                        "trafo_index": int(idx),
                        "loading_percent": round(_safe_float(row["loading_percent"]), 1),
                    })
        return {
            "threshold_percent": threshold,
            "overloaded_lines": overloaded_lines,
            "overloaded_trafos": overloaded_trafos,
            "converged": getattr(net, "converged", False),
        }

    @staticmethod
    def check_voltage_violations(
        net: pp.pandapowerNet,
        v_min: float | None = None,
        v_max: float | None = None,
        **kwargs,
    ) -> dict:
        global_v_min = _safe_float(v_min if v_min is not None else kwargs.get("v_min", 0.95))
        global_v_max = _safe_float(v_max if v_max is not None else kwargs.get("v_max", 1.05))
        undervoltage = []
        overvoltage = []
        if getattr(net, "converged", False) and hasattr(net, "res_bus") and not net.res_bus.empty:
            res = net.res_bus
            bus_df = net.bus
            for idx, row in res.iterrows():
                vm_pu = round(_safe_float(row["vm_pu"]), 4)
                
                # Use bus-specific limits if available, otherwise global defaults
                bus_v_min = bus_df.at[idx, "min_vm_pu"] if "min_vm_pu" in bus_df.columns and pd.notna(bus_df.at[idx, "min_vm_pu"]) else global_v_min
                bus_v_max = bus_df.at[idx, "max_vm_pu"] if "max_vm_pu" in bus_df.columns and pd.notna(bus_df.at[idx, "max_vm_pu"]) else global_v_max
                
                if vm_pu < bus_v_min:
                    undervoltage.append({"bus": int(idx), "vm_pu": vm_pu, "limit": bus_v_min})
                elif vm_pu > bus_v_max:
                    overvoltage.append({"bus": int(idx), "vm_pu": vm_pu, "limit": bus_v_max})
        return {
            "v_min_pu_global": global_v_min,
            "v_max_pu_global": global_v_max,
            "undervoltage_buses": undervoltage,
            "overvoltage_buses": overvoltage,
            "total_violations": len(undervoltage) + len(overvoltage),
            "converged": getattr(net, "converged", False),
        }

    @staticmethod
    def find_disconnected_areas(net: pp.pandapowerNet) -> dict:
        try:
            from pandapower.topology import create_nxgraph
            import networkx as nx
            G = create_nxgraph(net, respect_switches=True, include_out_of_service=False)
            ext_buses = set(net.ext_grid["bus"].astype(int))
            if not ext_buses:
                return {"disconnected_buses": list(G.nodes()), "message": "No external grid defined."}
            reachable = set()
            for sb in ext_buses:
                if sb in G:
                    reachable |= set(nx.descendants(G, sb)) | {sb}
            all_buses = set(G.nodes())
            disconnected = list(all_buses - reachable)
            return {
                "disconnected_buses": [int(b) for b in sorted(disconnected)],
                "connected_buses": [int(b) for b in sorted(reachable)],
                "message": f"{len(disconnected)} bus(es) not connected to slack." if disconnected else "All buses connected.",
            }
        except ImportError:
            return {"error": "networkx required for find_disconnected_areas.", "disconnected_buses": []}
        except Exception as e:
            return {"error": str(e), "disconnected_buses": []}

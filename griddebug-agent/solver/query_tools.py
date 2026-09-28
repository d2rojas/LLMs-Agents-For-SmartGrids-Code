"""
Query tools for the agentic pipeline.
Return JSON-serializable dicts for LLM consumption.
"""
from __future__ import annotations

import pandas as pd
import pandapower as pp


def _safe_float(x) -> float:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return 0.0
    return float(x)


def _df_to_records(df: pd.DataFrame, max_rows: int = 50) -> list[dict]:
    if df is None or df.empty:
        return []
    out = []
    for idx, row in df.head(max_rows).iterrows():
        rec = {"index": int(idx)}
        for c in df.columns:
            v = row[c]
            if pd.isna(v):
                rec[c] = None
            elif isinstance(v, (int, float)):
                rec[c] = v
            else:
                rec[c] = str(v)
        out.append(rec)
    return out


TOOL_DEFINITIONS = [
    {
        "name": "get_network_summary",
        "description": "Get high-level summary: bus count, line count, generators, loads, convergence status.",
        "parameters": {},
    },
    {
        "name": "get_bus_data",
        "description": "Get bus table (optional: list of bus indices to filter).",
        "parameters": {
            "bus_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Optional list of bus indices; if omitted returns all buses.",
            }
        },
    },
    {
        "name": "get_line_data",
        "description": "Get line table with from_bus, to_bus, in_service (optional: line indices).",
        "parameters": {
            "line_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Optional list of line indices; if omitted returns all lines.",
            }
        },
    },
    {
        "name": "get_gen_data",
        "description": "Get generator table: bus, p_mw, in_service, max_p_mw (optional: gen indices).",
        "parameters": {
            "gen_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Optional list of generator indices; if omitted returns all.",
            }
        },
    },
    {
        "name": "get_voltage_profile",
        "description": "Get bus voltage magnitudes (vm_pu) and angles; only available if power flow converged.",
        "parameters": {},
    },
    {
        "name": "get_loading_profile",
        "description": "Get line and transformer loading (percent); only available if power flow converged.",
        "parameters": {},
    },
    {
        "name": "get_power_balance",
        "description": "Get total load P/Q, total generation P/Q, total active power loss (MW), and load/gen ratio.",
        "parameters": {},
    },
    {
        "name": "get_line_results",
        "description": "Get power flow results for lines: p_from_mw, p_to_mw, q_from_mvar, q_to_mvar, pl_mw (losses), loading_percent. Only available if power flow converged.",
        "parameters": {
            "line_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Optional list of line indices; if omitted returns all lines.",
            }
        },
    },
    {
        "name": "get_bus_results",
        "description": "Get power flow results for buses: vm_pu, va_degree, p_mw, q_mvar. Only available if power flow converged.",
        "parameters": {
            "bus_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Optional list of bus indices; if omitted returns all buses.",
            }
        },
    },
]


class QueryTools:
    TOOL_DEFINITIONS = TOOL_DEFINITIONS

    @staticmethod
    def get_network_summary(net: pp.pandapowerNet) -> dict:
        converged = getattr(net, "converged", False)
        n_bus = len(net.bus)
        n_line = len(net.line)
        n_trafo = len(net.trafo)
        n_gen = len(net.gen[net.gen["in_service"]]) if len(net.gen) else 0
        n_load = len(net.load[net.load["in_service"]])
        return {
            "converged": converged,
            "bus_count": n_bus,
            "line_count": n_line,
            "trafo_count": n_trafo,
            "generator_count": n_gen,
            "load_count": n_load,
        }

    @staticmethod
    def get_bus_data(net: pp.pandapowerNet, bus_ids: list[int] | None = None, **kwargs) -> dict:
        bus_ids = bus_ids if bus_ids is not None else kwargs.get("bus_ids")
        df = net.bus
        if bus_ids is not None and len(bus_ids) > 0:
            df = df.loc[df.index.intersection(bus_ids)]
        return {"buses": _df_to_records(df)}

    @staticmethod
    def get_line_data(net: pp.pandapowerNet, line_ids: list[int] | None = None, **kwargs) -> dict:
        line_ids = line_ids if line_ids is not None else kwargs.get("line_ids")
        df = net.line[["from_bus", "to_bus", "in_service", "length_km"]].copy()
        if "max_i_ka" in net.line.columns:
            df["max_i_ka"] = net.line["max_i_ka"]
        if line_ids is not None and len(line_ids) > 0:
            df = df.loc[df.index.intersection(line_ids)]
        return {"lines": _df_to_records(df)}

    @staticmethod
    def get_gen_data(net: pp.pandapowerNet, gen_ids: list[int] | None = None, **kwargs) -> dict:
        gen_ids = gen_ids if gen_ids is not None else kwargs.get("gen_ids")
        df = net.gen
        if gen_ids is not None and len(gen_ids) > 0:
            df = df.loc[df.index.intersection(gen_ids)]
        return {"generators": _df_to_records(df)}

    @staticmethod
    def get_voltage_profile(net: pp.pandapowerNet) -> dict:
        if not getattr(net, "converged", False) or not hasattr(net, "res_bus") or net.res_bus.empty:
            return {"available": False, "message": "Power flow did not converge or no results.", "voltages": []}
        res = net.res_bus
        voltages = []
        for idx in res.index:
            voltages.append({
                "bus": int(idx),
                "vm_pu": round(_safe_float(res.at[idx, "vm_pu"]), 4),
                "va_degree": round(_safe_float(res.at[idx, "va_degree"]), 2) if "va_degree" in res.columns else None,
            })
        return {"available": True, "voltages": voltages}

    @staticmethod
    def get_loading_profile(net: pp.pandapowerNet) -> dict:
        if not getattr(net, "converged", False):
            return {"available": False, "message": "Power flow did not converge.", "lines": [], "trafos": []}
        lines = []
        if hasattr(net, "res_line") and not net.res_line.empty and "loading_percent" in net.res_line.columns:
            for idx, row in net.res_line.iterrows():
                lines.append({
                    "line_index": int(idx),
                    "loading_percent": round(_safe_float(row["loading_percent"]), 1),
                })
        trafos = []
        if len(net.trafo) and hasattr(net, "res_trafo") and not net.res_trafo.empty and "loading_percent" in net.res_trafo.columns:
            for idx, row in net.res_trafo.iterrows():
                trafos.append({
                    "trafo_index": int(idx),
                    "loading_percent": round(_safe_float(row["loading_percent"]), 1),
                })
        return {"available": True, "lines": lines, "trafos": trafos}

    @staticmethod
    def get_line_results(net: pp.pandapowerNet, line_ids: list[int] | None = None, **kwargs) -> dict:
        line_ids = line_ids if line_ids is not None else kwargs.get("line_ids")
        if not getattr(net, "converged", False) or not hasattr(net, "res_line") or net.res_line.empty:
            return {"available": False, "message": "Power flow did not converge or no results.", "lines": []}
        df = net.res_line
        if line_ids is not None and len(line_ids) > 0:
            df = df.loc[df.index.intersection(line_ids)]
        results = []
        for idx, row in df.iterrows():
            results.append({
                "line_index": int(idx),
                "p_from_mw": round(_safe_float(row.get("p_from_mw")), 4),
                "p_to_mw": round(_safe_float(row.get("p_to_mw")), 4),
                "q_from_mvar": round(_safe_float(row.get("q_from_mvar")), 4),
                "q_to_mvar": round(_safe_float(row.get("q_to_mvar")), 4),
                "pl_mw": round(_safe_float(row.get("pl_mw")), 4),
                "loading_percent": round(_safe_float(row.get("loading_percent")), 2),
            })
        return {"available": True, "lines": results}

    @staticmethod
    def get_bus_results(net: pp.pandapowerNet, bus_ids: list[int] | None = None, **kwargs) -> dict:
        bus_ids = bus_ids if bus_ids is not None else kwargs.get("bus_ids")
        if not getattr(net, "converged", False) or not hasattr(net, "res_bus") or net.res_bus.empty:
            return {"available": False, "message": "Power flow did not converge or no results.", "buses": []}
        df = net.res_bus
        if bus_ids is not None and len(bus_ids) > 0:
            df = df.loc[df.index.intersection(bus_ids)]
        results = []
        for idx, row in df.iterrows():
            results.append({
                "bus_index": int(idx),
                "vm_pu": round(_safe_float(row.get("vm_pu")), 4),
                "va_degree": round(_safe_float(row.get("va_degree")), 4),
                "p_mw": round(_safe_float(row.get("p_mw")), 4),
                "q_mvar": round(_safe_float(row.get("q_mvar")), 4),
            })
        return {"available": True, "buses": results}

    @staticmethod
    def get_power_balance(net: pp.pandapowerNet) -> dict:
        in_service_loads = net.load[net.load["in_service"]]
        total_load_p = float(in_service_loads["p_mw"].sum())
        total_load_q = float(in_service_loads["q_mvar"].sum())
        total_gen_p = 0.0
        total_gen_q = 0.0
        if hasattr(net, "res_gen") and not net.res_gen.empty:
            total_gen_p += float(net.res_gen["p_mw"].sum())
            total_gen_q += float(net.res_gen["q_mvar"].sum())
        if hasattr(net, "res_ext_grid") and not net.res_ext_grid.empty:
            total_gen_p += float(net.res_ext_grid["p_mw"].sum())
            total_gen_q += float(net.res_ext_grid["q_mvar"].sum())
        gen_capacity = 0.0
        if len(net.gen) > 0:
            in_service_gens = net.gen[net.gen["in_service"]]
            for _, row in in_service_gens.iterrows():
                gen_capacity += _safe_float(row.get("max_p_mw", row.get("p_mw", 0)))
        total_loss_p = round(total_gen_p - total_load_p, 4) if total_gen_p > 0 else None
        return {
            "total_load_p_mw": round(total_load_p, 2),
            "total_load_q_mvar": round(total_load_q, 2),
            "total_gen_p_mw": round(total_gen_p, 2),
            "total_gen_q_mvar": round(total_gen_q, 2),
            "total_active_power_loss_mw": total_loss_p,
            "gen_capacity_mw": round(gen_capacity, 2),
            "load_gen_ratio": round(total_load_p / gen_capacity, 2) if gen_capacity > 0 else None,
        }

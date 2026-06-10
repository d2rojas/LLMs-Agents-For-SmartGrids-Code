"""Pandapower-based AC power flow and network edits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional
import re

import pandapower as pp

from models.schemas import BusVoltage, LineFlow, NetworkInfo, PowerFlowResult
from solver.validators import validate_result


@dataclass(frozen=True)
class SolverConfig:
    algorithm: str = "nr"
    v_min: float = 0.95
    v_max: float = 1.05
    max_loading: float = 100.0


BranchType = Literal["line", "trafo"]


def _case_name_from_net(net: object) -> str:
    name = getattr(net, "_case_name", None) or getattr(net, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    return "unknown_case"


def _parse_bus_name_to_id(name: object) -> Optional[int]:
    if name is None:
        return None
    s = str(name).strip()
    if not s:
        return None
    if re.fullmatch(r"[-+]?\d+", s):
        return int(s)
    return None


def _bus_display_id(net: object, bus_idx: int) -> int:
    try:
        parsed = _parse_bus_name_to_id(net.bus.at[bus_idx, "name"])
        if parsed is not None:
            return int(parsed)
    except Exception:
        pass
    # MATPOWER conversion typically uses internal index = MATPOWER bus id - 1.
    return int(bus_idx) + 1


def _resolve_bus_index(net: object, bus_id: int) -> int:
    if "name" in net.bus.columns:
        matches = net.bus.index[net.bus["name"].astype(str) == str(bus_id)].tolist()
        if matches:
            return int(matches[0])
        for idx, name in net.bus["name"].items():
            parsed = _parse_bus_name_to_id(name)
            if parsed is not None and int(parsed) == int(bus_id):
                return int(idx)

    # Resolve by the same display-id mapping used in plots/results.
    for idx in net.bus.index.tolist():
        if int(_bus_display_id(net, int(idx))) == int(bus_id):
            return int(idx)

    if bus_id in net.bus.index:
        return int(bus_id)

    raise ValueError(f"Invalid bus_id: {bus_id}")


def _find_branches_between(net: object, fb: int, tb: int) -> list[tuple[BranchType, int]]:
    found: list[tuple[BranchType, int]] = []

    if hasattr(net, "line") and len(net.line) > 0:
        for idx, row in net.line.iterrows():
            a, b = int(row["from_bus"]), int(row["to_bus"])
            if (a == fb and b == tb) or (a == tb and b == fb):
                found.append(("line", int(idx)))

    if hasattr(net, "trafo") and len(net.trafo) > 0:
        for idx, row in net.trafo.iterrows():
            a, b = int(row["hv_bus"]), int(row["lv_bus"])
            if (a == fb and b == tb) or (a == tb and b == fb):
                found.append(("trafo", int(idx)))

    return found


def _set_branch_in_service(net: object, btype: BranchType, idx: int, in_service: bool) -> None:
    if btype == "line":
        net.line.at[idx, "in_service"] = bool(in_service)
    elif btype == "trafo":
        net.trafo.at[idx, "in_service"] = bool(in_service)
    else:
        raise ValueError(f"Unknown branch type: {btype}")


def _compute_network_info(net: object) -> NetworkInfo:
    n_buses = int(len(net.bus))
    n_loads = int(len(net.load)) if hasattr(net, "load") else 0

    n_generators = 0
    capacity = 0.0

    if hasattr(net, "gen"):
        n_generators += int(len(net.gen))
        if "max_p_mw" in net.gen.columns:
            capacity += float(net.gen["max_p_mw"].fillna(net.gen["p_mw"]).sum())
        else:
            capacity += float(net.gen["p_mw"].sum())

    if hasattr(net, "ext_grid"):
        n_generators += int(len(net.ext_grid))
        if "max_p_mw" in net.ext_grid.columns:
            capacity += float(net.ext_grid["max_p_mw"].fillna(0.0).sum())

    n_lines = 0
    if hasattr(net, "line"):
        n_lines += int(len(net.line))
    if hasattr(net, "trafo"):
        n_lines += int(len(net.trafo))

    total_load_mw = float(net.load["p_mw"].sum()) if hasattr(net, "load") else 0.0

    return NetworkInfo(
        case_name=_case_name_from_net(net),
        n_buses=n_buses,
        n_generators=n_generators,
        n_lines=n_lines,
        n_loads=n_loads,
        total_load_mw=total_load_mw,
        total_gen_capacity_mw=float(capacity),
    )


def get_network_status(net: object) -> NetworkInfo:
    return _compute_network_info(net)


def _extract_totals(net: object) -> tuple[float, float, float]:
    total_gen = 0.0
    total_load = 0.0
    total_loss = 0.0

    if hasattr(net, "res_ext_grid") and len(net.res_ext_grid) > 0:
        total_gen += float(net.res_ext_grid["p_mw"].sum())
    if hasattr(net, "res_gen") and len(net.res_gen) > 0:
        total_gen += float(net.res_gen["p_mw"].sum())
    if hasattr(net, "res_sgen") and len(net.res_sgen) > 0:
        total_gen += float(net.res_sgen["p_mw"].sum())

    if hasattr(net, "res_load") and len(net.res_load) > 0:
        total_load += float(net.res_load["p_mw"].sum())

    if hasattr(net, "res_line") and len(net.res_line) > 0 and "pl_mw" in net.res_line.columns:
        total_loss += float(net.res_line["pl_mw"].sum())
    if hasattr(net, "res_trafo") and len(net.res_trafo) > 0 and "pl_mw" in net.res_trafo.columns:
        total_loss += float(net.res_trafo["pl_mw"].sum())
    if hasattr(net, "res_trafo3w") and len(net.res_trafo3w) > 0 and "pl_mw" in net.res_trafo3w.columns:
        total_loss += float(net.res_trafo3w["pl_mw"].sum())

    return float(total_gen), float(total_load), float(total_loss)


def _extract_bus_voltages(net: object) -> list[BusVoltage]:
    bvs: list[BusVoltage] = []
    for bus_idx, row in net.res_bus.iterrows():
        bus_id = _bus_display_id(net, int(bus_idx))
        bvs.append(
            BusVoltage(
                bus_id=int(bus_id),
                vm_pu=float(row["vm_pu"]),
                va_deg=float(row["va_degree"]),
                is_violation=False,
                violation_type=None,
            )
        )
    return bvs


def _extract_line_flows(net: object) -> list[LineFlow]:
    flows: list[LineFlow] = []

    if hasattr(net, "res_line") and len(net.res_line) > 0:
        for idx, row in net.res_line.iterrows():
            fb = int(net.line.at[idx, "from_bus"])
            tb = int(net.line.at[idx, "to_bus"])
            flows.append(
                LineFlow(
                    line_id=int(idx),
                    from_bus=_bus_display_id(net, fb),
                    to_bus=_bus_display_id(net, tb),
                    p_from_mw=float(row["p_from_mw"]),
                    q_from_mvar=float(row["q_from_mvar"]),
                    loading_percent=float(row.get("loading_percent", 0.0)),
                    is_violation=False,
                )
            )

    if hasattr(net, "res_trafo") and len(net.res_trafo) > 0:
        for idx, row in net.res_trafo.iterrows():
            fb = int(net.trafo.at[idx, "hv_bus"])
            tb = int(net.trafo.at[idx, "lv_bus"])
            flows.append(
                LineFlow(
                    line_id=100000 + int(idx),
                    from_bus=_bus_display_id(net, fb),
                    to_bus=_bus_display_id(net, tb),
                    p_from_mw=float(row["p_hv_mw"]),
                    q_from_mvar=float(row["q_hv_mvar"]),
                    loading_percent=float(row.get("loading_percent", 0.0)),
                    is_violation=False,
                )
            )

    return flows


def run_power_flow(net: object, *, config: SolverConfig = SolverConfig()) -> PowerFlowResult:
    case_name = _case_name_from_net(net)

    try:
        pp.runpp(net, algorithm=config.algorithm)
        converged = bool(getattr(net, "converged", True))
    except Exception as e:
        return PowerFlowResult(
            case_name=case_name,
            converged=False,
            bus_voltages=[],
            line_flows=[],
            total_generation_mw=0.0,
            total_load_mw=0.0,
            total_loss_mw=0.0,
            summary_text=f"Power flow failed: {type(e).__name__}: {e}",
        )

    if not converged:
        return PowerFlowResult(
            case_name=case_name,
            converged=False,
            bus_voltages=[],
            line_flows=[],
            total_generation_mw=0.0,
            total_load_mw=0.0,
            total_loss_mw=0.0,
            summary_text="Power flow did not converge.",
        )

    total_gen, total_load, total_loss = _extract_totals(net)
    result = PowerFlowResult(
        case_name=case_name,
        converged=True,
        bus_voltages=_extract_bus_voltages(net),
        line_flows=_extract_line_flows(net),
        total_generation_mw=total_gen,
        total_load_mw=total_load,
        total_loss_mw=total_loss,
        summary_text="",
    )

    return validate_result(
        net,
        result,
        v_min=config.v_min,
        v_max=config.v_max,
        max_loading=config.max_loading,
    )


def modify_bus_load(
    net: object,
    bus_id: int,
    p_mw: float,
    q_mvar: Optional[float] = None,
    *,
    config: SolverConfig = SolverConfig(),
) -> PowerFlowResult:
    bus_idx = _resolve_bus_index(net, bus_id)

    if not hasattr(net, "load"):
        raise ValueError("Current network has no load table")

    load_rows = net.load.index[net.load["bus"] == bus_idx].tolist()
    if not load_rows:
        pp.create_load(net, bus=bus_idx, p_mw=float(p_mw), q_mvar=float(q_mvar or 0.0))
    else:
        first = int(load_rows[0])
        net.load.at[first, "p_mw"] = float(p_mw)
        if q_mvar is not None:
            net.load.at[first, "q_mvar"] = float(q_mvar)
        for extra in load_rows[1:]:
            net.load.at[int(extra), "p_mw"] = 0.0
            if q_mvar is not None:
                net.load.at[int(extra), "q_mvar"] = 0.0

    return run_power_flow(net, config=config)


def disconnect_line(
    net: object,
    from_bus: int,
    to_bus: int,
    *,
    config: SolverConfig = SolverConfig(),
) -> PowerFlowResult:
    fb = _resolve_bus_index(net, from_bus)
    tb = _resolve_bus_index(net, to_bus)

    branches = _find_branches_between(net, fb, tb)
    if not branches:
        raise ValueError(f"No branch found between bus {from_bus} and bus {to_bus}")

    btype, idx = branches[0]
    _set_branch_in_service(net, btype, idx, False)

    return run_power_flow(net, config=config)


def reconnect_line(
    net: object,
    from_bus: int,
    to_bus: int,
    *,
    config: SolverConfig = SolverConfig(),
) -> PowerFlowResult:
    fb = _resolve_bus_index(net, from_bus)
    tb = _resolve_bus_index(net, to_bus)

    branches = _find_branches_between(net, fb, tb)
    if not branches:
        raise ValueError(f"No branch found between bus {from_bus} and bus {to_bus}")

    btype, idx = branches[0]
    _set_branch_in_service(net, btype, idx, True)

    return run_power_flow(net, config=config)

"""N-1 contingency analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal, Optional
import re

from models.schemas import ContingencyOutcome, N1Report
from solver.power_flow import SolverConfig, run_power_flow


BranchType = Literal["line", "trafo"]


@dataclass(frozen=True)
class BranchRef:
    branch_type: BranchType
    idx: int
    from_bus: int
    to_bus: int

    @property
    def branch_id(self) -> int:
        return self.idx if self.branch_type == "line" else 100000 + self.idx


def _bus_display_id(net: Any, bus_idx: int) -> int:
    try:
        name = net.bus.at[bus_idx, "name"]
        s = str(name).strip() if name is not None else ""
        if s and re.fullmatch(r"[-+]?\d+", s):
            return int(s)
    except Exception:
        pass
    return int(bus_idx) + 1


def iter_in_service_branches(net: Any) -> Iterable[BranchRef]:
    if hasattr(net, "line") and len(net.line) > 0:
        for idx, row in net.line.iterrows():
            if bool(row.get("in_service", True)):
                yield BranchRef("line", int(idx), int(row["from_bus"]), int(row["to_bus"]))

    if hasattr(net, "trafo") and len(net.trafo) > 0:
        for idx, row in net.trafo.iterrows():
            if bool(row.get("in_service", True)):
                yield BranchRef("trafo", int(idx), int(row["hv_bus"]), int(row["lv_bus"]))


def set_branch_in_service(net: Any, ref: BranchRef, in_service: bool) -> None:
    if ref.branch_type == "line":
        net.line.at[ref.idx, "in_service"] = bool(in_service)
    else:
        net.trafo.at[ref.idx, "in_service"] = bool(in_service)


def _score_outcome(
    *,
    converged: bool,
    n_v: int,
    n_t: int,
    worst_vm: Optional[float],
    worst_loading: Optional[float],
    criteria: str,
    v_min: float,
) -> float:
    if not converged:
        return 1e9

    worst_vm = worst_vm if worst_vm is not None else 10.0
    worst_loading = worst_loading if worst_loading is not None else 0.0

    base = 10000.0 * (n_v + n_t)
    undervolt_penalty = max(0.0, v_min - worst_vm) * 100000.0
    overload_penalty = max(0.0, worst_loading - 100.0) * 1000.0

    if criteria == "max_overload":
        return base * 0.1 + worst_loading * 100.0 + overload_penalty + undervolt_penalty
    if criteria == "min_voltage":
        return base + (10.0 - worst_vm) * 10000.0 + overload_penalty
    return base + overload_penalty + undervolt_penalty + worst_loading


def get_most_loaded_branch(net: Any) -> Optional[dict[str, Any]]:
    best: Optional[tuple[BranchRef, float]] = None

    if hasattr(net, "res_line") and len(net.res_line) > 0:
        for idx, row in net.res_line.iterrows():
            loading = float(row.get("loading_percent", 0.0))
            fb = int(net.line.at[idx, "from_bus"])
            tb = int(net.line.at[idx, "to_bus"])
            ref = BranchRef("line", int(idx), fb, tb)
            if best is None or loading > best[1]:
                best = (ref, loading)

    if hasattr(net, "res_trafo") and len(net.res_trafo) > 0:
        for idx, row in net.res_trafo.iterrows():
            loading = float(row.get("loading_percent", 0.0))
            fb = int(net.trafo.at[idx, "hv_bus"])
            tb = int(net.trafo.at[idx, "lv_bus"])
            ref = BranchRef("trafo", int(idx), fb, tb)
            if best is None or loading > best[1]:
                best = (ref, loading)

    if best is None:
        return None

    ref, loading = best
    return {
        "branch_id": ref.branch_id,
        "branch_type": ref.branch_type,
        "from_bus": _bus_display_id(net, ref.from_bus),
        "to_bus": _bus_display_id(net, ref.to_bus),
        "loading_percent": loading,
    }


def run_n1_contingency(
    net: Any,
    *,
    top_k: int = 5,
    criteria: str = "max_violations",
    max_candidates: int = 0,
    config: SolverConfig = SolverConfig(),
) -> N1Report:
    base = run_power_flow(net, config=config)
    base_n_v = len(base.voltage_violations) if base and base.converged else 0
    base_n_t = len(base.thermal_violations) if base and base.converged else 0
    report = N1Report(
        case_name=base.case_name,
        base_converged=bool(base.converged),
        top_k=int(top_k),
        criteria=str(criteria),
        results=[],
        summary_text="",
    )

    if not base.converged:
        report.summary_text = "Base case did not converge; cannot run N-1 analysis."
        return report

    refs = list(iter_in_service_branches(net))
    if max_candidates and max_candidates > 0:
        refs = refs[: int(max_candidates)]

    outcomes: list[ContingencyOutcome] = []

    for ref in refs:
        set_branch_in_service(net, ref, False)
        try:
            r = run_power_flow(net, config=config)
        except Exception as e:
            r = None
            converged = False
            n_v = 0
            n_t = 0
            worst_vm = None
            worst_loading = None
            notes = f"solve exception: {type(e).__name__}: {e}"
        else:
            if r is None or not r.converged:
                converged = False
                n_v = 0
                n_t = 0
                worst_vm = None
                worst_loading = None
                notes = "not converged"
            else:
                converged = True
                n_v = len(r.voltage_violations)
                n_t = len(r.thermal_violations)
                worst_vm = min((bv.vm_pu for bv in r.bus_voltages), default=None)
                worst_loading = max((lf.loading_percent for lf in r.line_flows), default=None)
                notes = ""

        score = _score_outcome(
            converged=converged,
            n_v=n_v,
            n_t=n_t,
            worst_vm=worst_vm,
            worst_loading=worst_loading,
            criteria=str(criteria),
            v_min=float(config.v_min),
        )

        outcomes.append(
            ContingencyOutcome(
                branch_id=ref.branch_id,
                branch_type=ref.branch_type,
                from_bus=_bus_display_id(net, ref.from_bus),
                to_bus=_bus_display_id(net, ref.to_bus),
                converged=converged,
                n_voltage_violations=n_v,
                n_thermal_violations=n_t,
                delta_voltage_violations=int(n_v - base_n_v),
                delta_thermal_violations=int(n_t - base_n_t),
                worst_vm_pu=worst_vm,
                worst_loading_percent=worst_loading,
                score=float(score),
                notes=notes,
            )
        )
        set_branch_in_service(net, ref, True)

    outcomes.sort(key=lambda x: x.score, reverse=True)
    report.results = outcomes[: int(top_k)]

    if report.results:
        worst = report.results[0]
        report.summary_text = (
            f"N-1 completed over {len(outcomes)} branches. Worst outage: {worst.from_bus}-{worst.to_bus} "
            f"({worst.branch_type}), V violations={worst.n_voltage_violations} (delta={worst.delta_voltage_violations}), "
            f"thermal violations={worst.n_thermal_violations} (delta={worst.delta_thermal_violations})."
        )
    else:
        report.summary_text = "N-1 completed but no valid outcomes were produced."

    return report

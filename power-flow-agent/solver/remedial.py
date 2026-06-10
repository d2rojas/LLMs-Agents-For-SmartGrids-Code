"""Heuristic remedial action generation and apply pipeline."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Iterable
import re

import pandapower as pp

from models.schemas import RemedialAction, RemedialPlan, ViolationType
from solver.power_flow import SolverConfig, run_power_flow


@dataclass(frozen=True)
class RiskWeights:
    violation_count: float = 10000.0
    undervoltage: float = 100000.0
    overvoltage: float = 50000.0
    overload: float = 1000.0
    nonconverged: float = 1e9


def compute_risk_score(result, *, config: SolverConfig, w: RiskWeights = RiskWeights()) -> float:
    if result is None or not result.converged:
        return float(w.nonconverged)

    n_v = len(result.voltage_violations)
    n_t = len(result.thermal_violations)
    base = w.violation_count * float(n_v + n_t)

    min_vm = min((bv.vm_pu for bv in result.bus_voltages), default=10.0)
    max_vm = max((bv.vm_pu for bv in result.bus_voltages), default=0.0)
    max_loading = max((lf.loading_percent for lf in result.line_flows), default=0.0)

    under = max(0.0, float(config.v_min) - float(min_vm))
    over = max(0.0, float(max_vm) - float(config.v_max))
    overload = max(0.0, float(max_loading) - 100.0)

    return float(base + w.undervoltage * under + w.overvoltage * over + w.overload * overload)


def _parse_bus_name_to_id(name: object) -> int | None:
    if name is None:
        return None
    s = str(name).strip()
    if not s:
        return None
    if re.fullmatch(r"[-+]?\d+", s):
        return int(s)
    return None


def _bus_display_id(net: Any, bus_idx: int) -> int:
    try:
        parsed = _parse_bus_name_to_id(net.bus.at[bus_idx, "name"])
        if parsed is not None:
            return int(parsed)
    except Exception:
        pass
    return int(bus_idx) + 1


def _resolve_bus_index(net: Any, bus_id: int) -> int:
    if "name" in net.bus.columns:
        matches = net.bus.index[net.bus["name"].astype(str) == str(bus_id)].tolist()
        if matches:
            return int(matches[0])
        for idx, name in net.bus["name"].items():
            parsed = _parse_bus_name_to_id(name)
            if parsed is not None and int(parsed) == int(bus_id):
                return int(idx)

    for idx in net.bus.index.tolist():
        if int(_bus_display_id(net, int(idx))) == int(bus_id):
            return int(idx)

    if bus_id in net.bus.index:
        return int(bus_id)
    raise ValueError(f"Invalid bus_id: {bus_id}")


def _iter_neighbors(net: Any, bus_idx: int) -> Iterable[int]:
    if hasattr(net, "line"):
        for _, r in net.line.iterrows():
            a, b = int(r["from_bus"]), int(r["to_bus"])
            if a == bus_idx:
                yield b
            elif b == bus_idx:
                yield a
    if hasattr(net, "trafo"):
        for _, r in net.trafo.iterrows():
            a, b = int(r["hv_bus"]), int(r["lv_bus"])
            if a == bus_idx:
                yield b
            elif b == bus_idx:
                yield a


def _apply_shed_load(net: Any, bus_idx: int, pct: float) -> None:
    if not hasattr(net, "load") or len(net.load) == 0:
        return
    mask = net.load["bus"] == int(bus_idx)
    if not mask.any():
        return
    factor = max(0.0, 1.0 - float(pct))
    net.load.loc[mask, "p_mw"] = net.load.loc[mask, "p_mw"].astype(float) * factor
    if "q_mvar" in net.load.columns:
        net.load.loc[mask, "q_mvar"] = net.load.loc[mask, "q_mvar"].astype(float) * factor


def _apply_adjust_gen_vm(net: Any, bus_idx: int, delta: float) -> bool:
    changed = False
    if hasattr(net, "gen") and len(net.gen) > 0:
        mask = net.gen["bus"] == int(bus_idx)
        if mask.any() and "vm_pu" in net.gen.columns:
            net.gen.loc[mask, "vm_pu"] = net.gen.loc[mask, "vm_pu"].astype(float) + float(delta)
            changed = True
    return changed


def _apply_adjust_ext_grid_vm(net: Any, bus_idx: int, delta: float) -> bool:
    changed = False
    if hasattr(net, "ext_grid") and len(net.ext_grid) > 0:
        mask = net.ext_grid["bus"] == int(bus_idx)
        if mask.any() and "vm_pu" in net.ext_grid.columns:
            net.ext_grid.loc[mask, "vm_pu"] = net.ext_grid.loc[mask, "vm_pu"].astype(float) + float(delta)
            changed = True
    return changed


def recommend_remedial_actions(
    net: Any,
    base_result,
    *,
    config: SolverConfig,
    max_actions: int = 5,
    allow_load_shed: bool = True,
    allow_voltage_control: bool = True,
    weights: RiskWeights = RiskWeights(),
) -> RemedialPlan:
    base_risk = compute_risk_score(base_result, config=config, w=weights)
    plan = RemedialPlan(case_name=base_result.case_name, base_risk=float(base_risk), actions=[], summary_text="")

    if base_result is None or not base_result.converged:
        plan.summary_text = "Base case did not converge; cannot generate reliable remedial actions."
        return plan

    candidates: list[tuple[str, str, dict, Any]] = []

    if base_result.voltage_violations:
        # Separate undervoltage and overvoltage violation buses
        under_buses = sorted(
            [bv for bv in base_result.voltage_violations
             if bv.violation_type == ViolationType.UNDERVOLTAGE
             or (bv.violation_type is None and bv.vm_pu < float(config.v_min))],
            key=lambda x: x.vm_pu,
        )
        over_buses = sorted(
            [bv for bv in base_result.voltage_violations
             if bv.violation_type == ViolationType.OVERVOLTAGE
             or (bv.violation_type is None and bv.vm_pu > float(config.v_max))],
            key=lambda x: x.vm_pu, reverse=True,
        )

        # Handle top-3 worst undervoltage buses (not just the single worst)
        for bv in under_buses[:3]:
            worst_bus_id = int(bv.bus_id)
            worst_idx = _resolve_bus_index(net, worst_bus_id)

            if allow_load_shed:
                for pct in (0.05, 0.10, 0.20):
                    candidates.append((
                        "shed_load",
                        f"Shed {int(pct * 100)}% load at bus {worst_bus_id} (undervoltage)",
                        {"bus_id": worst_bus_id, "pct": pct, "reason": "undervoltage"},
                        ("shed", worst_idx, pct),
                    ))
                for nb in list(_iter_neighbors(net, worst_idx))[:3]:
                    nb_id = _bus_display_id(net, nb)
                    for pct in (0.05, 0.10):
                        candidates.append((
                            "shed_load",
                            f"Shed {int(pct * 100)}% load at neighbor bus {nb_id} (undervoltage)",
                            {"bus_id": int(nb_id), "pct": pct, "reason": "undervoltage"},
                            ("shed", int(nb), pct),
                        ))

            if allow_voltage_control:
                for target_idx in [worst_idx] + list(_iter_neighbors(net, worst_idx))[:3]:
                    for delta in (0.01, 0.02):
                        target_bus = int(_bus_display_id(net, target_idx))
                        candidates.append((
                            "adjust_gen_vm",
                            f"Increase generator VM at bus {target_bus} by +{delta:.2f} p.u.",
                            {"bus_id": target_bus, "delta": delta, "reason": "undervoltage"},
                            ("gen_vm", int(target_idx), delta),
                        ))
                        candidates.append((
                            "adjust_ext_grid_vm",
                            f"Increase ext_grid VM at bus {target_bus} by +{delta:.2f} p.u.",
                            {"bus_id": target_bus, "delta": delta, "reason": "undervoltage"},
                            ("ext_vm", int(target_idx), delta),
                        ))

        # Handle top-3 worst overvoltage buses (NOT elif -- both types must be handled)
        for bv in over_buses[:3]:
            worst_bus_id = int(bv.bus_id)
            worst_idx = _resolve_bus_index(net, worst_bus_id)

            if allow_voltage_control:
                for target_idx in [worst_idx] + list(_iter_neighbors(net, worst_idx))[:3]:
                    for delta in (-0.01, -0.02):
                        target_bus = int(_bus_display_id(net, target_idx))
                        candidates.append((
                            "adjust_gen_vm",
                            f"Decrease generator VM at bus {target_bus} by {delta:.2f} p.u.",
                            {"bus_id": target_bus, "delta": delta, "reason": "overvoltage"},
                            ("gen_vm", int(target_idx), delta),
                        ))
                        candidates.append((
                            "adjust_ext_grid_vm",
                            f"Decrease ext_grid VM at bus {target_bus} by {delta:.2f} p.u.",
                            {"bus_id": target_bus, "delta": delta, "reason": "overvoltage"},
                            ("ext_vm", int(target_idx), delta),
                        ))

    # Handle top-3 worst thermal violations (not just the single worst)
    if base_result.thermal_violations and allow_load_shed:
        worst_thermals = sorted(
            base_result.thermal_violations,
            key=lambda x: x.loading_percent, reverse=True,
        )
        for lf in worst_thermals[:3]:
            for bus_id in (int(lf.from_bus), int(lf.to_bus)):
                idx = _resolve_bus_index(net, bus_id)
                for pct in (0.05, 0.10, 0.20):
                    candidates.append((
                        "shed_load",
                        f"Shed {int(pct * 100)}% load at bus {bus_id} (thermal overload)",
                        {"bus_id": bus_id, "pct": pct, "reason": "thermal_overload"},
                        ("shed", idx, pct),
                    ))

    seen = set()
    uniq: list[tuple[str, str, dict, Any]] = []
    for a, d, p, fn in candidates:
        key = (a, tuple(sorted(p.items())))
        if key not in seen:
            seen.add(key)
            uniq.append((a, d, p, fn))

    scored: list[RemedialAction] = []
    for action, desc, params, op in uniq[:80]:
        net2 = copy.deepcopy(net)
        try:
            kind = op[0]
            if kind == "shed":
                _apply_shed_load(net2, op[1], op[2])
            elif kind == "gen_vm":
                if not _apply_adjust_gen_vm(net2, op[1], op[2]):
                    continue
            elif kind == "ext_vm":
                if not _apply_adjust_ext_grid_vm(net2, op[1], op[2]):
                    continue
            else:
                continue

            r2 = run_power_flow(net2, config=config)
        except Exception:
            continue

        risk2 = compute_risk_score(r2, config=config, w=weights)
        reduction = float(base_risk - risk2)
        scored.append(
            RemedialAction(
                action=action,
                description=desc,
                parameters=params,
                predicted_risk=float(risk2),
                risk_reduction=float(reduction),
                preview_result=r2,
            )
        )

    scored.sort(key=lambda x: x.risk_reduction, reverse=True)
    plan.actions = scored[: int(max_actions)]

    if plan.actions:
        best = plan.actions[0]
        plan.summary_text = (
            f"Generated {len(plan.actions)} remedial actions. Best: {best.description}; "
            f"risk reduction {best.risk_reduction:.2f}."
        )
    else:
        plan.summary_text = "No applicable remedial action found."

    return plan


def apply_remedial_action_inplace(
    net: Any,
    action: RemedialAction,
    *,
    config: SolverConfig,
) -> Any:
    """Apply a remedial action to *net* **in-place** and re-run power flow.

    .. warning::
        The caller MUST push an undo snapshot **before** calling this function.
        If the power flow fails after network modification the net state is left
        as-is (modified but without valid results).  Use the undo snapshot to
        restore the previous state in that case.
    """
    if net is None:
        raise ValueError("net cannot be None")
    if action is None:
        raise ValueError("action cannot be None")

    params = action.parameters or {}
    a = str(action.action)

    if a == "shed_load":
        bus_id = int(params.get("bus_id"))
        pct = float(params.get("pct"))
        bus_idx = _resolve_bus_index(net, bus_id)
        _apply_shed_load(net, bus_idx, pct)

    elif a == "adjust_gen_vm":
        bus_id = int(params.get("bus_id"))
        delta = float(params.get("delta"))
        bus_idx = _resolve_bus_index(net, bus_id)
        if not _apply_adjust_gen_vm(net, bus_idx, delta):
            raise ValueError(f"No adjustable gen.vm_pu at bus {bus_id}")

    elif a == "adjust_ext_grid_vm":
        bus_id = int(params.get("bus_id"))
        delta = float(params.get("delta"))
        bus_idx = _resolve_bus_index(net, bus_id)
        if not _apply_adjust_ext_grid_vm(net, bus_idx, delta):
            raise ValueError(f"No adjustable ext_grid.vm_pu at bus {bus_id}")

    else:
        raise ValueError(f"Unsupported remedial action: {a}")

    return run_power_flow(net, config=config)

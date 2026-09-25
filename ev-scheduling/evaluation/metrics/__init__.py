"""Evaluation metrics: cost, cost gap, unmet energy, peak load, violations, FR.

This module owns the *task utility* columns of the results table: Cost, Gap,
Unmet and the per-day inputs of Solved, plus FR (the share of days with no hard
violation). Names follow ``power-flow-agent/benchmarks/metrics.py`` and
``scoring.py`` so both case studies report the same protocol.

The cost gap and its trap
-------------------------
``gap = (cost - cost_star) / cost_star`` in per cent, where ``cost_star`` is the
CVXPY optimum on the same structured day. A schedule that under-delivers buys a
lower cost, so a *negative* gap can mean a better schedule or simply a schedule
that did not charge the cars. The gap is therefore only meaningful read together
with unmet energy, and ``cost_gap`` reports the pair: ``CostGap`` carries
``gap_pct``, ``unmet_kwh``, ``unmet_star_kwh`` and a ``comparable`` flag that is
False when the schedule leaves more energy unmet than the optimum does. The gap
is *not* silently redefined on the penalised objective, which would hide the
trade rather than report it.
"""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

import numpy as np

from config.site import TOUConfig
from constraints.checker import CheckResult
from data.format.schema import DaySessions

# Under-delivery below this is solver slop, not a real trade of energy for cost.
UNMET_TOL_KWH = 1e-3


@dataclass
class Metrics:
    """Aggregate metrics for one schedule.

    The fields after ``pct_fully_served`` are optional so that callers written
    before the results-table protocol keep working; they are populated when
    ``compute_metrics`` is given ``cost_star_usd`` and/or ``check_result``.
    """

    total_cost_usd: float
    total_unmet_kwh: float
    peak_load_kw: float
    violation_count: int
    pct_fully_served: float  # 0–100
    cost_reduction_vs_uncontrolled_pct: Optional[float] = None
    # Cost gap against the CVXPY optimum on the same day (see module docstring).
    cost_star_usd: Optional[float] = None
    cost_gap_pct: Optional[float] = None
    gap_comparable: Optional[bool] = None
    # Hard-violation view of the same day (from constraints.checker).
    no_hard_violation: Optional[bool] = None
    hard_violation_count: Optional[int] = None
    max_violation_kw: Optional[float] = None


@dataclass
class CostGap:
    """Cost gap against the optimum, reported together with unmet energy.

    Attributes:
        gap_pct: 100 * (cost - cost_star) / cost_star, or None when
            ``cost_star_usd`` is zero or negative (no meaningful denominator).
        cost_usd: Cost of the schedule under evaluation ($).
        cost_star_usd: CVXPY optimum on the same structured day ($).
        unmet_kwh: Unmet energy of the schedule under evaluation (kWh).
        unmet_star_kwh: Unmet energy of the optimum (kWh); non-zero when the
            day's demand is not fully satisfiable.
        comparable: False when the schedule leaves more energy unmet than the
            optimum by more than ``unmet_tol_kwh``. The gap is still reported,
            but a cheaper schedule that under-delivers did not beat the optimum,
            it bought the difference with energy it never delivered.
        detail: Short human-readable note on the pair.
    """

    gap_pct: Optional[float]
    cost_usd: float
    cost_star_usd: float
    unmet_kwh: float
    unmet_star_kwh: float
    comparable: bool
    detail: str


def rate(values: Iterable[Any]) -> Dict[str, Any]:
    """``{"rate", "count", "total"}`` over boolean-like values, ignoring ``None``.

    Same shape as ``benchmarks.metrics.rate`` in the power-flow case study, so
    both tables are filled from the same kind of aggregate.
    """
    vals = [bool(v) for v in values if v is not None]
    total = len(vals)
    count = sum(1 for v in vals if v)
    return {"rate": (float(count) / total) if total else None, "count": count, "total": total}


def total_cost(
    schedule: np.ndarray,
    tou: TOUConfig,
    dt_hours: float,
) -> float:
    """Total energy cost ($): sum_t c(t) * sum_i p_i(t) * dt."""
    if schedule.size == 0:
        return 0.0
    # c[t] = $/kWh at step t; total power at t = sum over sessions; cost at t = c[t] * power_t * dt
    c = np.asarray(tou.rates_per_kwh).flatten()
    n_steps = min(schedule.shape[1], len(c))
    return float(np.sum(c[:n_steps] * np.sum(schedule[:, :n_steps], axis=0) * dt_hours))


def total_unmet_kwh(schedule: np.ndarray, day: DaySessions, dt_hours: float) -> float:
    """Sum over sessions of (E_i - delivered_i). Only positive unmet counts."""
    if len(day.sessions) == 0:
        return 0.0
    total = 0.0
    for i, sess in enumerate(day.sessions):
        if i >= schedule.shape[0]:
            total += sess.energy_kwh  # no row for this session => full unmet
            continue
        delivered = np.sum(schedule[i, :]) * dt_hours  # kWh = sum_t p[i,t] * dt
        total += max(0.0, sess.energy_kwh - delivered)
    return total


def peak_load_kw(schedule: np.ndarray) -> float:
    """Peak facility load (kW): max over time of (sum of power over all sessions)."""
    if schedule.size == 0:
        return 0.0
    # Sum over axis=0 gives total power at each time step; max over those
    return float(np.max(np.sum(schedule, axis=0)))


def pct_fully_served(schedule: np.ndarray, day: DaySessions, dt_hours: float) -> float:
    """Percentage of sessions that received at least their requested energy (0–100)."""
    if len(day.sessions) == 0:
        return 0.0
    tol = 1e-6  # small tolerance for numerical comparison
    count = 0
    for i, sess in enumerate(day.sessions):
        if i >= schedule.shape[0]:
            continue
        delivered = np.sum(schedule[i, :]) * dt_hours
        if delivered >= sess.energy_kwh - tol:
            count += 1
    return 100.0 * count / len(day.sessions)


def cost_gap(
    cost_usd: float,
    cost_star_usd: float,
    *,
    unmet_kwh: float,
    unmet_star_kwh: float = 0.0,
    unmet_tol_kwh: float = UNMET_TOL_KWH,
) -> CostGap:
    """Cost gap against the optimum, paired with the unmet energy that explains it.

    Args:
        cost_usd: Energy cost of the schedule under evaluation ($).
        cost_star_usd: CVXPY optimum cost on the same structured day ($).
        unmet_kwh: Unmet energy of the schedule under evaluation (kWh).
        unmet_star_kwh: Unmet energy of the optimum (kWh). Non-zero on days whose
            demand cannot be met inside the site cap; the comparison is against
            this, not against zero.
        unmet_tol_kwh: Under-delivery below this counts as solver slop.

    Returns:
        CostGap with ``gap_pct`` (None when ``cost_star_usd <= 0``) and
        ``comparable`` False when the schedule under-delivers relative to the
        optimum. Callers must report the pair; ``gap_pct`` alone is not a
        statement about schedule quality (see the module docstring).
    """
    extra_unmet = float(unmet_kwh) - float(unmet_star_kwh)
    comparable = extra_unmet <= unmet_tol_kwh
    if cost_star_usd is None or cost_star_usd <= 0:
        return CostGap(
            gap_pct=None,
            cost_usd=float(cost_usd),
            cost_star_usd=float(cost_star_usd or 0.0),
            unmet_kwh=float(unmet_kwh),
            unmet_star_kwh=float(unmet_star_kwh),
            comparable=comparable,
            detail="no optimum cost to compare against (cost_star <= 0)",
        )
    gap_pct = 100.0 * (float(cost_usd) - float(cost_star_usd)) / float(cost_star_usd)
    detail = (
        f"gap {gap_pct:+.2f}% with {unmet_kwh:.3f} kWh unmet vs {unmet_star_kwh:.3f} kWh at the optimum"
        if comparable
        else (
            f"gap {gap_pct:+.2f}% is not comparable: the schedule leaves {extra_unmet:.3f} kWh "
            "more energy unmet than the optimum, which is what makes it cheaper"
        )
    )
    return CostGap(
        gap_pct=gap_pct,
        cost_usd=float(cost_usd),
        cost_star_usd=float(cost_star_usd),
        unmet_kwh=float(unmet_kwh),
        unmet_star_kwh=float(unmet_star_kwh),
        comparable=comparable,
        detail=detail,
    )


def feasible_rate(results: Iterable[Any]) -> Dict[str, Any]:
    """FR: share of days with no hard violation, as ``{"rate", "count", "total"}``.

    Args:
        results: Per-day ``CheckResult`` objects, or booleans already meaning
            "no hard violation". Soft (``energy``) violations never count here:
            a day that under-delivers but breaks no hard constraint is still
            feasible in the FR sense.

    Returns:
        ``rate`` is a fraction in [0, 1] (multiply by 100 for the table column)
        and is None when ``results`` is empty.
    """
    flags: List[Optional[bool]] = []
    for r in results:
        if isinstance(r, CheckResult):
            flags.append(r.no_hard_violation)
        elif r is None:
            flags.append(None)
        else:
            flags.append(bool(r))
    return rate(flags)


def max_violation_kw_per_day(results: Sequence[CheckResult]) -> List[float]:
    """Largest hard-violation excess per day, in kW (0.0 on days with none)."""
    return [r.max_violation_kw for r in results]


def charge_asap_schedule(day: DaySessions, site_p_max: float) -> np.ndarray:
    """Uncontrolled baseline: each session charges at max rate from arrival until E_i met.
    Used to compute cost and peak for 'charge-asap' so we can report % cost reduction.
    """
    n_sessions = len(day.sessions)
    n_steps = day.n_steps
    dt = day.dt_hours
    schedule = np.zeros((n_sessions, n_steps))
    for i, sess in enumerate(day.sessions):
        remaining = sess.energy_kwh
        # Charge at max rate in each step until requested energy is reached
        for t in range(sess.arrival_idx, min(sess.departure_idx, n_steps)):
            if remaining <= 0:
                break
            power = min(sess.max_power_kw, remaining / dt)  # cap by remaining energy in this step
            schedule[i, t] = power
            remaining -= power * dt
    return schedule


def compute_metrics(
    schedule: np.ndarray,
    day: DaySessions,
    tou: TOUConfig,
    dt_hours: float,
    violation_count: int = 0,
    uncontrolled_cost_usd: Optional[float] = None,
    *,
    cost_star_usd: Optional[float] = None,
    unmet_star_kwh: float = 0.0,
    check_result: Optional[CheckResult] = None,
) -> Metrics:
    """Compute all metrics for one day.

    Args:
        schedule: Power schedule (n_sessions, n_steps) in kW.
        day: Sessions and horizon.
        tou: TOU rates.
        dt_hours: Step duration in hours.
        violation_count: Total violation count; when 0 and ``check_result`` is
            given, it is taken from ``check_result`` instead.
        uncontrolled_cost_usd: Cost of the charge-asap baseline, for
            ``cost_reduction_vs_uncontrolled_pct``.
        cost_star_usd: CVXPY optimum cost on the same structured day. Given it,
            ``cost_gap_pct`` and ``gap_comparable`` are filled; without it they
            stay None, since a gap has no meaning without the optimum.
        unmet_star_kwh: Unmet energy at that optimum (kWh).
        check_result: ``constraints.checker.check`` output for this schedule,
            used for the hard-violation fields (FR and max violation).

    Returns:
        Metrics. ``cost_gap_pct`` must be read together with ``total_unmet_kwh``
        and ``gap_comparable``: a schedule that under-delivers buys a lower cost.
    """
    total_cost_usd = total_cost(schedule, tou, dt_hours)
    total_unmet = total_unmet_kwh(schedule, day, dt_hours)
    peak = peak_load_kw(schedule)
    pct = pct_fully_served(schedule, day, dt_hours)

    # Optional: % reduction vs uncontrolled (charge-asap) baseline
    cost_reduction_pct = None
    if uncontrolled_cost_usd is not None and uncontrolled_cost_usd > 0:
        cost_reduction_pct = 100.0 * (uncontrolled_cost_usd - total_cost_usd) / uncontrolled_cost_usd

    gap: Optional[CostGap] = None
    if cost_star_usd is not None:
        gap = cost_gap(
            total_cost_usd,
            cost_star_usd,
            unmet_kwh=total_unmet,
            unmet_star_kwh=unmet_star_kwh,
        )

    if check_result is not None and not violation_count:
        violation_count = len(check_result.violations)

    return Metrics(
        total_cost_usd=total_cost_usd,
        total_unmet_kwh=total_unmet,
        peak_load_kw=peak,
        violation_count=violation_count,
        pct_fully_served=pct,
        cost_reduction_vs_uncontrolled_pct=cost_reduction_pct,
        cost_star_usd=(float(cost_star_usd) if cost_star_usd is not None else None),
        cost_gap_pct=(gap.gap_pct if gap is not None else None),
        gap_comparable=(gap.comparable if gap is not None else None),
        no_hard_violation=(check_result.no_hard_violation if check_result is not None else None),
        hard_violation_count=(check_result.n_hard_violations if check_result is not None else None),
        max_violation_kw=(check_result.max_violation_kw if check_result is not None else None),
    )

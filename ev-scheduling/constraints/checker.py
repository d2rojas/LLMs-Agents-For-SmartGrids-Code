"""Constraint checker: feasibility of a schedule against sessions and site config.

Hard and soft violations
------------------------
``availability``, ``per_charger`` and ``site_cap`` are **hard** violations: the
schedule is physically or contractually impossible, so a result carrying one must
never be surfaced as valid. ``energy`` is **not** hard. The LP in
``optimization/solver.py`` keeps the unmet energy ``u_i`` as a penalised slack in
the objective, so under-delivery is a cost the formulation is allowed to pay, not
a broken constraint. Over-delivery is recorded under the same ``energy`` kind and
is not hard either (it wastes money, it breaks nothing).

``CheckResult.feasible`` keeps its original meaning, *no violation of any kind*,
so it is False as soon as one session is under-served. Existing callers
(``agent/llm_agent.py``, ``web/app.py``, ``scripts/``) read it with that meaning.
The hard-violation notion the results table needs is exposed separately:
``CheckResult.no_hard_violation`` feeds FR (the share of days with no hard
violation) and ``CheckResult.max_violation_kw`` is the largest hard-violation
excess on the day, in kW.
"""

from dataclasses import dataclass
from typing import FrozenSet, Iterable, List, Optional

import numpy as np

from config.site import SiteConfig
from data.format.schema import DaySessions

# Tolerance for numerical comparisons. CVXPY solvers typically achieve ~1e-6–1e-8;
# using 1e-5 here avoids flagging tiny solver slop as violations.
DEFAULT_TOL = 1e-5

# Kinds that make a schedule impossible to run. The complement (``energy``) is the
# penalised term of the objective, not a constraint breach; see the module docstring.
HARD_VIOLATION_KINDS: FrozenSet[str] = frozenset({"availability", "per_charger", "site_cap"})
SOFT_VIOLATION_KINDS: FrozenSet[str] = frozenset({"energy"})


@dataclass
class Violation:
    """Single constraint violation.

    Attributes:
        kind: "availability" | "per_charger" | "site_cap" | "energy".
        session_id: Session the violation belongs to; None for site-level ones.
        time_step: Step index where it occurs; None for per-session energy ones.
        message: Formatted description (human-readable only, never parsed).
        magnitude: Size of the excess in the violation's own unit, always
            non-negative. kW for the hard kinds (power above the per-charger or
            site limit, power charged outside the window, or power below zero);
            kWh for ``energy`` (unmet, or over-delivered, energy). This is the
            machine-readable counterpart of the number inside ``message``: the
            largest violation on a day is only derivable from this field.
    """

    kind: str  # "availability" | "per_charger" | "site_cap" | "energy"
    session_id: Optional[str]
    time_step: Optional[int]
    message: str
    magnitude: float = 0.0


def is_hard_violation(violation: Violation) -> bool:
    """Whether this violation makes the schedule invalid rather than merely costly."""
    return violation.kind in HARD_VIOLATION_KINDS


def hard_violations(violations: Iterable[Violation]) -> List[Violation]:
    """The subset of ``violations`` whose kind is in HARD_VIOLATION_KINDS."""
    return [v for v in violations if is_hard_violation(v)]


def max_violation_kw(violations: Iterable[Violation]) -> float:
    """Largest hard-violation excess, in kW; 0.0 when there is no hard violation.

    Soft (``energy``) violations are skipped: their magnitude is in kWh and must
    not leak into a kW figure.
    """
    hard = hard_violations(violations)
    return max((float(v.magnitude) for v in hard), default=0.0)


@dataclass
class CheckResult:
    """Result of checking a schedule.

    Attributes:
        feasible: True iff there is no violation of *any* kind, soft ones
            included. Unchanged from the original meaning; use
            ``no_hard_violation`` for the results table.
        violations: Every violation found, in detection order.
        unmet_energy_kwh: Per-session unmet energy (kWh), same order as
            ``day.sessions``.
        peak_load_kw: Maximum total power over the horizon (kW).
    """

    feasible: bool
    violations: List[Violation]
    unmet_energy_kwh: np.ndarray  # per session
    peak_load_kw: float

    @property
    def n_hard_violations(self) -> int:
        """Number of availability / per_charger / site_cap violations."""
        return len(hard_violations(self.violations))

    @property
    def no_hard_violation(self) -> bool:
        """True when the schedule is runnable: no hard violation (unmet energy allowed).

        This is the per-day term behind FR in the results table.
        """
        return self.n_hard_violations == 0

    @property
    def max_violation_kw(self) -> float:
        """Largest hard-violation excess on this day, in kW (0.0 when there is none)."""
        # Resolves to the module-level function above, not to this property.
        return max_violation_kw(self.violations)

    @property
    def total_unmet_kwh(self) -> float:
        """Total under-delivered energy over the day (kWh)."""
        if self.unmet_energy_kwh is None or len(self.unmet_energy_kwh) == 0:
            return 0.0
        return float(np.sum(self.unmet_energy_kwh))


def check(
    schedule: np.ndarray,
    day: DaySessions,
    site: SiteConfig,
    dt_hours: Optional[float] = None,
    tol: Optional[float] = None,
) -> CheckResult:
    """Check schedule against availability, per-charger limits, site cap, and energy.

    Args:
        schedule: Shape (n_sessions, n_steps), power in kW. Order must match day.sessions.
        day: DaySessions with sessions and n_steps, dt_hours.
        site: SiteConfig with P_max and n_steps.
        dt_hours: Override for step duration; defaults to day.dt_hours.
        tol: Numerical tolerance for comparisons; defaults to DEFAULT_TOL.

    Returns:
        CheckResult with feasible, violations (each carrying its magnitude),
        per-session unmet energy, and peak load.
    """
    TOL = tol if tol is not None else DEFAULT_TOL
    dt = dt_hours if dt_hours is not None else day.dt_hours
    violations: List[Violation] = []
    n_steps = day.n_steps
    n_sessions = len(day.sessions)
    total_power = np.zeros(n_steps)   # sum of p[i,t] over i at each t (for site cap check)
    unmet_energy_kwh = np.zeros(n_sessions)  # per-session unmet = max(0, requested - delivered)

    # --- Pass over each session and each time step: check availability, per-charger, and energy ---
    for i in range(n_sessions):
        s = day.sessions[i]
        delivered = 0.0  # accumulated energy delivered to this session (kWh)
        for t in range(n_steps):
            p = schedule[i, t]
            total_power[t] += p   # accumulate for site cap check later
            delivered += p * dt   # energy (kW * h) delivered in this step

            # --- Availability: p must be 0 outside [arrival_idx, departure_idx) ---
            if t < s.arrival_idx or t >= s.departure_idx:
                if abs(p) > TOL:
                    violations.append(
                        Violation(
                            kind="availability",
                            session_id=s.session_id,
                            time_step=t,
                            message=f"Charging outside window: p={p:.6f} kW at t={t} (allowed [a,d)=[{s.arrival_idx},{s.departure_idx}))",
                            magnitude=float(abs(p)),  # kW charged where 0 kW is allowed
                        )
                    )
            # --- Per-charger: 0 <= p[i,t] <= max_power_kw ---
            if p < -TOL:
                violations.append(
                    Violation(
                        kind="per_charger",
                        session_id=s.session_id,
                        time_step=t,
                        message=f"Negative power: p={p:.6f} kW",
                        magnitude=float(-p),  # kW below the 0 kW floor
                    )
                )
            elif p > s.max_power_kw + TOL:
                violations.append(
                    Violation(
                        kind="per_charger",
                        session_id=s.session_id,
                        time_step=t,
                        message=f"Power p={p:.6f} kW exceeds max_power_kw={s.max_power_kw}",
                        magnitude=float(p - s.max_power_kw),  # kW above the charger limit
                    )
                )

        # --- Energy: delivered should equal requested (within TOL); record unmet ---
        unmet_i = s.energy_kwh - delivered
        unmet_energy_kwh[i] = max(0.0, unmet_i)
        if unmet_i < -TOL:
            violations.append(
                Violation(
                    kind="energy",
                    session_id=s.session_id,
                    time_step=None,
                    message=f"Over-delivered: delivered={delivered:.4f} kWh, requested={s.energy_kwh} kWh",
                    magnitude=float(-unmet_i),  # kWh delivered beyond the request
                )
            )
        elif unmet_i > TOL:
            violations.append(
                Violation(
                    kind="energy",
                    session_id=s.session_id,
                    time_step=None,
                    message=f"Under-delivered: delivered={delivered:.4f} kWh, requested={s.energy_kwh} kWh, unmet={unmet_i:.4f}",
                    magnitude=float(unmet_i),  # kWh still owed to the session
                )
            )

    # --- Site cap: at each t, sum_i p[i,t] must not exceed P_max(t) ---
    for t in range(n_steps):
        p_max_t = site.get_P_max_at_step(t)
        if total_power[t] > p_max_t + TOL:
            violations.append(
                Violation(
                    kind="site_cap",
                    session_id=None,
                    time_step=t,
                    message=f"Total power {total_power[t]:.4f} kW exceeds P_max={p_max_t} kW at t={t}",
                    magnitude=float(total_power[t] - p_max_t),  # kW above the site cap
                )
            )

    # --- Build result: feasible iff no violations, peak = max_t total_power[t] ---
    peak_load_kw = float(total_power.max()) if n_steps > 0 else 0.0
    feasible = len(violations) == 0
    return CheckResult(
        feasible=feasible,
        violations=violations,
        unmet_energy_kwh=unmet_energy_kwh,
        peak_load_kw=peak_load_kw,
    )

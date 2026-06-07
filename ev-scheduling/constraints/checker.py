"""Constraint checker: feasibility of a schedule against sessions and site config."""

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from config.site import SiteConfig
from data.format.schema import DaySessions

# Tolerance for numerical comparisons. CVXPY solvers typically achieve ~1e-6–1e-8;
# using 1e-5 here avoids flagging tiny solver slop as violations.
DEFAULT_TOL = 1e-5


@dataclass
class Violation:
    """Single constraint violation."""

    kind: str  # "availability" | "per_charger" | "site_cap" | "energy"
    session_id: Optional[str]
    time_step: Optional[int]
    message: str


@dataclass
class CheckResult:
    """Result of checking a schedule."""

    feasible: bool
    violations: List[Violation]
    unmet_energy_kwh: np.ndarray  # per session
    peak_load_kw: float


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
        CheckResult with feasible, violations, per-session unmet energy, and peak load.
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
                    )
                )
            elif p > s.max_power_kw + TOL:
                violations.append(
                    Violation(
                        kind="per_charger",
                        session_id=s.session_id,
                        time_step=t,
                        message=f"Power p={p:.6f} kW exceeds max_power_kw={s.max_power_kw}",
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
                )
            )
        elif unmet_i > TOL:
            violations.append(
                Violation(
                    kind="energy",
                    session_id=s.session_id,
                    time_step=None,
                    message=f"Under-delivered: delivered={delivered:.4f} kWh, requested={s.energy_kwh} kWh, unmet={unmet_i:.4f}",
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

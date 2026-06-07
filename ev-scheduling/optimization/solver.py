"""CVXPY cost-minimization solver: decision variables p_i(t), objective, constraints.

Solver tolerances: CVXPY uses the default solver (e.g. ECOS/SCS) with its default
feasibility tolerances (typically ~1e-8). The constraint checker uses DEFAULT_TOL (1e-5)
so small numerical slop from the solver is not reported as violations.
"""

from dataclasses import dataclass
from typing import Optional

import cvxpy as cp
import numpy as np

from config.site import SiteConfig, TOUConfig
from data.format.schema import DaySessions


@dataclass
class SolveResult:
    """Result of optimization: schedule, cost, unmet, peak, and status."""

    schedule: np.ndarray  # (n_sessions, n_steps) in kW
    total_cost_usd: float
    unmet_energy_kwh: np.ndarray  # per session
    peak_load_kw: float
    success: bool
    message: Optional[str] = None


def solve(
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
    penalty_unmet: float = 1e6,
) -> SolveResult:
    """Formulate and solve min sum_t c(t) * sum_i p_i(t)*dt + M * sum_i u_i; report peak.

    Args:
        day: Sessions and horizon (n_steps, dt_hours).
        site: P_max, n_steps, dt_hours.
        tou: rates_per_kwh for each step.
        penalty_unmet: M in objective ($/kWh penalty for slack u_i).

    Returns:
        SolveResult with schedule, cost, unmet, peak, and success flag.
    """
    # --- 1. Extract problem dimensions and TOU rates ---
    n_sessions = len(day.sessions)
    n_steps = day.n_steps
    dt = day.dt_hours  # duration of one time step in hours (e.g. 0.25 for 15 min)
    c = np.asarray(tou.rates_per_kwh).flatten()  # cost per kWh at each time step ($/kWh)

    # --- 2. Handle empty problem (no sessions or no time steps) ---
    if n_sessions == 0 or n_steps == 0:
        return SolveResult(
            schedule=np.zeros((n_sessions, n_steps)),
            total_cost_usd=0.0,
            unmet_energy_kwh=np.zeros(n_sessions),
            peak_load_kw=0.0,
            success=True,
            message=None,
        )

    # --- 3. Define decision variables ---
    # p[i,t] = power (kW) delivered to session i at time step t
    # u[i]   = slack/unmet energy (kWh) for session i (allows infeasible demand to be penalized)
    p = cp.Variable((n_sessions, n_steps), nonneg=True)
    u = cp.Variable(n_sessions, nonneg=True)

    # --- 4. Build objective: minimize energy cost + penalty for unmet energy ---
    # Energy cost = sum over t of (rate[t] * total_power_at_t * dt)
    cost_energy = cp.sum(cp.multiply(c, cp.sum(p, axis=0)) * dt)
    cost_unmet = penalty_unmet * cp.sum(u)
    objective = cp.Minimize(cost_energy + cost_unmet)

    constraints = []

    # --- 5. Availability: no charging outside [arrival_idx, departure_idx) ---
    for i, sess in enumerate(day.sessions):
        for t in range(n_steps):
            if t < sess.arrival_idx or t >= sess.departure_idx:
                constraints.append(p[i, t] == 0)
            else:
                # --- 6. Per-charger limit: p[i,t] <= max_power_kw for session i ---
                constraints.append(p[i, t] <= sess.max_power_kw)

    # --- 7. Site power cap: total power at each t must not exceed P_max(t) ---
    for t in range(n_steps):
        constraints.append(cp.sum(p[:, t]) <= site.get_P_max_at_step(t))

    # --- 8. Energy balance: delivered + unmet = requested for each session ---
    # delivered_i = sum_t p[i,t] * dt; constraint: delivered_i + u[i] == energy_kwh_i
    for i, sess in enumerate(day.sessions):
        delivered = cp.sum(p[i, :]) * dt
        constraints.append(delivered + u[i] == sess.energy_kwh)

    # --- 9. Solve the problem ---
    prob = cp.Problem(objective, constraints)
    try:
        prob.solve()
    except Exception as e:
        return SolveResult(
            schedule=np.zeros((n_sessions, n_steps)),
            total_cost_usd=0.0,
            unmet_energy_kwh=np.zeros(n_sessions),
            peak_load_kw=0.0,
            success=False,
            message=str(e),
        )

    # --- 10. Check solver status (optimal or optimal with small inaccuracy) ---
    if prob.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        return SolveResult(
            schedule=np.zeros((n_sessions, n_steps)),
            total_cost_usd=0.0,
            unmet_energy_kwh=np.zeros(n_sessions),
            peak_load_kw=0.0,
            success=False,
            message=prob.status,
        )

    # --- 11. Extract solution and compute reported cost and peak ---
    # Clamp to nonnegative in case of tiny numerical negatives
    schedule = np.maximum(p.value, 0.0)
    unmet = np.maximum(u.value, 0.0)
    total_cost_usd = float(np.sum(c * np.sum(schedule, axis=0) * dt))
    peak_load_kw = float(np.max(np.sum(schedule, axis=0)))  # max over t of sum_i p[i,t]

    return SolveResult(
        schedule=schedule,
        total_cost_usd=total_cost_usd,
        unmet_energy_kwh=unmet,
        peak_load_kw=peak_load_kw,
        success=True,
        message=None,
    )

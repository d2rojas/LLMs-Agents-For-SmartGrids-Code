"""Optimize: call optimization solver; return schedule, cost, peak, unmet.

Thin wrapper around the CVXPY solver from optimization.solver. This module
exists so the agent can call the optimizer through a consistent interface,
and so future versions can add pre/post-processing (e.g. objective selection,
solver parameter tuning) without changing the agent pipeline.
"""

from config.site import SiteConfig, TOUConfig
from data.format.schema import DaySessions
from optimization.solver import SolveResult, solve


def optimize(
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
    penalty_unmet: float = 1e6,
) -> SolveResult:
    """Call the optimization solver and return the result.

    This is a thin wrapper around optimization.solver.solve. It exists so the
    agent pipeline has a consistent interface and so future versions can add
    objective selection or solver parameter tuning.

    Args:
        day: DaySessions with sessions and horizon.
        site: SiteConfig with power cap.
        tou: TOUConfig with TOU rates.
        penalty_unmet: Penalty ($/kWh) for unmet energy in the objective.

    Returns:
        SolveResult with schedule, total_cost_usd, unmet_energy_kwh, peak_load_kw,
        success flag, and optional message.
    """
    return solve(day, site, tou, penalty_unmet)

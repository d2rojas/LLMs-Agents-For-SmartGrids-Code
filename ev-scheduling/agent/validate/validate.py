"""Validate: run constraint checker on schedule; return feasibility and metrics.

Thin wrapper around constraints.checker.check. This module exists so the agent
can validate schedules through a consistent interface, and so future versions
can add custom validation logic or tolerance tuning.
"""

import numpy as np

from config.site import SiteConfig
from constraints.checker import CheckResult, check
from data.format.schema import DaySessions


def validate(
    schedule: np.ndarray,
    day: DaySessions,
    site: SiteConfig,
) -> CheckResult:
    """Run the constraint checker on a schedule.

    This is a thin wrapper around constraints.checker.check. It validates
    availability, per-charger limits, site power cap, and energy delivery.

    Args:
        schedule: Power schedule array of shape (n_sessions, n_steps) in kW.
        day: DaySessions with sessions and horizon.
        site: SiteConfig with power cap.

    Returns:
        CheckResult with feasible flag, list of violations, per-session unmet
        energy, and peak load.
    """
    return check(schedule, day, site)

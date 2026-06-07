"""Plan: parse user request into objective, horizon, constraints, session params.

For v1, this is a simple pass-through that returns the inputs unchanged with
objective="minimize_cost". Future versions may use an LLM to parse the request
and extract custom objectives, constraints, or session parameters.
"""

from dataclasses import dataclass
from typing import Any, Optional

from config.site import SiteConfig, TOUConfig
from data.format.schema import DaySessions


@dataclass
class PlanResult:
    """Structured representation for the optimizer and checker.

    Attributes:
        day: DaySessions with sessions and horizon.
        site: SiteConfig with power cap and time step info.
        tou: TOUConfig with energy rates per step.
        objective: String describing the optimization objective (e.g. "minimize_cost").
        raw: Optional raw data from request parsing (e.g. LLM response for debugging).
    """

    day: DaySessions
    site: SiteConfig
    tou: TOUConfig
    objective: str  # e.g. "minimize_cost"
    raw: Optional[Any] = None


def plan(
    request: str,
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
) -> PlanResult:
    """Parse user request into a structured PlanResult for the optimizer.

    For v1, this is a simple pass-through: the request string is stored in `raw`
    but not parsed. The objective is always "minimize_cost". Future versions may
    use an LLM to extract custom objectives or constraint modifications from
    natural-language requests.

    Args:
        request: Natural-language request (e.g. "Minimize cost for this day.").
        day: DaySessions with sessions and horizon.
        site: SiteConfig with power cap.
        tou: TOUConfig with TOU rates.

    Returns:
        PlanResult with day, site, tou unchanged, objective="minimize_cost",
        and raw=request for traceability.
    """
    return PlanResult(
        day=day,
        site=site,
        tou=tou,
        objective="minimize_cost",
        raw=request,
    )

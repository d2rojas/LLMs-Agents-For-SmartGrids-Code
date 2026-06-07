"""Explain: extract schedule-derived facts; generate natural-language explanation grounded in them.

The explanation module provides two functions:
  - extract_facts: Collects numeric metrics into a ScheduleFacts dataclass.
  - generate_explanation: Converts facts into a human-readable summary.

For v1, generate_explanation uses a template string. Future versions may use
an LLM to produce more natural explanations while remaining grounded in the facts.
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class ScheduleFacts:
    """Numeric facts from the schedule for grounding the explanation.

    Attributes:
        total_cost_usd: Total energy cost in USD.
        peak_load_kw: Maximum total power draw across all sessions (kW).
        total_unmet_kwh: Sum of unmet energy across all sessions (kWh).
        cost_reduction_vs_uncontrolled_pct: Percentage cost reduction compared
            to an uncontrolled (charge-asap) baseline. None if not computed.
    """

    total_cost_usd: float
    peak_load_kw: float
    total_unmet_kwh: float
    cost_reduction_vs_uncontrolled_pct: Optional[float] = None


def extract_facts(
    schedule: np.ndarray,
    total_cost_usd: float,
    peak_load_kw: float,
    total_unmet_kwh: float,
    uncontrolled_cost_usd: Optional[float] = None,
) -> ScheduleFacts:
    """Build ScheduleFacts from computed metrics.

    Args:
        schedule: Power schedule array (not used directly, but passed for
            potential future per-session analysis).
        total_cost_usd: Total energy cost in USD.
        peak_load_kw: Peak load in kW.
        total_unmet_kwh: Total unmet energy in kWh.
        uncontrolled_cost_usd: Cost of the uncontrolled baseline (optional).
            If provided, cost_reduction_vs_uncontrolled_pct is computed.

    Returns:
        ScheduleFacts with the given metrics and optional cost reduction.
    """
    cost_reduction_pct: Optional[float] = None
    if uncontrolled_cost_usd is not None and uncontrolled_cost_usd > 0:
        cost_reduction_pct = 100.0 * (uncontrolled_cost_usd - total_cost_usd) / uncontrolled_cost_usd

    return ScheduleFacts(
        total_cost_usd=total_cost_usd,
        peak_load_kw=peak_load_kw,
        total_unmet_kwh=total_unmet_kwh,
        cost_reduction_vs_uncontrolled_pct=cost_reduction_pct,
    )


def generate_explanation(facts: ScheduleFacts, use_llm: bool = False) -> str:
    """Generate a short natural-language explanation grounded in the facts.

    For v1, this uses a simple template string. Future versions may use an LLM
    (when use_llm=True) to produce more natural explanations while remaining
    strictly grounded in the numeric facts.

    Args:
        facts: ScheduleFacts with computed metrics.
        use_llm: If True, use an LLM to generate the explanation (not implemented in v1).

    Returns:
        A human-readable summary string describing the schedule results.
    """
    # v1: template-based explanation
    parts = [
        f"Total cost: ${facts.total_cost_usd:.2f}.",
        f"Peak load: {facts.peak_load_kw:.1f} kW.",
        f"Unmet energy: {facts.total_unmet_kwh:.2f} kWh.",
    ]

    if facts.cost_reduction_vs_uncontrolled_pct is not None:
        parts.append(
            f"Cost reduction vs uncontrolled: {facts.cost_reduction_vs_uncontrolled_pct:.1f}%."
        )

    return " ".join(parts)

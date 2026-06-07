"""Faithfulness check: verify explanation claims against computed schedule statistics.

Compares numeric claims in the agent's explanation (total cost, peak load, unmet
energy, cost reduction %) to the ground-truth values computed from the schedule.
Supports (1) direct ScheduleFacts vs ScheduleFacts comparison, and (2) parsing
explanation text and comparing to ground truth (for LLM-generated explanations).

Usage (e.g. in scripts or after run_agent):
    from agent.explain.explain import extract_facts
    from evaluation.faithfulness import check_faithfulness

    # ground_truth = extract_facts(schedule, total_cost_usd, peak_load_kw, ...)
    result = check_faithfulness(agent_result.explanation, ground_truth)
    if result.faithful:
        print("Explanation is faithful to schedule metrics.")
    else:
        for c in result.claims:
            if not c.matched:
                print(f"Mismatch {c.name}: claimed {c.claimed_value} vs actual {c.actual_value}")
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

# ScheduleFacts lives in agent.explain; we use it as the canonical fact shape.
from agent.explain.explain import ScheduleFacts


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ClaimCheck:
    """Result of checking one numeric claim against ground truth.

    Attributes:
        name: Human-readable claim identifier (e.g. "total_cost_usd").
        claimed_value: Value stated in the explanation (or extracted from text).
        actual_value: Ground-truth value from schedule/metrics.
        matched: True if |claimed - actual| within tolerance.
    """

    name: str
    claimed_value: float
    actual_value: float
    matched: bool


@dataclass
class FaithfulnessResult:
    """Result of a full faithfulness check.

    Attributes:
        faithful: True iff all checked claims matched within tolerance.
        claims: Per-claim results (cost, peak, unmet, cost_reduction_pct).
        parse_failed: If True, explanation text could not be parsed; claims may be empty.
    """

    faithful: bool
    claims: List[ClaimCheck] = field(default_factory=list)
    parse_failed: bool = False


# ---------------------------------------------------------------------------
# Default tolerance
# ---------------------------------------------------------------------------

# Relative or absolute tolerance per claim type. For percentages, use absolute
# (e.g. 0.5 = 0.5% difference allowed). For cost/peak/unmet, use relative
# (e.g. 1e-2 = 1% relative error) or absolute for very small numbers.
DEFAULT_TOL_RELATIVE = 1e-2   # 1% relative for cost, peak, unmet
DEFAULT_TOL_PCT_ABSOLUTE = 0.5  # 0.5% absolute for cost_reduction_vs_uncontrolled_pct


def _values_match(
    claimed: float,
    actual: float,
    rel_tol: float = DEFAULT_TOL_RELATIVE,
    abs_tol: float = 1e-4,
) -> bool:
    """Return True if claimed is within rel_tol or abs_tol of actual."""
    if actual == 0:
        return abs(claimed) <= abs_tol
    return abs(claimed - actual) <= rel_tol * abs(actual) or abs(claimed - actual) <= abs_tol


def _pct_match(claimed: Optional[float], actual: Optional[float], abs_tol: float = DEFAULT_TOL_PCT_ABSOLUTE) -> bool:
    """Return True if claimed and actual cost-reduction % are within abs_tol."""
    if claimed is None and actual is None:
        return True
    if claimed is None or actual is None:
        return False
    return abs(claimed - actual) <= abs_tol


# ---------------------------------------------------------------------------
# Direct fact comparison
# ---------------------------------------------------------------------------


def check_faithfulness_facts(
    claimed: ScheduleFacts,
    ground_truth: ScheduleFacts,
    rel_tol: float = DEFAULT_TOL_RELATIVE,
    pct_abs_tol: float = DEFAULT_TOL_PCT_ABSOLUTE,
) -> FaithfulnessResult:
    """Compare claimed facts (e.g. from explanation) to ground-truth facts.

    Use this when you have structured claimed facts (e.g. after parsing the
    explanation or when the explainer returns facts alongside text).

    Args:
        claimed: Facts stated in or extracted from the explanation.
        ground_truth: Facts computed from the schedule (e.g. from extract_facts).
        rel_tol: Relative tolerance for cost, peak, unmet.
        pct_abs_tol: Absolute tolerance for cost_reduction_vs_uncontrolled_pct (%).

    Returns:
        FaithfulnessResult with per-claim match results and overall faithful flag.
    """
    claims: List[ClaimCheck] = []

    # Total cost
    match_cost = _values_match(claimed.total_cost_usd, ground_truth.total_cost_usd, rel_tol=rel_tol)
    claims.append(
        ClaimCheck(
            name="total_cost_usd",
            claimed_value=claimed.total_cost_usd,
            actual_value=ground_truth.total_cost_usd,
            matched=match_cost,
        )
    )

    # Peak load
    match_peak = _values_match(claimed.peak_load_kw, ground_truth.peak_load_kw, rel_tol=rel_tol)
    claims.append(
        ClaimCheck(
            name="peak_load_kw",
            claimed_value=claimed.peak_load_kw,
            actual_value=ground_truth.peak_load_kw,
            matched=match_peak,
        )
    )

    # Unmet energy
    match_unmet = _values_match(claimed.total_unmet_kwh, ground_truth.total_unmet_kwh, rel_tol=rel_tol)
    claims.append(
        ClaimCheck(
            name="total_unmet_kwh",
            claimed_value=claimed.total_unmet_kwh,
            actual_value=ground_truth.total_unmet_kwh,
            matched=match_unmet,
        )
    )

    # Cost reduction % (optional)
    match_pct = _pct_match(claimed.cost_reduction_vs_uncontrolled_pct, ground_truth.cost_reduction_vs_uncontrolled_pct, abs_tol=pct_abs_tol)
    actual_pct = ground_truth.cost_reduction_vs_uncontrolled_pct if ground_truth.cost_reduction_vs_uncontrolled_pct is not None else 0.0
    claimed_pct = claimed.cost_reduction_vs_uncontrolled_pct if claimed.cost_reduction_vs_uncontrolled_pct is not None else 0.0
    claims.append(
        ClaimCheck(
            name="cost_reduction_vs_uncontrolled_pct",
            claimed_value=claimed_pct,
            actual_value=actual_pct,
            matched=match_pct,
        )
    )

    faithful = all(c.matched for c in claims)
    return FaithfulnessResult(faithful=faithful, claims=claims, parse_failed=False)


# ---------------------------------------------------------------------------
# Parse explanation text (v1 template format)
# ---------------------------------------------------------------------------

# Patterns for the current template: "Total cost: $X.XX." "Peak load: X.X kW."
# "Unmet energy: X.XX kWh." "Cost reduction vs uncontrolled: X.X%."
# Use number-only group so trailing period is not captured ([\d.]+ would capture "111.57.").
_NUM = r"\d+\.?\d*"
_RE_COST = re.compile(r"Total cost:\s*\$?\s*(" + _NUM + r")", re.IGNORECASE)
_RE_PEAK = re.compile(r"Peak load:\s*(" + _NUM + r")\s*kW", re.IGNORECASE)
_RE_UNMET = re.compile(r"Unmet energy:\s*(" + _NUM + r")\s*kWh", re.IGNORECASE)
_RE_PCT = re.compile(r"Cost reduction vs uncontrolled:\s*(" + _NUM + r")\s*%", re.IGNORECASE)


def parse_explanation_for_facts(explanation: str) -> Optional[ScheduleFacts]:
    """Extract ScheduleFacts from explanation text.

    Supports the v1 template format from agent.explain.generate_explanation.
    For other formats (e.g. LLM-generated), extend the regexes or add a
    fallback (e.g. LLM-based extraction) in this function.

    Args:
        explanation: Natural-language explanation string.

    Returns:
        ScheduleFacts if all required numbers could be parsed; None otherwise.
    """
    if not explanation or not explanation.strip():
        return None

    cost_match = _RE_COST.search(explanation)
    peak_match = _RE_PEAK.search(explanation)
    unmet_match = _RE_UNMET.search(explanation)
    pct_match = _RE_PCT.search(explanation)

    if not (cost_match and peak_match and unmet_match):
        return None

    try:
        total_cost_usd = float(cost_match.group(1))
        peak_load_kw = float(peak_match.group(1))
        total_unmet_kwh = float(unmet_match.group(1))
        cost_reduction_pct: Optional[float] = float(pct_match.group(1)) if pct_match else None
    except (ValueError, IndexError):
        return None

    return ScheduleFacts(
        total_cost_usd=total_cost_usd,
        peak_load_kw=peak_load_kw,
        total_unmet_kwh=total_unmet_kwh,
        cost_reduction_vs_uncontrolled_pct=cost_reduction_pct,
    )


# ---------------------------------------------------------------------------
# Full check: explanation text vs ground truth
# ---------------------------------------------------------------------------


def check_faithfulness(
    explanation: str,
    ground_truth: ScheduleFacts,
    rel_tol: float = DEFAULT_TOL_RELATIVE,
    pct_abs_tol: float = DEFAULT_TOL_PCT_ABSOLUTE,
) -> FaithfulnessResult:
    """Check that the explanation's numeric claims match ground-truth facts.

    Parses the explanation text to extract claimed values, then compares them
    to the provided ground-truth ScheduleFacts (e.g. from extract_facts on the
    actual schedule).

    Args:
        explanation: Natural-language explanation from the agent.
        ground_truth: Facts computed from the schedule (same source as explanation
            in v1; use this to verify LLM-generated explanations in the future).
        rel_tol: Relative tolerance for cost, peak, unmet.
        pct_abs_tol: Absolute tolerance for cost reduction %.

    Returns:
        FaithfulnessResult. If parsing fails, parse_failed=True and faithful=False.
    """
    claimed = parse_explanation_for_facts(explanation)
    if claimed is None:
        return FaithfulnessResult(
            faithful=False,
            claims=[],
            parse_failed=True,
        )
    return check_faithfulness_facts(
        claimed,
        ground_truth,
        rel_tol=rel_tol,
        pct_abs_tol=pct_abs_tol,
    )

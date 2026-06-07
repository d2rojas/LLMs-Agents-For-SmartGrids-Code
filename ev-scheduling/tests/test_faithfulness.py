"""Unit tests for the faithfulness check: explanation claims vs ground truth."""

import pytest

from agent.explain.explain import ScheduleFacts
from evaluation.faithfulness.faithfulness import (
    FaithfulnessResult,
    check_faithfulness,
    check_faithfulness_facts,
    parse_explanation_for_facts,
)


def test_parse_explanation_v1_template() -> None:
    """parse_explanation_for_facts extracts numbers from v1 template format."""
    explanation = (
        "Total cost: $111.57. Peak load: 50.0 kW. Unmet energy: 2.59 kWh. "
        "Cost reduction vs uncontrolled: 25.6%."
    )
    facts = parse_explanation_for_facts(explanation)
    assert facts is not None
    assert facts.total_cost_usd == pytest.approx(111.57)
    assert facts.peak_load_kw == pytest.approx(50.0)
    assert facts.total_unmet_kwh == pytest.approx(2.59)
    assert facts.cost_reduction_vs_uncontrolled_pct is not None
    assert facts.cost_reduction_vs_uncontrolled_pct == pytest.approx(25.6)


def test_parse_explanation_without_pct() -> None:
    """Parsing succeeds when cost reduction % is omitted."""
    explanation = "Total cost: $37.72. Peak load: 27.4 kW. Unmet energy: 42.76 kWh."
    facts = parse_explanation_for_facts(explanation)
    assert facts is not None
    assert facts.cost_reduction_vs_uncontrolled_pct is None


def test_parse_explanation_invalid_returns_none() -> None:
    """Unparseable or empty text returns None."""
    assert parse_explanation_for_facts("") is None
    assert parse_explanation_for_facts("No numbers here.") is None
    assert parse_explanation_for_facts("Total cost: $X. Peak load: 1.0 kW. Unmet energy: 0.0 kWh.") is None


def test_check_faithfulness_facts_match() -> None:
    """When claimed and ground truth match, result is faithful."""
    facts = ScheduleFacts(
        total_cost_usd=100.0,
        peak_load_kw=50.0,
        total_unmet_kwh=5.0,
        cost_reduction_vs_uncontrolled_pct=20.0,
    )
    result = check_faithfulness_facts(facts, facts)
    assert isinstance(result, FaithfulnessResult)
    assert result.faithful is True
    assert result.parse_failed is False
    assert len(result.claims) == 4
    assert all(c.matched for c in result.claims)


def test_check_faithfulness_facts_mismatch() -> None:
    """When claimed cost differs from ground truth, result is not faithful."""
    claimed = ScheduleFacts(100.0, 50.0, 5.0, 20.0)
    ground_truth = ScheduleFacts(200.0, 50.0, 5.0, 20.0)  # cost wrong
    result = check_faithfulness_facts(claimed, ground_truth)
    assert result.faithful is False
    cost_claim = next(c for c in result.claims if c.name == "total_cost_usd")
    assert cost_claim.matched is False
    assert cost_claim.claimed_value == 100.0
    assert cost_claim.actual_value == 200.0


def test_check_faithfulness_text_matching_ground_truth() -> None:
    """check_faithfulness with v1 explanation and matching ground truth is faithful."""
    explanation = (
        "Total cost: $111.57. Peak load: 50.0 kW. Unmet energy: 2.59 kWh. "
        "Cost reduction vs uncontrolled: 25.6%."
    )
    ground_truth = ScheduleFacts(
        total_cost_usd=111.57,
        peak_load_kw=50.0,
        total_unmet_kwh=2.59,
        cost_reduction_vs_uncontrolled_pct=25.6,
    )
    result = check_faithfulness(explanation, ground_truth)
    assert result.faithful is True
    assert result.parse_failed is False


def test_check_faithfulness_text_mismatch() -> None:
    """check_faithfulness when explanation claims wrong cost is not faithful."""
    explanation = "Total cost: $99.99. Peak load: 50.0 kW. Unmet energy: 2.59 kWh. Cost reduction vs uncontrolled: 25.6%."
    ground_truth = ScheduleFacts(111.57, 50.0, 2.59, 25.6)
    result = check_faithfulness(explanation, ground_truth)
    assert result.faithful is False
    assert result.parse_failed is False


def test_check_faithfulness_unparseable() -> None:
    """check_faithfulness with unparseable text returns parse_failed=True."""
    result = check_faithfulness("Not a valid explanation.", ScheduleFacts(1.0, 1.0, 0.0, None))
    assert result.faithful is False
    assert result.parse_failed is True
    assert len(result.claims) == 0

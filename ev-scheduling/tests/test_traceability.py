"""Unit tests for evaluation.traceability: do the answer's numbers come from the last solve?

Offline: the tool outputs are the dicts ``agent/llm_agent.py::_execute_solve``
returns, written out by hand. Two tests pin the module's documented limits, so a
later change that silently removes or worsens them fails here.
"""

import pytest

from evaluation.traceability import (
    LIMITATIONS,
    check_traceability,
    numbers_in_text,
    numbers_in_tool_outputs,
    traceable_answers_rate,
)

LAST_SOLVE = [
    {
        "success": True,
        "total_cost_usd": 24.1032,
        "peak_load_kw": 18.4,
        "total_unmet_kwh": 0.0,
        "pct_fully_served": 100.0,
        "n_sessions": 3,
        "n_steps": 96,
    }
]
PRIOR_SOLVE = [
    {
        "success": True,
        "total_cost_usd": 30.5,
        "peak_load_kw": 25.75,
        "total_unmet_kwh": 2.5,
        "pct_fully_served": 90.0,
        "n_sessions": 3,
        "n_steps": 96,
    }
]


def test_every_number_traces() -> None:
    """An answer quoting the last solve's cost, peak and unmet is traceable."""
    answer = "The optimized schedule costs $24.10, peaks at 18.4 kW, and leaves 0.00 kWh unmet."

    result = check_traceability(answer, LAST_SOLVE)

    assert result.traceable is True
    assert result.numbers_traceable is True
    assert result.from_last_solve is True
    assert result.n_numbers == 3
    assert result.n_untraceable == 0


def test_fabricated_number_is_untraceable() -> None:
    """A cost that appears in no tool output makes the whole answer untraceable."""
    answer = "The optimized schedule costs $31.75 and peaks at 18.4 kW."

    result = check_traceability(answer, LAST_SOLVE)

    assert result.traceable is False
    assert result.numbers_traceable is False
    assert result.n_numbers == 2
    assert result.n_untraceable == 1
    assert any("31.75" in t for t in result.untraceable)


def test_tolerance_band_is_one_cent() -> None:
    """$0.01 for cost: 24.11 traces to 24.1032, 24.13 does not."""
    inside = check_traceability("Total cost: $24.11.", LAST_SOLVE)
    outside = check_traceability("Total cost: $24.13.", LAST_SOLVE)

    assert inside.traceable is True
    assert outside.traceable is False


def test_coarser_quotation_of_a_solver_value_is_accepted() -> None:
    """A value quoted with fewer decimals matches the candidate rounded to that precision."""
    outputs = [{"total_unmet_kwh": 3.456}]

    assert check_traceability("About 3.5 kWh were left unmet.", outputs).traceable is True
    # The same rule can be switched off when a run needs the strict band only.
    strict = check_traceability("About 3.5 kWh were left unmet.", outputs, allow_rounded_quotes=False)
    assert strict.traceable is False


def test_answer_with_no_numbers() -> None:
    """Nothing is stated, so nothing is unsupported: traceable with n_numbers zero."""
    result = check_traceability("I could not produce a valid schedule for this day.", LAST_SOLVE)

    assert result.n_numbers == 0
    assert result.traceable is True
    assert "no numbers" in result.detail


def test_identifiers_and_clock_times_are_not_numbers() -> None:
    """Car labels, counts and clock times are not solver results and are not scored."""
    answer = "EV 1 and EV 2 charge from 9:00 to 17:00; 3 sessions in total, 2 hours each."

    mentions = numbers_in_text(answer)

    assert mentions == []
    assert check_traceability(answer, LAST_SOLVE).n_numbers == 0


def test_number_quoted_from_an_earlier_solve() -> None:
    """A value that only matches a previous solve is traceable but not current."""
    answer = "The schedule costs $30.50."

    result = check_traceability(answer, LAST_SOLVE, prior_tool_outputs=PRIOR_SOLVE)

    assert result.numbers_traceable is True   # it did come from a tool, just the wrong one
    assert result.from_last_solve is False
    assert result.traceable is False
    assert any("30.50" in t for t in result.quoted_prior_solve)


def test_before_and_after_comparison_is_not_stale() -> None:
    """Quoting both the old and the new value is a comparison, not a stale answer."""
    answer = "Cost falls from $30.50 before the outage to $24.10 after re-optimising."

    result = check_traceability(answer, LAST_SOLVE, prior_tool_outputs=PRIOR_SOLVE)

    assert result.from_last_solve is True
    assert result.traceable is True


def test_request_echo_is_not_fabricated() -> None:
    """Numbers restating the request (the site cap here) are not counted against the answer."""
    request = "Schedule the 3 cars under a 50 kW site cap."
    answer = "Total load stays under the 50 kW cap and costs $24.10."

    result = check_traceability(answer, LAST_SOLVE, request_text=request)

    assert result.traceable is True
    assert result.n_numbers == 1  # the 50 kW echo is dropped, the cost is checked


def test_limitation_derived_numbers_count_as_untraceable() -> None:
    """Documented limit 1: a correct difference of two tool values traces to neither."""
    outputs = [{"total_cost_usd": 24.10}, {"uncontrolled_cost_usd": 30.50}]
    answer = "Optimising saves $6.40 against charging on arrival."

    result = check_traceability(answer, outputs)

    assert result.traceable is False
    assert result.n_untraceable == 1
    assert "derived_numbers_count_as_untraceable" in result.limitations
    assert result.limitations == LIMITATIONS


def test_limitation_chance_match_within_tolerance() -> None:
    """Documented limit 2: an unrelated tool number can vouch for a fabricated one."""
    # 96 is the horizon length in steps; the answer uses it as a peak load in kW.
    answer = "The peak load is 96.0 kW."

    result = check_traceability(answer, LAST_SOLVE)

    assert result.traceable is True  # known false positive, not an endorsement
    assert "chance_match_within_tolerance" in result.limitations


def test_numbers_in_tool_outputs_accepts_json_strings() -> None:
    """Tool outputs may arrive as the JSON strings the transcript stores."""
    as_dicts = numbers_in_tool_outputs(LAST_SOLVE)
    as_json = numbers_in_tool_outputs(['{"total_cost_usd": 24.1032, "peak_load_kw": 18.4}'])

    assert 24.1032 in as_dicts and 18.4 in as_dicts
    assert as_json == [24.1032, 18.4]
    # Booleans must not be read as 1/0 candidates.
    assert 1.0 not in numbers_in_tool_outputs([{"success": True}])


def test_traceable_answers_rate_is_per_answer() -> None:
    """The column is the share of answers where every number traces."""
    good = check_traceability("Total cost: $24.10.", LAST_SOLVE)
    bad = check_traceability("Total cost: $31.75, peak 18.4 kW, 0.00 kWh unmet.", LAST_SOLVE)

    agg = traceable_answers_rate([good, good, good, bad])

    assert agg == {"rate": pytest.approx(0.75), "count": 3, "total": 4}
    # One fabricated number out of three sinks the whole answer; a per-number mean would not.
    assert bad.n_untraceable == 1 and bad.traceable is False

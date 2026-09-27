"""Unit tests for evaluation.outcome (the three-way split) and the cost gap.

The gap lives in ``evaluation/metrics`` but is the state term of Solved, so its
trap (a cheaper schedule bought by under-delivering) is tested here next to the
outcome that consumes it.
"""

import numpy as np
import pytest

from config.site import SiteConfig, TOUConfig
from solver.checker import check
from data.format.schema import DaySessions, Session
from evaluation.metrics import compute_metrics, cost_gap
from evaluation.outcome import (
    OUTCOMES,
    SOLVED_TERMS,
    AnswerCheck,
    GateVerdict,
    RequestAnswer,
    check_answer,
    check_state,
    classify_outcome,
    outcome_rates,
)


def _classify(**overrides):
    """A day where everything passes, with named parts overridden per test."""
    kwargs = dict(
        formulation_exact=True,
        no_hard_violation=True,
        gap_pct=0.0,
        traceable=True,
        gate=GateVerdict(passed=True, reason="schedule revalidated"),
        answer=RequestAnswer(kind="cost", truth=24.10, given=24.10, detail="What does the day cost?"),
    )
    kwargs.update(overrides)
    return classify_outcome(**kwargs)


# --------------------------------------------------------------------------- cost gap


def test_cost_gap_percentage() -> None:
    """gap = (cost - cost_star) / cost_star, in per cent."""
    gap = cost_gap(26.40, 24.00, unmet_kwh=0.0)

    assert gap.gap_pct == pytest.approx(10.0)
    assert gap.comparable is True
    assert gap.cost_star_usd == 24.00


def test_cost_gap_without_an_optimum() -> None:
    """No denominator (an empty day, cost_star 0) means no gap, not a gap of zero."""
    gap = cost_gap(0.0, 0.0, unmet_kwh=0.0)

    assert gap.gap_pct is None
    assert "no optimum" in gap.detail


def test_cost_gap_under_delivery_is_not_comparable() -> None:
    """The trap: a schedule that skips charging is cheaper, and that is not an improvement."""
    gap = cost_gap(12.00, 24.00, unmet_kwh=40.0, unmet_star_kwh=0.0)

    assert gap.gap_pct == pytest.approx(-50.0)   # the number is still reported
    assert gap.comparable is False               # paired with the reason it is meaningless
    assert gap.unmet_kwh == 40.0 and gap.unmet_star_kwh == 0.0
    assert "under-delivers" in gap.detail or "unmet" in gap.detail


def test_cost_gap_against_an_optimum_that_also_under_delivers() -> None:
    """On a day whose demand cannot be met, the comparison is against the optimum's unmet."""
    same = cost_gap(24.10, 24.00, unmet_kwh=5.0, unmet_star_kwh=5.0)
    worse = cost_gap(20.00, 24.00, unmet_kwh=9.0, unmet_star_kwh=5.0)

    assert same.comparable is True
    assert worse.comparable is False


def test_compute_metrics_threads_the_optimum_and_the_check_result() -> None:
    """compute_metrics reports the gap and the hard-violation view of the same day."""
    sessions = [Session("s1", arrival_idx=0, departure_idx=4, energy_kwh=4.0, charger_id="c1", max_power_kw=4.0)]
    day = DaySessions(sessions=sessions, n_steps=8, dt_hours=0.25)
    site = SiteConfig(P_max_kw=10.0, n_steps=8, dt_hours=0.25)
    tou = TOUConfig(rates_per_kwh=np.full(8, 0.10))
    schedule = np.zeros((1, 8))
    schedule[0, 0:4] = 4.0  # 4 kWh at $0.10/kWh = $0.40

    result = check(schedule, day, site)
    metrics = compute_metrics(
        schedule, day, tou, day.dt_hours,
        cost_star_usd=0.40, check_result=result,
    )

    assert metrics.total_cost_usd == pytest.approx(0.40)
    assert metrics.cost_gap_pct == pytest.approx(0.0)
    assert metrics.gap_comparable is True
    assert metrics.no_hard_violation is True
    assert metrics.max_violation_kw == 0.0
    assert metrics.violation_count == 0


def test_compute_metrics_without_an_optimum_leaves_the_gap_empty() -> None:
    """No cost_star means no gap field, rather than a fabricated zero."""
    sessions = [Session("s1", arrival_idx=0, departure_idx=4, energy_kwh=4.0, charger_id="c1", max_power_kw=4.0)]
    day = DaySessions(sessions=sessions, n_steps=8, dt_hours=0.25)
    tou = TOUConfig(rates_per_kwh=np.full(8, 0.10))
    schedule = np.zeros((1, 8))
    schedule[0, 0:4] = 4.0

    metrics = compute_metrics(schedule, day, tou, day.dt_hours)

    assert metrics.cost_gap_pct is None
    assert metrics.gap_comparable is None
    assert metrics.no_hard_violation is None


# --------------------------------------------------------------------------- state term


def test_check_state_terms() -> None:
    """The state passes only when it is runnable, close to the optimum, and comparable."""
    assert check_state(no_hard_violation=True, gap_pct=0.4).status == "pass"
    assert check_state(no_hard_violation=False, gap_pct=0.0, max_violation_kw=3.0).status == "fail"
    assert check_state(no_hard_violation=True, gap_pct=5.0).status == "fail"
    assert check_state(no_hard_violation=True, gap_pct=-50.0, gap_comparable=False).status == "fail"
    # A negative gap that is comparable is a legitimate pass (solver slop below the optimum).
    assert check_state(no_hard_violation=True, gap_pct=-0.2, gap_comparable=True).status == "pass"
    # No optimum to compare against: not checkable, and it does not demote on its own.
    assert check_state(no_hard_violation=True, gap_pct=None).status == "not_checkable"


# --------------------------------------------------------------------------- answer term


def test_check_answer_statuses() -> None:
    """pass, fail, and not_checkable are three distinct states."""
    assert check_answer(RequestAnswer("cost", 24.10, 24.105)).status == "pass"
    assert check_answer(RequestAnswer("cost", 24.10, 31.75)).status == "fail"
    assert check_answer(RequestAnswer("state", {"total_cost_usd": 24.10}, None, checkable=False)).status == "not_checkable"
    assert check_answer(None).status == "not_checkable"
    # A checkable question the reply never answered is a failure, not a free pass.
    assert check_answer(RequestAnswer("peak_kw", 18.4, None)).status == "fail"


def test_check_answer_set_valued() -> None:
    """Which cars go unserved is compared as a set, order and case ignored."""
    ok = check_answer(RequestAnswer("sessions", ["EV-2", "EV-5"], ["ev-5", "EV-2"]))
    bad = check_answer(RequestAnswer("sessions", ["EV-2", "EV-5"], ["EV-2"]))

    assert ok.status == "pass"
    assert bad.status == "fail"


def test_check_answer_keeps_both_sides() -> None:
    """Both answers are stored on the check, including when it is not checkable."""
    truth_state = {"total_cost_usd": 24.10, "peak_load_kw": 18.4}
    result = check_answer(RequestAnswer("state", truth_state, None, checkable=False))

    assert isinstance(result, AnswerCheck)
    assert result.truth == truth_state
    assert result.given is None
    assert result.status == "not_checkable"


# --------------------------------------------------------------------------- outcome


def test_solved() -> None:
    """Everything passes, including the answer to the question asked."""
    result = _classify()

    assert result.outcome == "solved"
    assert (result.solved, result.escalated, result.wrong_unflagged) == (True, False, False)
    assert result.parts == {
        "formulation": "pass",
        "state": "pass",
        "traceability": "pass",
        "answer": "pass",
    }


def test_wrong_answer_demotes_a_correct_state() -> None:
    """The third failure class: right schedule, wrong answer to the question."""
    result = _classify(answer=RequestAnswer("peak_kw", truth=18.4, given=25.75))

    assert result.outcome == "wrong_unflagged"
    assert result.solved is False
    assert result.state.status == "pass"          # the state was right
    assert result.answer.status == "fail"         # and it does not rescue the day
    assert result.formulation == "pass" and result.traceability == "pass"
    assert "answer" in result.reason


def test_answer_never_given_demotes() -> None:
    """A reply that never addresses the question asked is not solved."""
    result = _classify(answer=RequestAnswer("peak_kw", truth=18.4, given=None))

    assert result.outcome == "wrong_unflagged"
    assert result.answer.status == "fail"


def test_operation_only_request_is_solved_on_state_alone() -> None:
    """Nothing checkable in the reply: the state is the whole criterion, and truth is still stored."""
    truth_state = {"total_cost_usd": 24.10, "peak_load_kw": 18.4, "total_unmet_kwh": 0.0}
    result = _classify(answer=RequestAnswer("state", truth=truth_state, given=None, checkable=False))

    assert result.outcome == "solved"
    assert result.answer.status == "not_checkable"  # not folded into "pass"
    assert result.answer_truth == truth_state       # stored anyway, for a later audit
    assert result.as_row()["answer_truth"] == truth_state
    assert result.as_row()["answer_status"] == "not_checkable"


def test_escalated() -> None:
    """The gate failed and the answer declares it."""
    result = _classify(
        no_hard_violation=False,
        gap_pct=None,
        max_violation_kw=4.2,
        gate=GateVerdict(passed=False, declared_failure=True, reason="site cap exceeded at t=40"),
    )

    assert result.outcome == "escalated"
    assert (result.solved, result.escalated, result.wrong_unflagged) == (False, True, False)
    assert result.gate_passed is False
    assert "site cap" in result.detail


def test_escalation_takes_precedence_over_a_passing_state() -> None:
    """A gate abstention on a day that was in fact fine is escalated, never solved."""
    result = _classify(gate=GateVerdict(passed=False, declared_failure=True, reason="could not verify"))

    assert result.outcome == "escalated"
    assert result.solved is False
    assert result.state.status == "pass"


def test_gate_failed_but_answer_presented_a_schedule() -> None:
    """Failing the gate and reporting anyway is the worst case, not an escalation."""
    result = _classify(gate=GateVerdict(passed=False, declared_failure=False, reason="unmet above threshold"))

    assert result.outcome == "wrong_unflagged"
    assert result.escalated is False
    assert "presented a schedule" in result.reason


def test_arm_without_a_gate_can_never_escalate() -> None:
    """The LLM-only baseline has no handoff mechanism, however uncertain its prose sounds."""
    solved = _classify(gate=None)
    wrong = _classify(gate=None, no_hard_violation=False, max_violation_kw=6.0)

    assert solved.outcome == "solved" and solved.gate_passed is None
    assert wrong.outcome == "wrong_unflagged"
    assert wrong.escalated is False


def test_untraceable_number_demotes() -> None:
    """A number that does not come from the last solve is wrong, unflagged."""
    result = _classify(traceable=False)

    assert result.outcome == "wrong_unflagged"
    assert result.traceability == "fail"


def test_hard_violation_demotes() -> None:
    result = _classify(no_hard_violation=False, max_violation_kw=3.5)

    assert result.outcome == "wrong_unflagged"
    assert result.state.status == "fail"
    assert result.as_row()["max_violation_kw"] == 3.5


def test_gap_outside_tolerance_demotes() -> None:
    result = _classify(gap_pct=7.5)

    assert result.outcome == "wrong_unflagged"
    assert result.state.gap_within_tolerance is False


def test_under_delivering_schedule_is_not_solved() -> None:
    """Feasible in the hard sense, cheaper than the optimum, and still not solved."""
    result = _classify(gap_pct=-50.0, gap_comparable=False)

    assert result.outcome == "wrong_unflagged"
    assert result.state.no_hard_violation is True
    assert result.state.gap_comparable is False


def test_missing_formulation_step_does_not_demote() -> None:
    """An arm with no extraction step has that term not checkable, not failed."""
    result = _classify(formulation_exact=None)

    assert result.formulation == "not_checkable"
    assert result.outcome == "solved"


# ------------------------------------------------- formulation is not a term of Solved


def test_formulation_is_not_one_of_the_solved_terms() -> None:
    """The definition is one constant, not a list comprehension to be re-read."""
    assert SOLVED_TERMS == ("state", "traceability", "answer")
    assert "formulation" not in SOLVED_TERMS


def test_a_wrong_formulation_does_not_demote_a_correct_day() -> None:
    """Daniela's decision of 2026-09-21: Solved says what was delivered was right."""
    result = _classify(formulation_exact=False)

    assert result.outcome == "solved"
    assert result.formulation == "fail"          # still measured
    assert result.parts["formulation"] == "fail"  # still stored on the row
    assert "formulation" in result.reason         # and still said out loud


@pytest.mark.parametrize("term", SOLVED_TERMS)
def test_each_solved_term_still_demotes(term: str) -> None:
    """Removing formulation removed one term and no others."""
    failing = {
        "state": {"no_hard_violation": False},
        "traceability": {"traceable": False},
        "answer": {"answer": RequestAnswer("cost", truth=24.10, given=99.99)},
    }[term]
    result = _classify(**failing)

    assert result.outcome == "wrong_unflagged"
    assert result.parts[term] == "fail"
    assert term in result.reason


def test_a_wrong_formulation_usually_fails_the_state_term_too() -> None:
    """The honest case, and the one the twenty-day gpt-4o-mini run produced.

    A schedule optimised on misread parameters breaks the real session's window
    and its cost is not comparable with the true optimum, so the state term
    fails for the same underlying error. Dropping the formulation term from
    Solved does not rescue such a day, and the test exists so that nobody reads
    the change as one that improves the score.
    """
    result = _classify(
        formulation_exact=False,
        no_hard_violation=False,
        max_violation_kw=5.14,
        gap_pct=-0.13,
        gap_comparable=False,
        answer=RequestAnswer("unmet_kwh", truth=2.59, given=3.84),
    )

    assert result.outcome == "wrong_unflagged"
    assert result.parts == {
        "formulation": "fail",
        "state": "fail",
        "traceability": "pass",
        "answer": "fail",
    }
    assert result.reason == "failed: state, answer"


def test_outcomes_are_mutually_exclusive_and_exhaustive() -> None:
    """Exactly one of the three, in every combination tested here."""
    cases = [
        _classify(),
        _classify(answer=RequestAnswer("cost", 24.10, 31.75)),
        _classify(traceable=False),
        _classify(no_hard_violation=False),
        _classify(gate=GateVerdict(passed=False, declared_failure=True)),
        _classify(gate=GateVerdict(passed=False, declared_failure=False)),
        _classify(gate=None, formulation_exact=False),
    ]

    for result in cases:
        flags = [result.solved, result.escalated, result.wrong_unflagged]
        assert sum(bool(f) for f in flags) == 1
        assert result.outcome in OUTCOMES


def test_outcome_rates_sum_to_one() -> None:
    results = [
        _classify(),
        _classify(),
        _classify(gate=GateVerdict(passed=False, declared_failure=True)),
        _classify(traceable=False),
    ]

    rates = outcome_rates(results)

    assert rates["total"] == 4
    assert rates["solved_rate"] == pytest.approx(0.5)
    assert rates["escalated_rate"] == pytest.approx(0.25)
    assert rates["wrong_unflagged_rate"] == pytest.approx(0.25)
    assert sum(rates[f"{name}_rate"] for name in OUTCOMES) == pytest.approx(1.0)
    assert outcome_rates([])["solved_rate"] is None

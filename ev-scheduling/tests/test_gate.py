"""Unit tests for methods.agent.validate.gate: the seven conditions, and the one retry.

Offline and adversarial. No API key, no LLM and no CVXPY: the solve results are
hand-written in the shape ``solver.solver.SolveResult`` returns, and the
tool outputs are the dicts ``methods/agent/llm_agent.py::_execute_solve`` builds. Each
failure test isolates one condition, so a change that makes a condition stop
catching its own failure class fails here and not somewhere else.

The day whose demand the site cap cannot serve is the test that matters most:
the solver is optimal, energy is unmet, and the gate must pass. Under-delivery
forced by the cap is the optimum paying a penalised slack, not an error, and a
gate that escalated it would report a person is needed on exactly the days the
optimiser got right.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pytest

from methods.agent.validate.gate import (
    ACCEPT,
    CONDITION_DESCRIPTIONS,
    CONDITION_LABELS,
    CONDITION_ORDER,
    DECLARE_FAILURE,
    FAIL,
    MATERIAL_UNMET_KWH,
    MATERIAL_UNMET_SHARE,
    NOT_APPLICABLE,
    PASS,
    RETRY,
    decide,
    is_material_shortfall,
    shortfall_of,
    declared_failure_text,
    retry_changes_problem,
    retry_message,
    split_tool_outputs,
    verify_answer,
)
from config.site import SiteConfig, TOUConfig
from data.format.schema import DaySessions, Session
from evaluation.outcome import classify_outcome

# --------------------------------------------------------------------------- fixtures


@dataclass
class FakeSolve:
    """Same fields as ``solver.solver.SolveResult``, built without CVXPY."""

    schedule: np.ndarray
    total_cost_usd: float = 0.0
    unmet_energy_kwh: np.ndarray = field(default_factory=lambda: np.zeros(1))
    peak_load_kw: float = 0.0
    success: bool = True
    message: Optional[str] = None


def one_car_day() -> DaySessions:
    """One session asking 2 kWh over a two-hour horizon of eight 15-minute steps."""
    session = Session(
        session_id="s1",
        arrival_idx=0,
        departure_idx=8,
        energy_kwh=2.0,
        charger_id="CA-322",
        max_power_kw=8.0,
    )
    return DaySessions(sessions=[session], n_steps=8, dt_hours=0.25)


def one_car_site() -> SiteConfig:
    """A 20 kW cap, wide enough for the whole request."""
    return SiteConfig(P_max_kw=20.0, n_steps=8, dt_hours=0.25)


def cheap_then_expensive_tou() -> TOUConfig:
    """$0.10/kWh for the first hour, $0.50/kWh for the second."""
    return TOUConfig(rates_per_kwh=np.array([0.10] * 4 + [0.50] * 4))


def optimal_schedule() -> np.ndarray:
    """8 kW in the first cheap step delivers the 2 kWh: $0.20, peak 8 kW, nothing unmet."""
    schedule = np.zeros((1, 8))
    schedule[0, 0] = 8.0
    return schedule


OPTIMAL_TOOL_OUTPUT: Dict[str, Any] = {
    "success": True,
    "total_cost_usd": 0.2,
    "peak_load_kw": 8.0,
    "total_unmet_kwh": 0.0,
    "pct_fully_served": 100.0,
    "n_sessions": 1,
    "n_steps": 8,
}
# An earlier, differently posed solve in the same episode (a what-if the model tried).
WHAT_IF_TOOL_OUTPUT: Dict[str, Any] = {
    "success": True,
    "total_cost_usd": 1.35,
    "peak_load_kw": 12.0,
    "total_unmet_kwh": 0.5,
    "pct_fully_served": 75.0,
    "n_sessions": 2,
    "n_steps": 8,
}

GOOD_ANSWER = "The optimised schedule costs $0.20, peaks at 8.0 kW, and leaves 0.00 kWh unmet."


def verify(
    answer: Optional[str],
    *,
    solve_result: Optional[FakeSolve],
    day: Optional[DaySessions] = None,
    site: Optional[SiteConfig] = None,
    tool_outputs: Optional[List[Any]] = None,
    prior_tool_outputs: Optional[List[Any]] = None,
):
    """``verify_answer`` on the one-car day, with the tariff supplied."""
    return verify_answer(
        answer,
        solve_result=solve_result,
        day=day if day is not None else one_car_day(),
        site=site if site is not None else one_car_site(),
        tool_outputs=tool_outputs if tool_outputs is not None else [OPTIMAL_TOOL_OUTPUT],
        prior_tool_outputs=prior_tool_outputs or [],
        tou=cheap_then_expensive_tou(),
    )


def status_of(result, name: str) -> str:
    """Status of one condition by key."""
    return result.conditions[name].status


# --------------------------------------------------------------------------- the good day


def test_verified_answer_passes_every_condition() -> None:
    """An optimal schedule reported with the last solve's own numbers passes.

    E6 is not applicable here rather than passing: the day is served in full, so
    there is no shortfall for the answer to declare.
    """
    result = verify(GOOD_ANSWER, solve_result=FakeSolve(schedule=optimal_schedule(), success=True))

    assert result.passed is True
    assert [status_of(result, name) for name in CONDITION_ORDER[:5]] == [PASS] * 5
    assert status_of(result, "shortfall_declared") == NOT_APPLICABLE
    assert result.failed == []
    assert result.reason == "every applicable condition passed"


def test_passing_result_is_accepted_without_a_retry() -> None:
    """``decide`` on a passing result accepts, with a passed verdict and no message."""
    result = verify(GOOD_ANSWER, solve_result=FakeSolve(schedule=optimal_schedule()))

    decision = decide(result, attempt=1)

    assert decision.action == ACCEPT
    assert decision.message == ""
    assert decision.verdict.passed is True
    assert decision.verdict.declared_failure is False


# --------------------------------------------------------------------------- E1


def test_no_solve_at_all_fails_e1() -> None:
    """The model answered without calling the solver: nothing is solver-grounded."""
    result = verify("The cars will all be charged by 8am.", solve_result=None, tool_outputs=[])

    assert result.passed is False
    assert status_of(result, "solver_optimal") == FAIL
    assert "never called" in result.conditions["solver_optimal"].detail
    # Nothing to check the schedule against either, and no metrics to compare.
    assert status_of(result, "no_hard_violation") == FAIL
    assert status_of(result, "schedule_consistency") == NOT_APPLICABLE


def test_non_optimal_solver_status_fails_e1() -> None:
    """A solve that did not reach an optimal status carries its status into the verdict."""
    solve = FakeSolve(schedule=np.zeros((1, 8)), success=False, message="infeasible")

    result = verify("No feasible schedule was found.", solve_result=solve, tool_outputs=[])

    assert status_of(result, "solver_optimal") == FAIL
    assert "infeasible" in result.conditions["solver_optimal"].detail


def test_schedule_for_a_different_problem_fails_e1() -> None:
    """A schedule sized for another day did not solve the problem actually posed."""
    two_rows = np.zeros((2, 8))

    result = verify(GOOD_ANSWER, solve_result=FakeSolve(schedule=two_rows))

    assert status_of(result, "solver_optimal") == FAIL
    assert "different problem" in result.conditions["solver_optimal"].detail
    assert status_of(result, "no_hard_violation") == FAIL


# --------------------------------------------------------------------------- E2


def test_infeasible_schedule_presented_as_valid_fails_e2() -> None:
    """24 kW on an 8 kW charger under a 20 kW cap is not runnable, however it is described."""
    schedule = np.zeros((1, 8))
    schedule[0, 0] = 24.0
    tool_output = {
        "success": True,
        "total_cost_usd": 0.6,
        "peak_load_kw": 24.0,
        "total_unmet_kwh": 0.0,
        "pct_fully_served": 100.0,
    }
    answer = "The schedule is valid: it costs $0.60 and peaks at 24.0 kW."

    result = verify(answer, solve_result=FakeSolve(schedule=schedule), tool_outputs=[tool_output])

    assert result.passed is False
    assert status_of(result, "no_hard_violation") == FAIL
    # The numbers are real and current, and they do describe this schedule: only E2 fails.
    assert status_of(result, "traceable") == PASS
    assert status_of(result, "currency") == PASS
    assert status_of(result, "schedule_consistency") == PASS
    assert result.conditions["no_hard_violation"].residual == pytest.approx(16.0)


def test_unmet_energy_forced_by_the_site_cap_is_not_a_failure() -> None:
    """The optimum under a cap that cannot serve the day in full still passes the gate.

    The checker calls this day infeasible, because ``CheckResult.feasible`` means
    no violation of any kind and 5 kWh go undelivered. The gate reads
    ``no_hard_violation`` instead, so the day is not escalated.
    """
    session = Session(
        session_id="s1",
        arrival_idx=0,
        departure_idx=4,
        energy_kwh=10.0,
        charger_id="CA-322",
        max_power_kw=8.0,
    )
    day = DaySessions(sessions=[session], n_steps=4, dt_hours=0.25)
    site = SiteConfig(P_max_kw=5.0, n_steps=4, dt_hours=0.25)
    schedule = np.full((1, 4), 5.0)  # 5 kWh delivered of the 10 kWh asked
    tool_output = {
        "success": True,
        "total_cost_usd": 0.5,
        "peak_load_kw": 5.0,
        "total_unmet_kwh": 5.0,
        "pct_fully_served": 0.0,
    }
    answer = (
        "The day cannot be served in full under the cap: the schedule costs $0.50, "
        "peaks at 5.0 kW, and leaves 5.00 kWh unmet."
    )

    result = verify_answer(
        answer,
        solve_result=FakeSolve(schedule=schedule),
        day=day,
        site=site,
        tool_outputs=[tool_output],
        tou=TOUConfig(rates_per_kwh=np.array([0.10] * 4)),
    )

    assert result.check_result is not None
    assert result.check_result.feasible is False  # the old, any-violation meaning
    assert result.check_result.no_hard_violation is True
    assert result.passed is True
    assert status_of(result, "no_hard_violation") == PASS
    assert decide(result, attempt=1).action == ACCEPT


# --------------------------------------------------------------------------- E3 and E4


def test_fabricated_number_fails_e3() -> None:
    """A cost that appears in no tool output makes the answer unreportable."""
    answer = "The optimised schedule costs $31.75 and peaks at 8.0 kW."

    result = verify(answer, solve_result=FakeSolve(schedule=optimal_schedule()))

    assert result.passed is False
    assert status_of(result, "traceable") == FAIL
    assert status_of(result, "currency") == PASS
    assert "31.75" in result.conditions["traceable"].detail


def test_number_from_a_previous_solve_fails_e4() -> None:
    """Quoting the what-if solve the model tried earlier, after re-solving, is stale."""
    answer = "The schedule costs $1.35 and peaks at 12.0 kW."

    result = verify(
        answer,
        solve_result=FakeSolve(schedule=optimal_schedule()),
        tool_outputs=[OPTIMAL_TOOL_OUTPUT],
        prior_tool_outputs=[WHAT_IF_TOOL_OUTPUT],
    )

    assert result.passed is False
    assert status_of(result, "currency") == FAIL
    # The numbers exist in the episode, so E3 passes: only E4 separates the two.
    assert status_of(result, "traceable") == PASS
    assert result.conditions["currency"].residual == pytest.approx(2.0)


def test_before_and_after_comparison_is_not_stale() -> None:
    """An answer quoting the old and the new value is a comparison, not a stale report."""
    answer = "Cost falls from $1.35 to $0.20 once the charger is back, and the peak from 12.0 kW to 8.0 kW."

    result = verify(
        answer,
        solve_result=FakeSolve(schedule=optimal_schedule()),
        tool_outputs=[OPTIMAL_TOOL_OUTPUT],
        prior_tool_outputs=[WHAT_IF_TOOL_OUTPUT],
    )

    assert status_of(result, "currency") == PASS
    assert result.passed is True


def test_answer_with_no_numbers_leaves_e3_and_e4_inapplicable() -> None:
    """An answer stating no numbers reports nothing unsupported, so the gate does not fail it.

    Whether it answered the question asked is the answer term in
    ``evaluation/outcome.py``, not the gate's business.
    """
    result = verify("The schedule is ready and every car leaves charged.", solve_result=FakeSolve(schedule=optimal_schedule()))

    assert status_of(result, "traceable") == NOT_APPLICABLE
    assert status_of(result, "currency") == NOT_APPLICABLE
    assert result.conditions["traceable"].residual is None
    assert result.passed is True


# --------------------------------------------------------------------------- E5


def test_metrics_of_another_solve_fail_e5() -> None:
    """The prose describes the what-if solve while the matrix surfaced is the base one.

    Every other condition passes: the solve is optimal, the schedule is runnable,
    the numbers are real and they are the last solve's. Only recomputing the
    metrics from the schedule itself shows the two are not the same solve.
    """
    result = verify(
        "The schedule costs $1.35, peaks at 12.0 kW, and leaves 0.50 kWh unmet.",
        solve_result=FakeSolve(schedule=optimal_schedule()),
        tool_outputs=[WHAT_IF_TOOL_OUTPUT],
    )

    assert result.passed is False
    assert status_of(result, "schedule_consistency") == FAIL
    assert [status_of(result, name) for name in ("solver_optimal", "no_hard_violation", "traceable", "currency")] == [PASS] * 4
    assert result.conditions["schedule_consistency"].residual == pytest.approx(4.0)  # 12.0 kW reported, 8.0 kW real
    assert "peak load" in result.conditions["schedule_consistency"].detail


def test_e5_compares_peak_and_unmet_without_a_tariff() -> None:
    """Without TOU rates the cost cannot be recomputed, and the other two still are."""
    result = verify_answer(
        "The schedule peaks at 12.0 kW.",
        solve_result=FakeSolve(schedule=optimal_schedule()),
        day=one_car_day(),
        site=one_car_site(),
        tool_outputs=[WHAT_IF_TOOL_OUTPUT],
    )

    assert status_of(result, "schedule_consistency") == FAIL
    assert result.conditions["schedule_consistency"].residual == pytest.approx(4.0)


def test_e5_is_inapplicable_without_solver_metrics() -> None:
    """A tool output carrying no solve metrics leaves nothing for E5 to compare."""
    result = verify(
        "The schedule is ready.",
        solve_result=FakeSolve(schedule=optimal_schedule()),
        tool_outputs=[{"error": "Unknown tool: draw_schedule"}],
    )

    assert status_of(result, "schedule_consistency") == NOT_APPLICABLE
    assert result.passed is True


def test_e5_accepts_a_json_string_tool_output() -> None:
    """Tool outputs are read as dicts or as the JSON strings the transcript stores."""
    import json

    result = verify(
        GOOD_ANSWER,
        solve_result=FakeSolve(schedule=optimal_schedule()),
        tool_outputs=[json.dumps(OPTIMAL_TOOL_OUTPUT)],
    )

    assert status_of(result, "schedule_consistency") == PASS
    assert result.passed is True


# --------------------------------------------------------------------------- E6


def curtailed_day() -> DaySessions:
    """One car asking 200 kWh over two hours, far more than the site can deliver.

    The EV counterpart of a power flow that does not converge, except that it
    does converge: the LP returns an optimal schedule and puts the 120 kWh it
    cannot deliver into the slack.
    """
    session = Session(
        session_id="s1",
        arrival_idx=0,
        departure_idx=8,
        energy_kwh=200.0,
        charger_id="CA-900",
        max_power_kw=40.0,
    )
    return DaySessions(sessions=[session], n_steps=8, dt_hours=0.25)


def curtailed_site() -> SiteConfig:
    """A 40 kW cap, which the whole two-hour window cannot turn into 200 kWh."""
    return SiteConfig(P_max_kw=40.0, n_steps=8, dt_hours=0.25)


def curtailed_schedule() -> np.ndarray:
    """40 kW at every step: 80 kWh delivered, 120 kWh left unmet."""
    return np.full((1, 8), 40.0)


CURTAILED_TOOL_OUTPUT: Dict[str, Any] = {
    "success": True,
    "total_cost_usd": 8.0,
    "peak_load_kw": 40.0,
    "total_unmet_kwh": 120.0,
    "pct_fully_served": 0.0,
    "n_sessions": 1,
    "n_steps": 8,
}

FLAT_TOU = TOUConfig(rates_per_kwh=np.full(8, 0.10))


def verify_curtailed(answer: Optional[str], *, tool_output: Optional[Dict[str, Any]] = None):
    """``verify_answer`` on the curtailed day, with the flat tariff supplied."""
    return verify_answer(
        answer,
        solve_result=FakeSolve(schedule=curtailed_schedule()),
        day=curtailed_day(),
        site=curtailed_site(),
        tool_outputs=[tool_output if tool_output is not None else CURTAILED_TOOL_OUTPUT],
        tou=FLAT_TOU,
    )


def test_a_curtailed_plan_reported_as_a_success_fails_e6() -> None:
    """Every number true, and the one that matters left out.

    This is the failure the condition exists for. The cost and the peak are the
    solver's own, the schedule is runnable, and the answer never says that 120 of
    the 200 kWh asked for will not be delivered.
    """
    result = verify_curtailed("The optimised schedule costs $8.00 and peaks at 40.0 kW.")

    assert result.passed is False
    assert status_of(result, "shortfall_declared") == FAIL
    # Nothing else is wrong with the answer: only E6 catches it.
    assert status_of(result, "solver_optimal") == PASS
    assert status_of(result, "no_hard_violation") == PASS
    assert status_of(result, "traceable") == PASS
    assert status_of(result, "currency") == PASS
    assert status_of(result, "schedule_consistency") == PASS
    assert result.conditions["shortfall_declared"].residual == pytest.approx(120.0)
    assert "120.00 kWh" in result.conditions["shortfall_declared"].detail


def test_stating_the_undelivered_energy_passes_e6() -> None:
    """The same day and the same schedule, said honestly, is accepted."""
    result = verify_curtailed(
        "The schedule costs $8.00 and peaks at 40.0 kW, and 120.00 kWh of the energy "
        "asked for cannot be delivered under the cap."
    )

    assert result.passed is True
    assert status_of(result, "shortfall_declared") == PASS
    assert decide(result, attempt=1).action == ACCEPT


def test_a_rounded_statement_of_the_shortfall_still_declares_it() -> None:
    """"about 120 kWh" is the same declaration as "120.00 kWh"."""
    result = verify_curtailed(
        "The schedule costs $8.00 and peaks at 40.0 kW. About 120 kWh will go undelivered."
    )

    assert status_of(result, "shortfall_declared") == PASS


def test_the_shortfall_may_be_declared_as_a_share_of_what_was_asked_for() -> None:
    """60% of 200 kWh undelivered is the same statement as 120 kWh undelivered.

    The complementary share counts too: "40% will be delivered" says the same
    thing. Only E6 is asserted here, because a share the agent worked out itself
    appears in no tool output and E3 scores it as untraceable, which is the
    documented ``derived_numbers_count_as_untraceable`` limit of
    ``evaluation/traceability.py``. An agent that wants to pass both states the
    kWh the tool returned.
    """
    undelivered = verify_curtailed(
        "The schedule costs $8.00 and peaks at 40.0 kW. 60.0% of the requested energy "
        "cannot be delivered."
    )
    delivered = verify_curtailed(
        "The schedule costs $8.00 and peaks at 40.0 kW. Only 40.0% of the requested energy "
        "will be delivered."
    )

    assert status_of(undelivered, "shortfall_declared") == PASS
    assert status_of(delivered, "shortfall_declared") == PASS


def test_a_shortfall_below_the_absolute_floor_is_not_material() -> None:
    """A day short by less than one driver's request has nothing to declare."""
    day = DaySessions(
        sessions=[Session("s1", 0, 8, 20.0, "CA-900", 40.0)], n_steps=8, dt_hours=0.25
    )
    tool_output = dict(CURTAILED_TOOL_OUTPUT, total_unmet_kwh=4.0)

    result = verify_answer(
        "The schedule costs $8.00 and peaks at 40.0 kW.",
        solve_result=FakeSolve(schedule=curtailed_schedule()),
        day=day,
        site=curtailed_site(),
        tool_outputs=[tool_output],
        tou=FLAT_TOU,
    )

    # 4 kWh is 20% of the day, well over the relative floor, and still below the
    # absolute one: both have to be crossed.
    assert 4.0 >= MATERIAL_UNMET_SHARE * 20.0
    assert status_of(result, "shortfall_declared") == NOT_APPLICABLE
    assert "nothing the answer must declare" in result.conditions["shortfall_declared"].detail


def test_a_shortfall_below_the_relative_floor_is_not_material() -> None:
    """Six kWh out of six hundred is inherent slop, not a curtailed plan."""
    day = DaySessions(
        sessions=[Session("s1", 0, 8, 600.0, "CA-900", 400.0)], n_steps=8, dt_hours=0.25
    )
    tool_output = dict(CURTAILED_TOOL_OUTPUT, total_unmet_kwh=6.0)

    result = verify_answer(
        "The schedule costs $8.00 and peaks at 40.0 kW.",
        solve_result=FakeSolve(schedule=curtailed_schedule()),
        day=day,
        site=SiteConfig(P_max_kw=400.0, n_steps=8, dt_hours=0.25),
        tool_outputs=[tool_output],
        tou=FLAT_TOU,
    )

    assert 6.0 >= MATERIAL_UNMET_KWH
    assert status_of(result, "shortfall_declared") == NOT_APPLICABLE


def test_a_day_served_in_full_leaves_e6_inapplicable() -> None:
    """Nothing undelivered means nothing to declare, and the condition says so."""
    result = verify(GOOD_ANSWER, solve_result=FakeSolve(schedule=optimal_schedule()))

    assert status_of(result, "shortfall_declared") == NOT_APPLICABLE
    assert result.conditions["shortfall_declared"].residual is None


def test_e6_is_inapplicable_when_nothing_reports_undelivered_energy() -> None:
    """With no tool output and no schedule there is no shortfall figure to go on."""
    result = verify_answer(
        "Time-of-use pricing charges more during the peak window.",
        solve_result=None,
        day=curtailed_day(),
        site=curtailed_site(),
        tool_outputs=[],
    )

    assert status_of(result, "shortfall_declared") == NOT_APPLICABLE
    assert shortfall_of(curtailed_day(), [], None) is None


def test_e6_falls_back_to_the_schedule_when_the_tool_reports_no_metrics() -> None:
    """An agent that surfaces a schedule without a metric summary is held to it too."""
    result = verify_curtailed(
        "Here is the plan.", tool_output={"success": True, "note": "schedule attached"}
    )
    shortfall = shortfall_of(curtailed_day(), [], None)

    assert status_of(result, "shortfall_declared") == FAIL
    assert result.conditions["shortfall_declared"].residual == pytest.approx(120.0)
    assert "recomputed" in result.conditions["shortfall_declared"].detail
    assert shortfall is None  # ... but only when there is a schedule to recompute from


def test_hiding_a_shortfall_costs_one_retry_and_then_a_declared_failure() -> None:
    """E6 goes through the same protocol as every other condition."""
    result = verify_curtailed("The optimised schedule costs $8.00 and peaks at 40.0 kW.")

    retry = decide(result, attempt=1)
    declared = decide(result, attempt=2)

    assert retry.action == RETRY
    assert "120.00 kWh" in retry.message
    assert "report the unmet energy the solver returned" in retry.message
    assert declared.action == DECLARE_FAILURE
    assert declared.verdict.declared_failure is True
    assert "120.00" in declared.message


def test_the_two_floors_of_a_material_shortfall() -> None:
    """Both have to be crossed, and the documented values are the ones in force."""
    assert MATERIAL_UNMET_KWH == 5.0
    assert MATERIAL_UNMET_SHARE == 0.02
    assert is_material_shortfall(120.0, 200.0) is True
    assert is_material_shortfall(4.99, 20.0) is False      # under the kWh floor
    assert is_material_shortfall(6.0, 600.0) is False      # under the share floor
    assert is_material_shortfall(5.0, 250.0) is True       # exactly on both floors
    assert is_material_shortfall(10.0, 0.0) is False       # nothing was asked for


def test_the_shortfall_is_read_from_the_last_tool_output() -> None:
    """``shortfall_of`` reports the day's own requested energy against the tool's unmet."""
    shortfall = shortfall_of(curtailed_day(), [CURTAILED_TOOL_OUTPUT], None)

    assert shortfall is not None
    assert shortfall.unmet_kwh == pytest.approx(120.0)
    assert shortfall.requested_kwh == pytest.approx(200.0)
    assert shortfall.share_pct == pytest.approx(60.0)
    assert shortfall.source == "tool output"
    assert shortfall.material is True


# --------------------------------------------------------------------------- retry protocol


def test_first_failure_asks_for_one_retry() -> None:
    """The first failed attempt returns the verdict to the model instead of declaring."""
    result = verify("The optimised schedule costs $31.75.", solve_result=FakeSolve(schedule=optimal_schedule()))

    decision = decide(result, attempt=1)

    assert decision.action == RETRY
    assert decision.verdict.passed is False
    assert decision.verdict.declared_failure is False  # nothing has been declared yet
    assert "Failed condition(s)" in decision.message
    assert "31.75" in decision.message
    assert "only on the problem as posed" in decision.message


def test_second_failure_declares_the_failure_and_reports_no_schedule() -> None:
    """The second failed attempt is terminal: a declared failure, no numbers surfaced."""
    result = verify("The optimised schedule costs $31.75.", solve_result=FakeSolve(schedule=optimal_schedule()))

    decision = decide(result, attempt=2)

    assert decision.action == DECLARE_FAILURE
    assert decision.verdict.passed is False
    assert decision.verdict.declared_failure is True
    assert decision.message.startswith("No schedule and no numbers are reported.")
    assert "Verification failed" in decision.message
    assert "declared after 2 attempt(s)" in decision.verdict.reason


def test_a_corrected_second_answer_is_accepted() -> None:
    """The retry exists to be used: a corrected answer on attempt 2 still passes."""
    result = verify(GOOD_ANSWER, solve_result=FakeSolve(schedule=optimal_schedule()))

    decision = decide(result, attempt=2)

    assert decision.action == ACCEPT
    assert decision.verdict.passed is True


def test_retry_message_names_every_failed_condition() -> None:
    """A day failing two conditions is told about both, once."""
    schedule = np.zeros((1, 8))
    schedule[0, 0] = 24.0
    tool_output = {"success": True, "total_cost_usd": 0.6, "peak_load_kw": 24.0, "total_unmet_kwh": 0.0}

    result = verify(
        "The schedule is valid: it costs $0.60, peaks at 24.0 kW, and saves $99.99.",
        solve_result=FakeSolve(schedule=schedule),
        tool_outputs=[tool_output],
    )
    message = retry_message(result)

    assert {c.name for c in result.failed} == {"no_hard_violation", "traceable"}
    assert message.count("\n- ") == 2
    assert "hard constraint" in message
    assert "99.99" in message


def test_declared_failure_text_does_not_present_a_schedule() -> None:
    """The terminal text says the verification step failed, not that the day is unservable."""
    result = verify("The optimised schedule costs $31.75.", solve_result=FakeSolve(schedule=optimal_schedule()))

    text = declared_failure_text(result)

    assert "No schedule and no numbers are reported." in text
    assert "not a claim that the day cannot be served" in text


def test_retry_changes_problem_blocks_a_new_what_if() -> None:
    """Re-solving with a charger disabled or the cap moved answers a different question."""
    assert retry_changes_problem({"disabled_chargers": ["CA-322"]}) is True
    assert retry_changes_problem({"site_cap_kw": 5.0}) is True
    assert retry_changes_problem({"extra_sessions": [{"arrival_idx": 0}]}) is True
    assert retry_changes_problem('{"site_cap_kw": 5.0}') is True


def test_retry_may_re_solve_the_problem_as_posed() -> None:
    """A plain re-solve, or the what-if the request itself asked for, is allowed."""
    assert retry_changes_problem({}) is False
    assert retry_changes_problem({"penalty_unmet": 1e6}) is False
    assert retry_changes_problem({"disabled_chargers": []}) is False
    assert (
        retry_changes_problem(
            {"site_cap_kw": 30.0},
            original_arguments={"site_cap_kw": 30.0},
        )
        is False
    )
    assert (
        retry_changes_problem(
            {"site_cap_kw": 5.0},
            original_arguments={"site_cap_kw": 30.0},
        )
        is True
    )


# --------------------------------------------------------------------------- wiring


def test_split_tool_outputs_separates_the_last_solve() -> None:
    """The last recorded output is the solve being surfaced; the rest is exploration."""
    prior, last = split_tool_outputs([WHAT_IF_TOOL_OUTPUT, OPTIMAL_TOOL_OUTPUT])

    assert prior == [WHAT_IF_TOOL_OUTPUT]
    assert last == [OPTIMAL_TOOL_OUTPUT]
    assert split_tool_outputs([]) == ([], [])


def test_declared_failure_makes_the_day_escalated() -> None:
    """The verdict feeds ``evaluation.outcome`` unchanged: a declared failure escalates."""
    result = verify("The optimised schedule costs $31.75.", solve_result=FakeSolve(schedule=optimal_schedule()))
    decision = decide(result, attempt=2)

    outcome = classify_outcome(
        formulation_exact=None,
        no_hard_violation=True,
        gap_pct=0.0,
        traceable=False,
        gate=decision.verdict,
    )

    assert outcome.outcome == "escalated"
    assert outcome.escalated is True
    assert outcome.gate_declared_failure is True


def test_gate_failure_presented_as_valid_is_wrong_unflagged() -> None:
    """A caller that surfaces a schedule anyway must not store a declared failure."""
    result = verify("The optimised schedule costs $31.75.", solve_result=FakeSolve(schedule=optimal_schedule()))
    decision = decide(result, attempt=1)  # retry offered, nothing declared

    outcome = classify_outcome(
        formulation_exact=None,
        no_hard_violation=True,
        gap_pct=0.0,
        traceable=False,
        gate=decision.verdict,
    )

    assert outcome.outcome == "wrong_unflagged"


def test_every_condition_is_reported_separately() -> None:
    """One status and one residual per condition, for the supplementary table."""
    result = verify(GOOD_ANSWER, solve_result=FakeSolve(schedule=optimal_schedule()))
    row = result.as_row()

    assert set(CONDITION_LABELS) == set(CONDITION_ORDER) == set(CONDITION_DESCRIPTIONS)
    for name in CONDITION_ORDER[:5]:
        label = CONDITION_LABELS[name]
        assert row[f"gate_{label}_{name}"] == PASS
        assert row[f"gate_{label}_residual"] == pytest.approx(0.0)
    # Nothing is undelivered on this day, so E6 is reported as not in force and
    # carries no residual.
    assert row["gate_E6_shortfall_declared"] == NOT_APPLICABLE
    assert row["gate_E6_residual"] is None
    # This fixture's verify() passes no request text, so E7 abstains: it is the
    # one condition that reads something outside the solve.
    assert row["gate_E7_problem_read_back"] == NOT_APPLICABLE
    # And E8 with it: with no request text there is no question to hold the
    # answer's quantity to.
    assert row["gate_E8_answers_the_question"] == NOT_APPLICABLE
    assert row["gate_passed"] is True
    assert [CONDITION_LABELS[name] for name in CONDITION_ORDER] == [
        "E1", "E2", "E3", "E4", "E5", "E6", "E7", "E8",
    ]


# --------------------------------------------------------------------------- E7, the read-back


def _read_back_day(text: str):
    """The day the deterministic grammar reads out of a request, for E7 fixtures."""
    from methods.agent.parse.parse import parsed_problem_to_day_site_tou
    from methods.deterministic.rule_based import parse_request

    day, _site, _tou = parsed_problem_to_day_site_tou(parse_request(text).problem)
    return day


_E7_REQUEST = (
    "2 cars are charging at the lot today, and here is what each one needs. "
    "EV 1: arrives a quarter to two in the afternoon, leaves 23:15, 14.72 kWh, 7 kW maximum. "
    "EV 2 sits on a 7 kW station between 17:00 and 24:00 and asks for 6.47 kWh. "
    "Total draw across all the chargers has to stay at or below 50 kilowatts. "
    "Energy costs $0.45 per kWh between 4 pm and 9 pm and $0.12 per kWh the rest of the day. "
    "Plan the charging to minimise what we pay for the energy."
)


def test_e7_passes_when_the_extraction_matches_the_request() -> None:
    from methods.agent.validate.gate import PASS, _check_problem_read_back

    condition = _check_problem_read_back(_read_back_day(_E7_REQUEST), _E7_REQUEST)
    assert condition.status == PASS
    assert condition.label == "E7"


def test_e7_catches_the_quarter_to_misread_that_the_gate_used_to_accept() -> None:
    """The failure the run of 2026-09-28 measured, as a test.

    "a quarter to two in the afternoon" is 13:45. The model read it as 13:15 on
    58 of the 59 thirty-minute errors of that run, the solver then produced an
    optimal schedule for a day that does not exist, and E1 to E6 all passed
    because each of them judges the answer against that same wrong problem.
    """
    import dataclasses

    from methods.agent.validate.gate import FAIL, _check_problem_read_back

    day = _read_back_day(_E7_REQUEST)
    sessions = list(day.sessions)
    # 13:45 read as 13:15: two steps of a quarter hour, early.
    sessions[0] = dataclasses.replace(sessions[0], arrival_idx=sessions[0].arrival_idx - 2)
    misread = dataclasses.replace(day, sessions=sessions)

    condition = _check_problem_read_back(misread, _E7_REQUEST)
    assert condition.status == FAIL
    assert condition.residual == 1.0
    assert "arrival" in condition.detail
    assert "13.25 h" in condition.detail and "13.75 h" in condition.detail


def test_e7_abstains_rather_than_accuses() -> None:
    """A reader that cannot read the sentence is not evidence that the model is wrong.

    The grammar is deliberately bounded. Three cases abstain, and abstaining
    never fails the gate: no request text, a phrasing outside the grammar, and
    an extraction with no sessions.
    """
    import dataclasses

    from methods.agent.validate.gate import NOT_APPLICABLE, _check_problem_read_back

    day = _read_back_day(_E7_REQUEST)
    assert _check_problem_read_back(day, "").status == NOT_APPLICABLE
    assert _check_problem_read_back(day, None).status == NOT_APPLICABLE
    assert _check_problem_read_back(
        day, "EV 1 shows up sometime after lunch and stays until the evening; it wants 10 kWh at 7 kW."
    ).status == NOT_APPLICABLE
    assert _check_problem_read_back(dataclasses.replace(day, sessions=[]), _E7_REQUEST).status == NOT_APPLICABLE


def test_e7_is_in_the_registry_and_carries_its_own_row_fields() -> None:
    from evaluation.runner import GATE_ROW_FIELDS
    from methods.agent.validate.gate import CONDITION_DESCRIPTIONS, CONDITION_LABELS, CONDITION_ORDER

    assert CONDITION_ORDER[-2] == "problem_read_back"
    assert CONDITION_LABELS["problem_read_back"] == "E7"
    assert CONDITION_DESCRIPTIONS["problem_read_back"]
    assert "gate_E7_problem_read_back" in GATE_ROW_FIELDS
    assert "gate_E7_residual" in GATE_ROW_FIELDS


# --------------------------------------------------------------------------- E8, the question


_E8_COST_REQUEST = (
    "1 car is charging at the lot today. "
    "EV 1: arrives at midnight, leaves at 02:00, 2 kWh, 8 kW maximum. "
    "What does that cheapest plan cost for the day? Give the total in dollars, to the cent."
)
_E8_SHARE_REQUEST = _E8_COST_REQUEST.replace(
    "What does that cheapest plan cost for the day? Give the total in dollars, to the cent.",
    "Tell me what percentage of the requested energy is delivered, to two decimals.",
)


def _verify_with_question(answer: str, request: str, *, schedule=None, solve=None):
    """``verify_answer`` on the one-car day with a question attached."""
    return verify_answer(
        answer,
        solve_result=solve if solve is not None else FakeSolve(schedule=schedule if schedule is not None else optimal_schedule()),
        day=one_car_day(),
        site=one_car_site(),
        tool_outputs=[OPTIMAL_TOOL_OUTPUT],
        prior_tool_outputs=[],
        request_text=request,
        tou=cheap_then_expensive_tou(),
    )


def test_e8_passes_when_the_answer_reports_the_quantity_that_was_asked_for() -> None:
    """The cheap schedule costs $0.20 and the answer says so."""
    result = _verify_with_question("The cheapest plan costs $0.20 for the day.", _E8_COST_REQUEST)

    assert status_of(result, "answers_the_question") == PASS
    assert result.conditions["answers_the_question"].label == "E8"
    assert result.passed is True


def test_e8_catches_the_right_number_to_the_wrong_question() -> None:
    """The failure of 2026-09-28 that every other condition accepted.

    Asked for the share of the requested *energy* delivered, the agent reported
    ``pct_fully_served`` from the solver's own output: the share of *cars* that
    left full. Here the day delivers 100 % of its energy, and an answer that
    reports the day's cost instead states a number that is equally real, equally
    current, and not the one asked for.
    """
    result = _verify_with_question("The plan costs $0.20 and peaks at 8.0 kW.", _E8_SHARE_REQUEST)

    condition = result.conditions["answers_the_question"]
    assert condition.status == FAIL
    assert "100.00 %" in condition.detail
    assert result.passed is False
    # The point of the test: nothing else objects. The numbers are the last
    # solve's, they trace, and they describe the surfaced schedule.
    for name in ("solver_optimal", "no_hard_violation", "traceable", "currency", "schedule_consistency"):
        assert status_of(result, name) == PASS


def test_e8_does_not_escalate_an_answer_that_rounds() -> None:
    """The gate's tolerance is the scorer's, so rounding is not a failure.

    A reply written for a person rounds. If E8 were tighter than
    ``evaluation.outcome``, it would escalate days the scorer then counts as
    correctly answered, which is one system disagreeing with itself.
    """
    result = _verify_with_question("The cheapest plan costs about $0.2 for the day.", _E8_COST_REQUEST)

    assert status_of(result, "answers_the_question") == PASS


def test_e8_abstains_on_a_question_it_does_not_read() -> None:
    """Bounded grammar, same discipline as E7: it recognises what it knows.

    A request that prescribes an operation only, asks a yes/no, or asks about
    the day rather than the plan leaves E8 out of force, and abstaining never
    fails the gate.
    """
    for request in (
        "",
        "Plan the charging to minimise what we pay for the energy.",
        "Can every car leave with all the energy it asked for? Answer yes or no.",
        "Also tell me the total energy requested across all the cars, in kWh to two decimals.",
    ):
        result = _verify_with_question(GOOD_ANSWER, request)
        assert status_of(result, "answers_the_question") == NOT_APPLICABLE, request


def test_e8_abstains_when_two_quantities_are_asked_for_at_once() -> None:
    """An ambiguous read accuses nobody: one number cannot answer two questions."""
    from methods.agent.validate.gate import _asked_quantity

    both = (
        "What does that cheapest plan cost for the day? "
        "Tell me what percentage of the requested energy is delivered, to two decimals."
    )
    assert _asked_quantity(both) is None


def test_e8_reads_every_question_the_generator_can_ask_and_no_other() -> None:
    """E8's grammar is coupled to ``evaluation/requests.py``, and this is the coupling.

    The condition can only recompute three quantities from a schedule. It must
    recognise every phrasing the generator emits for those three, so a real run
    never leaves E8 silently out of force, and none of the others, so it never
    holds an answer to a quantity the request did not ask for. A new phrasing
    breaks this test instead of quietly disabling the condition.
    """
    import ast
    import inspect

    from evaluation import requests as reqs
    from methods.agent.validate.gate import _asked_quantity

    expected = {"cost_question": "cost", "unmet_question": "unmet_kwh", "served_share": "pct_energy_served"}
    for variant, builder in reqs._QUESTION_BUILDERS.items():
        # The phrasings are the literal list the builder hands to ``rng.choice``.
        tree = ast.parse(inspect.getsource(builder).lstrip())
        def literal(element: ast.expr) -> Optional[str]:
            """The phrasing, with any interpolated clock phrase left as a blank."""
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                return element.value
            if isinstance(element, ast.JoinedStr):
                return " ".join(
                    part.value for part in element.values
                    if isinstance(part, ast.Constant) and isinstance(part.value, str)
                )
            return None

        phrasings = [
            text
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "choice"
            for argument in node.args
            if isinstance(argument, ast.List)
            for element in argument.elts
            if (text := literal(element))
        ]
        assert phrasings or variant in reqs.STATE_VARIANTS, variant
        for text in phrasings:
            assert _asked_quantity(text) == expected.get(variant), (variant, text)


def test_e8_is_in_the_registry_and_carries_its_own_row_fields() -> None:
    from evaluation.runner import GATE_ROW_FIELDS
    from methods.agent.validate.gate import CONDITION_DESCRIPTIONS, CONDITION_LABELS, CONDITION_ORDER

    assert CONDITION_ORDER[-1] == "answers_the_question"
    assert CONDITION_LABELS["answers_the_question"] == "E8"
    assert CONDITION_DESCRIPTIONS["answers_the_question"]
    assert "gate_E8_answers_the_question" in GATE_ROW_FIELDS
    assert "gate_E8_residual" in GATE_ROW_FIELDS

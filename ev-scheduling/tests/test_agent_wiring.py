"""The evaluated agent path: the gate's loop, the problem actually posed, and what comes out.

Offline and adversarial. Every test injects a stub client that returns scripted
responses, so no API key is read and no request is ever made; the only real
computation is CVXPY, which the day here keeps to one session over eight steps.

Four things are pinned:

* the gate's three outcomes, accept / retry / declared failure, including that a
  retry really is a second answer written after the gate's own message and that a
  declared failure surfaces the gate's text with no schedule and no numbers;
* that a what-if is judged against the problem it posed. Each what-if test also
  runs the *old* check, against the base day and site, and asserts it disagrees:
  the bug was silent, so a test that only exercised the new path would have
  passed before the fix as well;
* that a retry cannot re-solve an easier problem;
* that nothing the harness needs is dropped on the way out: the token accounting,
  the run-named trace, the gate verdict, and the parsed problem.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import cvxpy as cp
import numpy as np
import pytest

from methods.agent.llm_agent import run_agent_plan_act, BLOCKED_RETRY_ERROR, run_agent_llm
from methods.agent.run import AgentResult, ClarificationResult, run_agent, run_agent_from_text
from methods.agent.validate.gate import verify_answer
from config.site import SiteConfig, TOUConfig
from solver.checker import check
from data.format.schema import DaySessions, Session
from evaluation.formulation import formulation_exact
from solver.solver import SolveResult, solve

MODEL = "openrouter:openai/gpt-4o"

# A number no solver output of this day carries, so an answer quoting it fails E3.
FABRICATED = "$123.45"


# --------------------------------------------------------------------------- stub client


class _FakeFunction:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, call_id: str, name: str, arguments: str) -> None:
        self.id = call_id
        self.type = "function"
        self.function = _FakeFunction(name, arguments)

    def model_dump(self, exclude_none: bool = False) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "function": {"name": self.function.name, "arguments": self.function.arguments},
        }


class _FakeMessage:
    def __init__(
        self,
        content: Optional[str] = None,
        tool_calls: Optional[List[_FakeToolCall]] = None,
    ) -> None:
        self.role = "assistant"
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, exclude_none: bool = False) -> Dict[str, Any]:
        out: Dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            out["tool_calls"] = [tc.model_dump(exclude_none) for tc in self.tool_calls]
        if exclude_none:
            out = {k: v for k, v in out.items() if v is not None}
        return out


class _FakeUsage:
    def __init__(self, prompt: int, completion: int) -> None:
        self.prompt_tokens = prompt
        self.completion_tokens = completion
        self.total_tokens = prompt + completion


class _FakeChoice:
    def __init__(self, message: _FakeMessage) -> None:
        self.message = message


class _FakeResponse:
    def __init__(self, message: _FakeMessage, usage: _FakeUsage) -> None:
        self.choices = [_FakeChoice(message)]
        self.usage = usage


class _FakeCompletions:
    def __init__(self, responses: List[_FakeResponse], calls: List[Dict[str, Any]]) -> None:
        self._responses = list(responses)
        self._calls = calls

    def create(self, **kwargs: Any) -> _FakeResponse:
        self._calls.append(kwargs)
        if not self._responses:
            raise AssertionError(
                "The stub client ran out of scripted responses: the loop made more "
                "model calls than this test expects."
            )
        return self._responses.pop(0)


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeClient:
    """Stub with the one method the code calls: chat.completions.create."""

    def __init__(self, responses: List[_FakeResponse]) -> None:
        self.calls: List[Dict[str, Any]] = []
        self.chat = _FakeChat(_FakeCompletions(responses, self.calls))

    @property
    def unused(self) -> int:
        """Scripted responses the run never asked for."""
        return len(self.chat.completions._responses)


def _text(content: str, prompt: int = 100, completion: int = 20) -> _FakeResponse:
    return _FakeResponse(_FakeMessage(content=content), _FakeUsage(prompt, completion))


def _tool(
    arguments: str = "{}",
    call_id: str = "call_1",
    prompt: int = 200,
    completion: int = 30,
) -> _FakeResponse:
    message = _FakeMessage(
        content=None, tool_calls=[_FakeToolCall(call_id, "solve_ev_schedule", arguments)]
    )
    return _FakeResponse(message, _FakeUsage(prompt, completion))


# --------------------------------------------------------------------------- problem


def tiny_problem():
    """One car asking 10 kWh, one cheap step, a 20 kW site cap.

    The tariff has a single cheap step, so the optimum is unique in the numbers
    that matter: fill step 0 to the cap, spread the rest. Under the 20 kW cap
    that is $3.00 at a 20 kW peak; under a 50 kW what-if cap it becomes $1.00 at
    a 40 kW peak, which is what makes the site-cap what-if test sharp.
    """
    session = Session(
        session_id="s1",
        arrival_idx=0,
        departure_idx=8,
        energy_kwh=10.0,
        charger_id="CA-322",
        max_power_kw=50.0,
    )
    day = DaySessions(sessions=[session], n_steps=8, dt_hours=0.25)
    site = SiteConfig(P_max_kw=20.0, n_steps=8, dt_hours=0.25)
    tou = TOUConfig(rates_per_kwh=np.array([0.10] + [0.50] * 7))
    return day, site, tou


def grounded_answer(day: DaySessions, site: SiteConfig, tou: TOUConfig) -> str:
    """An answer quoting exactly what the solver returns for this problem."""
    result = solve(day, site, tou)
    return (
        f"The schedule costs ${result.total_cost_usd:.2f}, peaks at "
        f"{result.peak_load_kw:.2f} kW, and leaves "
        f"{float(np.sum(result.unmet_energy_kwh)):.2f} kWh unmet."
    )


def read_trace(path: Optional[Path]) -> Dict[str, Any]:
    assert path is not None
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- accept


def test_a_verified_answer_is_surfaced_and_the_verdict_says_so(tmp_path: Path) -> None:
    """One solve, one grounded answer: the gate accepts on the first attempt."""
    day, site, tou = tiny_problem()
    answer = grounded_answer(day, site, tou)
    client = _FakeClient([_tool('{"penalty_unmet": 1000000}'), _text(answer)])

    result = run_agent_llm(
        day, site, tou, model=MODEL, client=client, run_id="2019-06-15", trace_dir=tmp_path
    )

    assert result.explanation == answer
    assert result.declared_failure is False
    assert result.gate is not None
    assert result.gate.passed is True
    assert result.gate.declared_failure is False
    assert result.gate_attempts == 1
    assert np.count_nonzero(result.schedule) > 0
    assert result.total_cost_usd == pytest.approx(3.0)
    # No second attempt: the gate accepted without another model call.
    assert result.usage.n_llm_calls == 2
    assert client.unused == 0

    # The per-condition row is stored next to the run it judged.
    payload = read_trace(result.trace_path)
    gate_row = payload["gate"]
    assert gate_row == result.gate_row
    assert gate_row["gate_passed"] is True
    assert gate_row["gate_action"] == "accept"
    assert [c["label"] for c in gate_row["conditions"].values()] == ["E1", "E2", "E3", "E4", "E5", "E6"]
    assert gate_row["conditions"]["traceable"]["status"] == "pass"
    assert gate_row["gate_E1_solver_optimal"] == "pass"


def test_an_answer_with_no_solve_skips_the_gate_rather_than_escalating(tmp_path: Path) -> None:
    """A conceptual question surfaces no schedule, so there is nothing to verify.

    ``gate`` is None, which ``classify_outcome`` reads as "no gate on this day":
    the day can never be scored as an escalation on the strength of a question
    the agent simply answered.
    """
    day, site, tou = tiny_problem()
    client = _FakeClient([_text("TOU pricing charges more during peak hours.")])

    result = run_agent_llm(
        day, site, tou, request="What is TOU pricing?", model=MODEL,
        client=client, trace_dir=tmp_path,
    )

    assert result.tool_called is False
    assert result.gate is None
    assert result.gate_row == {}
    assert result.gate_attempts == 0
    assert read_trace(result.trace_path)["status"] == "no_tool_call"


# --------------------------------------------------------------------------- retry


def test_a_failed_answer_is_handed_back_to_the_model_and_the_second_one_is_accepted(
    tmp_path: Path,
) -> None:
    """E3 fails, the gate's message becomes a user turn, the corrected answer passes."""
    day, site, tou = tiny_problem()
    good = grounded_answer(day, site, tou)
    client = _FakeClient([
        _tool(),
        _text(f"The schedule costs {FABRICATED}."),
        _text(good),
    ])

    result = run_agent_llm(
        day, site, tou, model=MODEL, client=client, run_id="2019-06-15", trace_dir=tmp_path
    )

    assert result.explanation == good
    assert result.gate is not None and result.gate.passed is True
    assert result.declared_failure is False
    assert result.gate_attempts == 2
    # One extra model call, and only one: the retry is a single second answer.
    assert result.usage.n_llm_calls == 3
    assert len(result.tool_outputs) == 1

    payload = read_trace(result.trace_path)
    user_turns = [m for m in payload["messages"] if m.get("role") == "user"]
    # The gate's own words, appended as a user turn, and nothing invented here.
    assert len(user_turns) == 2
    retry_turn = user_turns[1]["content"]
    assert retry_turn.startswith("Verification failed before this answer could be accepted.")
    assert "only on the problem as posed" in retry_turn
    assert FABRICATED in retry_turn
    assert payload["gate"]["gate_attempts"] == 2
    assert payload["gate"]["gate_passed"] is True


def test_a_second_failure_returns_the_gate_text_with_no_schedule_and_no_numbers(
    tmp_path: Path,
) -> None:
    """Two untraceable answers: the declared failure is the answer, and it carries no result."""
    day, site, tou = tiny_problem()
    client = _FakeClient([
        _tool(),
        _text(f"The schedule costs {FABRICATED}."),
        _text("On reflection the cost is $987.65."),
    ])

    result = run_agent_llm(
        day, site, tou, model=MODEL, client=client, run_id="2019-06-15", trace_dir=tmp_path
    )

    assert result.declared_failure is True
    assert result.gate is not None
    assert result.gate.passed is False
    assert result.gate.declared_failure is True
    assert result.gate_attempts == 2
    assert result.explanation.startswith("No schedule and no numbers are reported. Verification failed:")
    assert "not a claim that the day cannot be served" in result.explanation
    # No schedule, and none of the solve's numbers.
    assert np.count_nonzero(result.schedule) == 0
    assert result.total_cost_usd == 0.0
    assert result.peak_load_kw == 0.0
    assert result.unmet_energy_kwh == 0.0
    assert result.feasible is False
    assert "3.00" not in result.explanation and "20.0" not in result.explanation

    payload = read_trace(result.trace_path)
    assert payload["status"] == "declared_failure"
    assert payload["answer"] == result.explanation
    assert payload["gate"]["gate_declared_failure"] is True
    assert payload["gate"]["conditions"]["traceable"]["status"] == "fail"


def test_an_empty_second_answer_is_not_a_second_chance_taken(tmp_path: Path) -> None:
    """A retry that writes nothing leaves the first verdict standing and declares it."""
    day, site, tou = tiny_problem()
    client = _FakeClient([
        _tool(),
        _text(f"The schedule costs {FABRICATED}."),
        _text(""),
    ])

    result = run_agent_llm(day, site, tou, model=MODEL, client=client, trace_dir=tmp_path)

    assert result.declared_failure is True
    assert result.gate is not None and result.gate.declared_failure is True
    assert np.count_nonzero(result.schedule) == 0


# --------------------------------------------------------------------------- what-if


def test_a_site_cap_what_if_is_judged_against_the_cap_that_was_solved(tmp_path: Path) -> None:
    """The bug: the 50 kW solve was checked against the 20 kW base cap.

    The solver is asked for a 50 kW cap and returns a 40 kW peak. Checking that
    schedule against the base site reports a 20 kW site-cap violation that does
    not exist in the problem posed, which is what ``feasible`` used to carry.
    """
    day, site, tou = tiny_problem()
    client = _FakeClient([
        _tool('{"site_cap_kw": 50}'),
        _text("The lifted cap lets the whole session charge in the cheap step."),
    ])

    result = run_agent_llm(
        day, site, tou,
        request="What if the site cap were 50 kW?",
        model=MODEL, client=client, run_id="2019-06-15", trace_dir=tmp_path,
    )

    # The problem that was solved comes back with the result.
    assert result.posed_site is not None and result.posed_site.P_max_kw == 50.0
    assert site.P_max_kw == 20.0, "the base site must not be mutated"
    assert result.peak_load_kw == pytest.approx(40.0)

    # What the old code did: check the 50 kW schedule against the 20 kW site.
    old = check(result.schedule, day, site)
    assert old.feasible is False
    assert [v.kind for v in old.violations] == ["site_cap"] * len(old.violations)
    assert old.max_violation_kw == pytest.approx(20.0)

    # What it does now: check it against the site that was solved.
    assert result.check_result is not None
    assert result.check_result.feasible is True
    assert result.check_result.no_hard_violation is True
    assert result.feasible is True

    # And the gate agreed, on the same posed problem.
    assert result.gate is not None and result.gate.passed is True
    assert result.gate_row["gate_E2_no_hard_violation"] == "pass"


def test_an_extra_session_what_if_is_judged_against_the_day_that_was_solved(
    tmp_path: Path,
) -> None:
    """The bug: a two-row schedule was checked against a one-session day.

    The check loops over the day's sessions, so the injected car's row was never
    read: its power vanished from the peak and its energy from the unmet total,
    and the gate's E1 would have called the schedule the wrong shape for the day.
    """
    day, site, tou = tiny_problem()
    extra = '{"extra_sessions": [{"arrival_idx": 0, "departure_idx": 8, "energy_kwh": 4.0, "max_power_kw": 10.0}]}'
    client = _FakeClient([
        _tool(extra),
        _text("Adding the second car keeps the site within its cap."),
    ])

    result = run_agent_llm(
        day, site, tou,
        request="What if another EV arrives needing 4 kWh?",
        model=MODEL, client=client, run_id="2019-06-15", trace_dir=tmp_path,
    )

    assert result.posed_day is not None
    assert len(result.posed_day.sessions) == 2
    assert len(day.sessions) == 1, "the base day must not be mutated"
    assert result.schedule.shape == (2, 8)

    # What the old code did: check two rows against a one-session day. It does
    # not fail, it silently reads only the first row and under-reports the peak.
    old = check(result.schedule, day, site)
    assert result.check_result is not None
    assert old.peak_load_kw < result.check_result.peak_load_kw
    assert result.check_result.peak_load_kw == pytest.approx(20.0)

    # And the gate: against the base day E1 rejects the shape, against the posed
    # day it passes. The wired loop uses the posed day.
    against_base = verify_answer(
        result.explanation,
        solve_result=SolveResult(
            schedule=result.schedule,
            total_cost_usd=result.total_cost_usd,
            unmet_energy_kwh=np.zeros(2),
            peak_load_kw=result.peak_load_kw,
            success=True,
            status=cp.OPTIMAL,
        ),
        day=day,
        site=site,
        tool_outputs=result.tool_outputs,
        tou=tou,
    )
    assert against_base.passed is False
    assert against_base.conditions["solver_optimal"].status == "fail"
    assert "different problem" in against_base.conditions["solver_optimal"].detail
    assert result.gate is not None and result.gate.passed is True


# --------------------------------------------------------------------------- guarded retry


def test_a_retry_that_introduces_a_what_if_is_blocked(tmp_path: Path) -> None:
    """The second attempt may not reach a passing answer by changing the question."""
    day, site, tou = tiny_problem()
    client = _FakeClient([
        _tool("{}"),
        _text(f"The schedule costs {FABRICATED}."),
        _tool('{"site_cap_kw": 999}', call_id="call_2"),
        _text("I cannot improve on the schedule the solver returned."),
    ])

    result = run_agent_llm(day, site, tou, model=MODEL, client=client, trace_dir=tmp_path)

    # The blocked call never reached the solver.
    assert len(result.tool_outputs) == 1
    assert result.posed_site is not None and result.posed_site.P_max_kw == 20.0

    # It is recorded, not swallowed: a blocked retry is visible in the trace.
    payload = read_trace(result.trace_path)
    tool_records = [t for r in payload["trace"]["rounds"] for t in r["tools"]]
    assert len(tool_records) == 2
    blocked = json.loads(tool_records[1]["output"])
    assert blocked["error"] == BLOCKED_RETRY_ERROR
    assert blocked["blocked_arguments"] == {"site_cap_kw": 999}
    assert result.usage.n_tool_calls == 2


def test_a_retry_may_re_solve_the_problem_as_posed(tmp_path: Path) -> None:
    """Only a *new* override is blocked; solving the same problem again is allowed."""
    day, site, tou = tiny_problem()
    good = grounded_answer(day, site, tou)
    client = _FakeClient([
        _tool('{"penalty_unmet": 1000000}'),
        _text(f"The schedule costs {FABRICATED}."),
        _tool('{"penalty_unmet": 1000000}', call_id="call_2"),
        _text(good),
    ])

    result = run_agent_llm(day, site, tou, model=MODEL, client=client, trace_dir=tmp_path)

    assert len(result.tool_outputs) == 2
    assert result.gate is not None and result.gate.passed is True
    assert result.explanation == good
    assert BLOCKED_RETRY_ERROR not in json.dumps(read_trace(result.trace_path))


# --------------------------------------------------------------------------- solver status


def test_an_optimal_solve_keeps_its_status() -> None:
    """Success is unchanged, and the status string now says which optimum it was."""
    day, site, tou = tiny_problem()
    result = solve(day, site, tou)

    assert result.success is True
    assert result.status == cp.OPTIMAL
    assert result.optimal_exact is True
    assert result.inaccurate is False


def test_an_inaccurate_optimum_still_succeeds_but_is_distinguishable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """OPTIMAL_INACCURATE keeps success True, as before, and is no longer invisible."""

    class _InaccurateProblem(cp.Problem):
        """A real solve reporting the status CVXPY uses for a degraded optimum."""

        @property
        def status(self) -> str:
            return cp.OPTIMAL_INACCURATE

    monkeypatch.setattr(cp, "Problem", _InaccurateProblem)

    day, site, tou = tiny_problem()
    result = solve(day, site, tou)

    assert result.success is True, "existing callers must keep their schedule"
    assert result.message is None
    assert result.status == cp.OPTIMAL_INACCURATE
    assert result.optimal_exact is False
    assert result.inaccurate is True
    assert np.count_nonzero(result.schedule) > 0

    # The agent passes it on, so the trace says the optimum was a degraded one.
    client = _FakeClient([_tool(), _text("The solver returned a schedule.")])
    agent = run_agent_llm(day, site, tou, model=MODEL, client=client, trace_dir=tmp_path)
    assert agent.tool_outputs[0]["solver_status"] == cp.OPTIMAL_INACCURATE
    assert agent.tool_outputs[0]["solver_inaccurate"] is True


def test_a_failed_solve_keeps_both_its_message_and_its_status() -> None:
    """An infeasible problem: success False and message unchanged, status added."""
    session = Session(
        session_id="s1", arrival_idx=0, departure_idx=1, energy_kwh=10.0,
        charger_id="CA-322", max_power_kw=1.0,
    )
    day = DaySessions(sessions=[session], n_steps=2, dt_hours=0.25)
    site = SiteConfig(P_max_kw=-1.0, n_steps=2, dt_hours=0.25)
    tou = TOUConfig(rates_per_kwh=np.array([0.1, 0.1]))

    result = solve(day, site, tou)

    assert result.success is False
    assert result.message == result.status
    assert result.status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE)


# --------------------------------------------------------------------------- run_agent


def test_run_agent_carries_the_accounting_and_names_the_trace_by_the_run(
    tmp_path: Path,
) -> None:
    """A harness calling run_agent gets tokens, the model id, the gate, and a day-named trace."""
    day, site, tou = tiny_problem()
    answer = grounded_answer(day, site, tou)
    client = _FakeClient([_tool(prompt=2400, completion=25), _text(answer, prompt=2600, completion=90)])

    result = run_agent(
        day, site, tou,
        request="Minimize energy cost for this day.",
        model=MODEL, client=client, run_id="2019-06-15", trace_dir=tmp_path,
    )

    assert isinstance(result, AgentResult)
    assert result.model == MODEL
    assert result.usage.n_llm_calls == 2
    assert result.usage.n_tool_calls == 1
    assert result.usage.prompt_tokens == 5000
    assert result.usage.completion_tokens == 115
    assert result.usage.total_tokens == 5115
    assert result.usage.wall_time_s > 0.0

    # Named by the day, not by the clock, so a harness can find the day's trace.
    assert result.trace_path == tmp_path / "agent" / "openrouter_openai_gpt-4o" / "2019-06-15.json"
    assert result.trace_path.exists()

    # The gate verdict travels with it, ready for classify_outcome.
    assert result.gate is not None and result.gate.passed is True
    assert result.gate_row["gate_passed"] is True
    assert result.tool_called is True
    assert result.check_result is not None
    assert result.posed_day is day
    assert result.total_usage().total_tokens == 5115


def test_run_agent_still_reaches_the_six_legacy_values() -> None:
    """The AgentLLMResult tuple protocol run_agent used to rely on is untouched."""
    day, site, tou = tiny_problem()
    client = _FakeClient([_tool(), _text("Done.")])

    schedule, cost, peak, unmet, feasible, explanation = run_agent_llm(
        day, site, tou, model=MODEL, client=client, write_trace=False
    )

    assert schedule.shape == (1, 8)
    assert cost == pytest.approx(3.0)
    assert peak == pytest.approx(20.0)
    assert unmet == pytest.approx(0.0, abs=1e-6)
    assert feasible is True
    assert explanation == "Done."


# --------------------------------------------------------------------------- run_agent_from_text


_PARSED_JSON = json.dumps({
    "sessions": [{
        "session_id": "EV-1",
        "arrival_hour": 18.0,
        "departure_hour": 22.0,
        "energy_kwh": 20.0,
        "max_power_kw": 7.0,
    }],
    "site_cap_kw": 50.0,
    "peak_price": 0.45,
    "off_peak_price": 0.12,
})

_USER_TEXT = "EV-1 arrives at 6 pm, leaves at 10 pm, and needs 20 kWh."


def test_run_agent_from_text_returns_the_parsed_problem_and_both_usages(
    tmp_path: Path,
) -> None:
    """The NL entry point is a first-class path: parsed problem, usage, traces, gate."""
    client = _FakeClient([
        _text(_PARSED_JSON, prompt=300, completion=60),      # the parse
        _tool(prompt=900, completion=20),                     # the solve
        _text("The car charges in the cheapest hours before it leaves.", prompt=950, completion=40),
    ])

    result = run_agent_from_text(
        _USER_TEXT, model=MODEL, client=client, run_id="2019-06-15", trace_dir=tmp_path
    )

    assert isinstance(result, AgentResult)

    # The parsed problem comes back, so formulation can be scored against truth.
    problem = result.parsed_problem
    assert problem is not None
    assert len(problem.sessions) == 1
    assert problem.sessions[0].arrival_hour == 18.0
    assert problem.sessions[0].energy_kwh == 20.0
    truth = DaySessions(
        sessions=[Session(
            session_id="EV-1", arrival_idx=72, departure_idx=88,
            energy_kwh=20.0, charger_id="charger-1", max_power_kw=7.0,
        )],
        n_steps=96,
        dt_hours=0.25,
    )
    assert formulation_exact(problem, truth).formulation_exact is True

    # Both steps are billed, and each writes its own trace under the run's name.
    assert result.parse_usage is not None
    assert result.parse_usage.n_llm_calls == 1
    assert result.usage.n_llm_calls == 2
    assert result.total_usage().n_llm_calls == 3
    assert result.total_usage().total_tokens == 300 + 60 + 900 + 20 + 950 + 40
    assert result.parse_trace_path == tmp_path / "parse" / "openrouter_openai_gpt-4o" / "2019-06-15.json"
    assert result.trace_path == tmp_path / "agent" / "openrouter_openai_gpt-4o" / "2019-06-15.json"
    assert result.parse_trace_path.exists()

    # The gate ran on this path too.
    assert result.gate is not None and result.gate.passed is True
    assert result.parse is not None and result.parse.model == MODEL
    assert client.unused == 0


def test_run_agent_from_text_reports_a_missing_field_without_spending_the_agent_call(
    tmp_path: Path,
) -> None:
    """An incomplete problem stops at the parse, and its cost still comes back."""
    incomplete = json.dumps({"sessions": [{"session_id": "EV-1", "arrival_hour": 18.0,
                                           "departure_hour": None, "energy_kwh": None}]})
    client = _FakeClient([_text(incomplete), _text(incomplete)])

    result = run_agent_from_text(
        "EV-1 shows up at 6 pm.", model=MODEL, client=client,
        run_id="2019-06-15", trace_dir=tmp_path, allow_inference=False,
    )

    assert isinstance(result, ClarificationResult)
    assert result.missing_fields
    assert result.usage.n_llm_calls == 1
    assert result.model == MODEL
    assert result.trace_path == tmp_path / "parse" / "openrouter_openai_gpt-4o" / "2019-06-15.json"


def test_the_parser_asks_config_llm_for_its_key_and_says_which_one_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No key, no quiet fallback: the error names the key this project actually uses.

    The parser used to build an OpenAI client from OPENAI_API_KEY, which this
    project never sets, so the natural-language path could not run at all.
    """
    from methods.agent.parse.parse import parse_nl_problem

    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError) as excinfo:
        parse_nl_problem(_USER_TEXT, model=MODEL)

    assert "OPENROUTER_API_KEY" in str(excinfo.value)


# --------------------------------------------------------------------------- no gate


def test_without_the_gate_the_first_answer_goes_out_as_written(tmp_path: Path) -> None:
    """The ReAct row: same loop, same tool, and an answer nobody checks.

    The scripted answer quotes numbers the solver never returned. Behind the
    gate that is an E3 failure and a retry; without it, it is the answer.
    """
    day, site, tou = tiny_problem()
    wrong = "The schedule costs $99.00, peaks at 1.00 kW, and leaves 0.00 kWh unmet."
    client = _FakeClient([_tool('{"penalty_unmet": 1000000}'), _text(wrong)])

    result = run_agent_llm(
        day, site, tou, model=MODEL, client=client, run_id="2019-06-15", trace_dir=tmp_path, gate=False
    )

    assert result.explanation == wrong
    assert result.gate is None
    assert result.gate_attempts == 0
    assert result.declared_failure is False
    assert result.tool_called is True
    assert np.count_nonzero(result.schedule) > 0
    assert result.total_cost_usd == pytest.approx(3.0)  # the solver's, whatever the prose says
    # Two calls and not one more: no verdict was handed back to the model.
    assert result.usage.n_llm_calls == 2
    assert client.unused == 0

    payload = read_trace(result.trace_path)
    assert payload["gate"]["gate_passed"] is None
    assert payload["gate"]["gate_action"] == "none"
    assert payload["gate"] == result.gate_row


def test_the_same_scripted_run_is_a_retry_behind_the_gate(tmp_path: Path) -> None:
    """The control for the test above: with the gate on, the same answer is not accepted."""
    day, site, tou = tiny_problem()
    wrong = "The schedule costs $99.00, peaks at 1.00 kW, and leaves 0.00 kWh unmet."
    client = _FakeClient([_tool('{"penalty_unmet": 1000000}'), _text(wrong), _text(grounded_answer(day, site, tou))])

    result = run_agent_llm(
        day, site, tou, model=MODEL, client=client, run_id="2019-06-15", trace_dir=tmp_path
    )

    assert result.gate is not None and result.gate.passed is True
    assert result.gate_attempts == 2
    assert result.usage.n_llm_calls == 3


# --------------------------------------------------------------------------- plan-and-act


def test_plan_and_act_plans_everything_before_any_result_exists(tmp_path: Path) -> None:
    """Three calls, no tools offered to the model, the plan executed as written."""
    day, site, tou = tiny_problem()
    plan = '{"plan": [{"tool": "solve_ev_schedule", "args": {"penalty_unmet": 1000000}}]}'
    answer = grounded_answer(day, site, tou)
    client = _FakeClient([_text(plan), _text(answer)])

    result = run_agent_plan_act(
        day, site, tou, model=MODEL, client=client, run_id="2019-06-15", trace_dir=tmp_path
    )

    assert result.explanation == answer
    assert result.gate is None and result.gate_attempts == 0
    assert result.tool_called is True
    assert np.count_nonzero(result.schedule) > 0
    assert result.total_cost_usd == pytest.approx(3.0)
    assert result.usage.n_llm_calls == 2 and result.usage.n_tool_calls == 1
    assert client.unused == 0
    # the model was never offered a tool: both calls went out without a tools argument
    assert all(not call.get("tools") for call in client.calls)
    # the planned call is in the trace where the rescore reads tool calls from
    payload = read_trace(result.trace_path)
    calls = [c for r in payload["trace"]["rounds"] for c in r.get("tools", [])]
    assert [c["name"] for c in calls] == ["solve_ev_schedule"]
    assert payload["gate"]["gate_action"] == "none"


def test_a_plan_that_is_not_json_executes_nothing(tmp_path: Path) -> None:
    day, site, tou = tiny_problem()
    client = _FakeClient([_text("I would first look at the cars and then decide.")])

    result = run_agent_plan_act(day, site, tou, model=MODEL, client=client, run_id="x", trace_dir=tmp_path)

    assert result.tool_called is False
    assert np.count_nonzero(result.schedule) == 0
    assert result.usage.n_llm_calls == 1 and client.unused == 0

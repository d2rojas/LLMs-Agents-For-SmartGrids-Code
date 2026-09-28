"""Every method runs end to end on one benchmark request with a scripted model, and the scorer reads the result.

No API key. The request is turbine 8, days 201 to 214, 3 h ahead, with the peak-hour
question. The scripted model either copies a tool's series (a solved run), writes its
own numbers while claiming a tool (wrong, unflagged without the gate; escalated with
it), or declares it cannot forecast (escalated).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import methods  # noqa: E402
from config import ModelSpec  # noqa: E402
from evaluation import scoring  # noqa: E402
from evaluation.requests import generate_requests, window_for  # noqa: E402
from methods.common import Context  # noqa: E402
from solver.tools import ToolDispatcher  # noqa: E402
from tests.fake_client import FakeClient, answer_json  # noqa: E402

SPEC = ModelSpec("openrouter", "openai/fake")
ARGS = {"turbine": 8, "history_end_day": 214, "horizon_hours": 3}


@pytest.fixture(scope="module")
def req():
    reqs = generate_requests(instance_ids=["t008-d201"], horizons=(3,), questions=("peak_hour",), seed=0)
    assert len(reqs) == 1
    return reqs[0]


@pytest.fixture(scope="module")
def window(req):
    return window_for(req)


@pytest.fixture(scope="module")
def gru_series(window):
    d = ToolDispatcher(window)
    out = d.call("gru_forecast", ARGS)
    assert out.get("forecast") and len(out["forecast"]) == 18, out
    return out["forecast"]


def ctx_for(req, window, client, **kw) -> Context:
    return Context(request_id=req.request_id, text=req.text, window=window, horizon_hours=req.horizon_hours, spec=SPEC, client=client, **kw)


def score(req, window, run):
    return scoring.score_run(run, req=req, window=window, has_tools=bool(methods.card(run.method)["uses_tools"]))


def peak_hour(series):
    from methods.agent.gate import derive_answer

    return derive_answer("peak_hour", series)


def test_request_and_window(req, window):
    assert req.turbine == 8 and req.history_days == [201, 214] and req.horizon_hours == 3
    assert window.history_end_day == 214 and len(window.history()) == 14 * 144
    assert len(window.target(3)) == 18 and len(window.target(48)) == 288


def test_tools_refuse_another_window(window):
    d = ToolDispatcher(window)
    assert "error" in d.call("gru_forecast", {"turbine": 9, "history_end_day": 214, "horizon_hours": 3})
    assert "error" in d.call("gru_forecast", {"turbine": 8, "history_end_day": 200, "horizon_hours": 3})
    assert "error" in d.call("gru_forecast", {"turbine": 8, "history_end_day": 214})  # missing horizon
    assert d.n_calls == 3


def test_rule_based_is_solved_and_traceable(req, window):
    from methods.deterministic.rule_based import run_rule_based

    run = run_rule_based(ctx_for(req, window, None))
    s = score(req, window, run)
    assert s["common_outcome"] == "solved", s["common_reason"]
    assert s["common_formulation_exact"] is True and s["common_traceable"] is True
    assert s["common_mae"] is not None and s["common_answer_ok"] is True
    assert run.n_llm_calls == 0 and run.n_tool_calls == 2


def test_rule_based_escalates_what_it_cannot_parse(req, window):
    from methods.deterministic.rule_based import run_rule_based

    ctx = ctx_for(req, window, None)
    ctx.text = "Give me the two-day power outlook for the eighth machine, please."
    run = run_rule_based(ctx)
    s = score(req, window, run)
    assert s["common_outcome"] == "escalated" and "cannot parse" in s["common_escalation_reason"]


def test_react_solved_when_the_model_copies_a_tool(req, window, gru_series):
    from methods.agent.loop import run_react

    client = FakeClient([
        [("get_history_summary", {"turbine": 8, "history_end_day": 214})],
        [("gru_forecast", ARGS)],
        answer_json(series=gru_series, answer=peak_hour(gru_series)),
    ])
    run = run_react(ctx_for(req, window, client), gate=False, question_kind=req.question)
    s = score(req, window, run)
    assert s["common_outcome"] == "solved", s["common_reason"]
    assert run.n_llm_calls == 3 and run.n_tool_calls == 2
    assert s["common_source_call"]["name"] == "gru_forecast"


def test_react_wrong_unflagged_when_the_series_is_invented(req, window, gru_series):
    from methods.agent.loop import run_react

    invented = [float(v) + 37.0 for v in gru_series]
    client = FakeClient([[("gru_forecast", ARGS)], answer_json(series=invented, answer=peak_hour(invented))])
    run = run_react(ctx_for(req, window, client), gate=False, question_kind=req.question)
    s = score(req, window, run)
    assert s["common_outcome"] == "wrong_unflagged" and "matches no forecast-tool output" in s["common_reason"]


def test_windagent_gate_catches_the_invented_series_and_escalates(req, window, gru_series):
    from methods.agent.loop import run_react

    invented = [float(v) + 37.0 for v in gru_series]
    client = FakeClient([
        [("gru_forecast", ARGS)],
        answer_json(series=invented, answer=peak_hour(invented)),   # W3 fails
        answer_json(series=invented, answer=peak_hour(invented)),   # retry, same -> declared failure
    ])
    run = run_react(ctx_for(req, window, client), gate=True, question_kind=req.question)
    assert run.gate is not None and not run.gate["passed"] and "traceable" in run.gate["failed"]
    s = score(req, window, run)
    assert s["common_outcome"] == "escalated" and "gate rejected" in run.harness_declared
    assert run.answer.status == "cannot_forecast" and run.answer.forecast == []


def test_windagent_gate_passes_a_copied_series_after_a_retry(req, window, gru_series):
    from methods.agent.loop import run_react

    client = FakeClient([
        [("gru_forecast", ARGS)],
        answer_json(series=gru_series, answer=99),                       # W5 fails: answer contradicts the series
        answer_json(series=gru_series, answer=peak_hour(gru_series)),    # fixed on the retry
    ])
    run = run_react(ctx_for(req, window, client), gate=True, question_kind=req.question)
    assert run.trace["gate_history"][0]["failed"] == ["coherent"]
    assert run.gate["passed"]
    assert score(req, window, run)["common_outcome"] == "solved"


def test_windagent_accepts_the_mean_of_two_tools(req, window):
    from methods.agent.loop import run_react

    d = ToolDispatcher(window)
    a = d.call("gru_forecast", ARGS)["forecast"]
    b = d.call("persistence_forecast", ARGS)["forecast"]
    mean = [(x + y) / 2 for x, y in zip(a, b)]
    client = FakeClient([[("gru_forecast", ARGS), ("persistence_forecast", ARGS)], answer_json(series=mean, source="mean_of_tools", answer=peak_hour(mean))])
    run = run_react(ctx_for(req, window, client), gate=True, question_kind=req.question)
    assert run.gate["passed"], run.gate["failed"]
    assert score(req, window, run)["common_outcome"] == "solved"


def test_plan_act_executes_the_plan_then_answers(req, window, gru_series):
    from methods.agent.plan_act import run_plan_act

    plan = json.dumps({"reading": "turbine 8, days 201-214, 3 h", "plan": [
        {"tool": "get_history_summary", "args": {"turbine": 8, "history_end_day": 214}}, {"tool": "gru_forecast", "args": ARGS}]})
    run = run_plan_act(ctx_for(req, window, FakeClient([plan, answer_json(series=gru_series, answer=peak_hour(gru_series))])))
    assert run.n_llm_calls == 2 and run.n_tool_calls == 2
    assert score(req, window, run)["common_outcome"] == "solved"


def test_llm_only_is_solved_on_a_valid_series_but_never_traceable(req, window):
    from methods.prompting.llm_only import run_llm_only

    series = [100.0 + i for i in range(18)]
    run = run_llm_only(ctx_for(req, window, FakeClient([answer_json(series=series, source="own_computation", answer=peak_hour(series))])), strategy="structured")
    s = score(req, window, run)
    assert run.n_llm_calls == 1 and run.n_tool_calls == 0
    assert s["common_outcome"] == "solved" and s["common_traceable"] is False and s["common_mae"] is not None
    # the history really was in the prompt
    assert "## SCADA history" in run.trace["messages"][1]["content"]


def test_llm_only_wrong_length_is_wrong_unflagged(req, window):
    from methods.prompting.llm_only import run_llm_only

    run = run_llm_only(ctx_for(req, window, FakeClient(["reasoning...\nFINAL ANSWER:\n" + answer_json(series=[100.0] * 17, source="own_computation", answer=1)])), strategy="cot")
    s = score(req, window, run)
    assert s["common_outcome"] == "wrong_unflagged" and "17 values" in s["common_reason"]
    assert s["common_mae"] is None   # a short series is not scored on its first values


def test_out_of_range_value_is_wrong_unflagged(req, window):
    from methods.prompting.llm_only import run_llm_only

    series = [100.0] * 17 + [2500.0]
    run = run_llm_only(ctx_for(req, window, FakeClient([answer_json(series=series, source="own_computation", answer=peak_hour(series))])), strategy="structured")
    assert score(req, window, run)["common_outcome"] == "wrong_unflagged"


def test_declared_failure_is_escalated(req, window):
    from methods.prompting.llm_only import run_llm_only

    run = run_llm_only(ctx_for(req, window, FakeClient([answer_json(status="cannot_forecast", forecast=[], cannot_forecast="history incomplete", answer=None)])), strategy="structured")
    assert score(req, window, run)["common_outcome"] == "escalated"


def test_stress_condition_expects_an_escalation(req):
    from methods.deterministic.rule_based import run_rule_based
    from methods.prompting.llm_only import run_llm_only
    from evaluation.requests import generate_requests

    sreq = generate_requests(instance_ids=["t008-d201"], horizons=(3,), questions=("peak_hour",), seed=0, condition="stress")[0]
    w = window_for(sreq)
    assert w.history_valid_rows_per_day()[214] == 0
    run = run_rule_based(ctx_for(sreq, w, None))
    s = score(sreq, w, run)
    assert s["common_outcome"] == "solved" and "correctly escalated" in s["common_reason"]
    series = [100.0] * 18
    run2 = run_llm_only(ctx_for(sreq, w, FakeClient([answer_json(series=series, source="own_computation", answer=1)])), strategy="structured")
    assert score(sreq, w, run2)["common_outcome"] == "wrong_unflagged"


def test_budget_exhaustion_ends_in_a_declared_failure(req, window):
    from methods.agent.loop import run_react

    client = FakeClient([[("get_history_summary", {"turbine": 8, "history_end_day": 214})]] * 30)
    run = run_react(ctx_for(req, window, client, max_llm_calls=4, max_tool_calls=3), gate=False, question_kind=req.question)
    assert run.budget_exhausted
    assert score(req, window, run)["common_outcome"] == "escalated"


def test_gate_rejection_followed_by_budget_exhaustion_escalates(req, window, gru_series):
    from methods.agent.loop import run_react

    invented = [float(v) + 37.0 for v in gru_series]
    # one rejected answer, then the model keeps calling tools until the model-call budget ends
    client = FakeClient([[("gru_forecast", ARGS)], answer_json(series=invented, answer=1),
                         [("get_history_summary", {"turbine": 8, "history_end_day": 214})]] * 4)
    run = run_react(ctx_for(req, window, client, max_llm_calls=3), gate=True, question_kind=req.question)
    assert not run.gate["passed"] and run.budget_exhausted
    s = score(req, window, run)
    assert s["common_outcome"] == "escalated" and "budget exhausted" in run.harness_declared
    assert run.answer.forecast == []


def test_duplicate_tool_calls_are_refused_and_not_charged(window):
    d = ToolDispatcher(window, max_calls=3)
    assert d.call("gru_forecast", ARGS).get("forecast")
    out = d.call("gru_forecast", ARGS)
    assert "identical to call 1" in out["error"]
    assert d.n_calls == 2 and d.n_charged == 1 and not d.exhausted
    assert d.call("persistence_forecast", ARGS).get("forecast") and d.call("power_curve_forecast", ARGS).get("forecast")
    assert d.exhausted


def test_llm_only_prompt_carries_the_data_check(req, window):
    from methods.common import Context, user_message
    from config import ModelSpec

    ctx = Context(request_id=req.request_id, text=req.text, window=window, horizon_hours=3, spec=ModelSpec("none", "x"))
    msg = user_message(ctx, history=True)
    assert "Data check: 14 days" in msg and "The history is complete." in msg

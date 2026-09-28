"""Every method runs end to end on one scenario with a scripted model, and the scorer reads the result.

No API key. The scenario is the IEEE-14 line contingency (line 9 out); the
scripted model either restores it (a solved run), claims a repair it did not
make (wrong, unflagged), or declares it cannot (escalated). The gate is
exercised on the claim the solver contradicts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import ModelSpec  # noqa: E402
from evaluation import scoring  # noqa: E402
from evaluation.requests import build_request, fresh_network  # noqa: E402
from methods.common import Context  # noqa: E402
from tests.fake_client import FakeClient, answer_json  # noqa: E402

SPEC = ModelSpec("openrouter", "openai/fake")


@pytest.fixture(scope="module")
def req():
    return build_request("case14", "line_contingency_overload")


def ctx_for(req, client, **kw) -> Context:
    return Context(request_id=req.request_id, text=req.text, evidence_text=req.evidence_text, net=fresh_network(req),
                   base_keys=req.base_keys, spec=SPEC, client=client, **kw)


def score(req, run):
    return scoring.score_run(run, injected=req.injected, initial=req.initial, base_keys=req.base_keys,
                             evidence_text=req.evidence_text, request_text=req.text)


def test_scenario_is_a_real_contingency(req):
    assert req.initial.converged and req.initial.n_new and req.initial.n_new > 0
    assert req.injected.fault_type == "line_outage" and req.injected.components == {"line": [9]}


def test_rule_based_restores_the_line_and_is_solved(req):
    from methods.deterministic.rule_based import run_rule_based

    run = run_rule_based(ctx_for(req, None))
    s = score(req, run)
    assert s["common_outcome"] == "solved", s["common_reason"]
    assert s["common_formulation_exact"] is True
    assert run.n_llm_calls == 0 and run.n_tool_calls > 0


def test_react_solved_when_the_model_repairs_and_reports_honestly(req):
    from methods.agent.loop import run_react

    client = FakeClient([
        [("switch_element", {"element_type": "line", "element_index": 9, "in_service": True})],
        [("run_power_flow", {}), ("check_overloads", {}), ("check_voltage_violations", {}), ("find_disconnected_areas", {})],
        answer_json(),
    ])
    run = run_react(ctx_for(req, client), gate=False)
    s = score(req, run)
    assert s["common_outcome"] == "solved", s["common_reason"]
    assert run.n_llm_calls == 3 and run.n_tool_calls == 5


def test_react_wrong_unflagged_when_the_claim_contradicts_the_solver(req):
    from methods.agent.loop import run_react

    client = FakeClient([
        [("run_power_flow", {})],
        answer_json(actions=[], summary="Nothing was wrong; the network is secure."),
    ])
    run = run_react(ctx_for(req, client), gate=False)
    s = score(req, run)
    assert s["common_outcome"] == "wrong_unflagged"
    assert "not secure" in s["common_reason"] or "violation" in s["common_reason"]


def test_griddebug_gate_catches_the_false_claim_and_escalates(req):
    from methods.agent.loop import run_react

    client = FakeClient([
        [("run_power_flow", {})],
        answer_json(actions=[], summary="The network is secure."),   # gate: secure_or_declared, consistent fail
        answer_json(actions=[], summary="Still secure."),            # retry, same false claim -> declared failure
    ])
    run = run_react(ctx_for(req, client), gate=True)
    assert run.gate is not None and not run.gate["passed"]
    assert "secure_or_declared" in run.gate["failed"] and "consistent" in run.gate["failed"]
    s = score(req, run)
    assert s["common_outcome"] == "escalated"
    assert run.harness_declared and "gate rejected" in run.harness_declared
    assert run.answer.status == "cannot_repair"


def test_griddebug_gate_passes_a_true_repair(req):
    from methods.agent.loop import run_react

    client = FakeClient([
        [("switch_element", {"element_type": "line", "element_index": 9, "in_service": True}), ("run_power_flow", {}),
         ("check_overloads", {}), ("check_voltage_violations", {}), ("find_disconnected_areas", {})],
        answer_json(),
    ])
    run = run_react(ctx_for(req, client), gate=True)
    assert run.gate["passed"], run.gate["failed"]
    assert score(req, run)["common_outcome"] == "solved"


def test_griddebug_currency_fails_when_acting_after_the_last_power_flow(req):
    from methods.agent.loop import run_react

    client = FakeClient([
        [("run_power_flow", {}), ("switch_element", {"element_type": "line", "element_index": 9, "in_service": True})],
        answer_json(),
        [("run_power_flow", {}), ("check_overloads", {})],
        answer_json(),
    ])
    run = run_react(ctx_for(req, client), gate=True)
    assert run.trace["gate_history"][0]["failed"] == ["currency"]
    assert run.gate["passed"]
    assert score(req, run)["common_outcome"] == "solved"


def test_plan_act_executes_the_plan_then_answers(req):
    from methods.agent.plan_act import run_plan_act

    plan = '{"diagnosis": "line 9 out", "plan": [{"tool": "switch_element", "args": {"element_type": "line", "element_index": 9, "in_service": true}}, {"tool": "run_power_flow", "args": {}}, {"tool": "check_overloads", "args": {}}]}'
    run = run_plan_act(ctx_for(req, FakeClient([plan, answer_json()])))
    assert run.n_llm_calls == 2 and run.n_tool_calls == 3
    assert score(req, run)["common_outcome"] == "solved"


def test_llm_only_actions_are_applied_by_the_harness(req):
    from methods.prompting.llm_only import run_llm_only

    run = run_llm_only(ctx_for(req, FakeClient([answer_json()])), strategy="structured")
    assert run.n_llm_calls == 1 and run.n_tool_calls == 0
    assert any(e.get("harness") for e in run.tool_log)
    assert score(req, run)["common_outcome"] == "solved"

    run2 = run_llm_only(ctx_for(req, FakeClient(["reasoning first...\nFINAL ANSWER:\n" + answer_json(actions=[])])), strategy="cot")
    s = score(req, run2)
    assert s["common_outcome"] == "wrong_unflagged"   # claimed repaired, did nothing


def test_declared_failure_is_escalated(req):
    from methods.prompting.llm_only import run_llm_only

    run = run_llm_only(ctx_for(req, FakeClient([answer_json(status="cannot_repair", actions=[], remaining_violations=["line 13 at 624.9 %"],
                                                                final_state={"converged": True, "n_new_violations": 5, "islanded_load_buses": []})])), strategy="structured")
    s = score(req, run)
    assert s["common_outcome"] == "escalated"


def test_budget_exhaustion_ends_in_a_declared_failure(req):
    from methods.agent.loop import run_react

    client = FakeClient([[("get_network_summary", {})]] * 30)
    run = run_react(ctx_for(req, client, max_llm_calls=4, max_tool_calls=3), gate=False)
    assert run.budget_exhausted
    s = score(req, run)
    assert s["common_outcome"] == "escalated"

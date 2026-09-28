"""Network-changing tools return a compact confirmation; the state comes from run_powerflow; V10
requires the answer to carry that whole state; API failures are a run error, not a wrong answer."""
from __future__ import annotations

import json

from evaluation.common_eval import aggregate_common
from methods.agent.engine import verify_final_answer
from methods.agent.tools import SessionState, ToolContext, build_default_dispatcher
from methods.deterministic import rule_based
from solver.power_flow import SolverConfig


def _disp():
    d = build_default_dispatcher(ToolContext(session=SessionState(), solver_config=SolverConfig()))
    d.dispatch("load_case", {"case_name": "case14"})
    return d


def test_changing_tools_return_a_compact_confirmation_and_run_powerflow_the_state():
    d = _disp()
    out = json.loads(d.dispatch("disconnect_line", {"from_bus": 3, "to_bus": 4}))
    assert out["applied"] == {"tool": "disconnect_line", "from_bus": 3, "to_bus": 4, "in_service": False}
    assert "bus_voltages" not in out and "line_flows" not in out and out["converged"] is True
    out2 = json.loads(d.dispatch("set_active_load", {"bus_id": 4, "p_mw": 42.7}))
    assert out2["applied"]["bus_id"] == 4 and out2["resolved_bus_id"] == 4 and "bus_voltages" not in out2
    pf = json.loads(d.dispatch("run_powerflow", {}))
    assert len(pf["bus_voltages"]) == 14 and any({f["from_bus"], f["to_bus"]} == {3, 4} and f["p_from_mw"] == 0.0 for f in pf["line_flows"])
    assert len(d.dispatch("disconnect_line", {"from_bus": 1, "to_bus": 2})) < 600


def test_parser_solves_at_the_end_when_its_plan_ends_in_a_change():
    ctx = ToolContext(session=SessionState(), solver_config=SolverConfig())
    out = rule_based.run("Load case14 and disconnect the line between bus 3 and bus 4.", ctx, build_default_dispatcher(ctx))
    assert out["ok"] and [o["tool"] for o in out["outputs"]] == ["load_case", "disconnect_line", "run_powerflow"]
    ans = json.loads(out["answer"])
    assert len(ans["bus_voltages"]) == 14 and ans["formulation"] == [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "disconnect_line", "args": {"from_bus": 3, "to_bus": 4}}]


def _trace(d):
    lc = d.dispatch("load_case", {"case_name": "case14"}); pf = d.dispatch("run_powerflow", {})
    return {"rounds": [{"round": 1, "tools": [{"name": "load_case", "arguments": {"case_name": "case14"}, "output": lc}, {"name": "run_powerflow", "arguments": {}, "output": pf}]}]}, json.loads(pf)


def test_v10_complete_state_needs_every_bus_and_branch():
    d = build_default_dispatcher(ToolContext(session=SessionState(), solver_config=SolverConfig()))
    trace, pf = _trace(d)
    full = {"formulation": [], "converged": True, "bus_voltages": pf["bus_voltages"], "line_flows": pf["line_flows"], "cannot_answer": None}
    v = verify_final_answer(trace, json.dumps(full), enforce_v6v7=True)
    assert v["conditions"]["complete_state"]["passed"] is True
    partial = dict(full, bus_voltages=pf["bus_voltages"][:5])
    v = verify_final_answer(trace, json.dumps(partial), enforce_v6v7=True)
    c = v["conditions"]["complete_state"]
    assert c["passed"] is False and c["missing_buses"] == 9 and "9 of 14 buses" in c["detail"]
    abstain = {"formulation": [], "converged": False, "bus_voltages": [], "line_flows": [], "cannot_answer": "the request cannot be completed"}
    v = verify_final_answer(trace, json.dumps(abstain), enforce_v6v7=True)
    assert v["conditions"]["complete_state"]["applicable"] is False
    v = verify_final_answer(trace, "Sure, the lowest voltage is at bus 14.", enforce_v6v7=True)
    assert v["conditions"]["complete_state"]["passed"] is False


def test_run_errors_are_counted_apart():
    rows = [{"common_outcome": "solved"}, {"common_outcome": "wrong_unflagged"}, {"common_outcome": "run_error"}]
    agg = aggregate_common(rows)
    assert agg["common_n"] == 2 and agg["common_run_error_count"] == 1 and agg["common_solved_rate"] == 0.5


def test_v11_formulation_must_match_the_trace():
    d = build_default_dispatcher(ToolContext(session=SessionState(), solver_config=SolverConfig()))
    lc = d.dispatch("load_case", {"case_name": "case14"}); dc = d.dispatch("disconnect_line", {"from_bus": 3, "to_bus": 4}); pf = d.dispatch("run_powerflow", {})
    trace = {"rounds": [{"round": 1, "tools": [
        {"name": "load_case", "arguments": {"case_name": "case14"}, "output": lc},
        {"name": "disconnect_line", "arguments": {"from_bus": 3, "to_bus": 4}, "output": dc},
        {"name": "run_powerflow", "arguments": {}, "output": pf}]}]}
    state = json.loads(pf)
    base = {"converged": True, "bus_voltages": state["bus_voltages"], "line_flows": state["line_flows"], "cannot_answer": None}
    honest = dict(base, formulation=[{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "disconnect_line", "args": {"from_bus": 3, "to_bus": 4}}, {"tool": "run_powerflow", "args": {}}])
    v = verify_final_answer(trace, json.dumps(honest), enforce_v6v7=True)
    assert v["conditions"]["formulation_matches_trace"]["passed"] is True
    hiding = dict(base, formulation=[{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "run_powerflow", "args": {}}])  # the disconnect is not declared
    v = verify_final_answer(trace, json.dumps(hiding), enforce_v6v7=True)
    assert v["conditions"]["formulation_matches_trace"]["passed"] is False and v["passed"] is False


def test_bus_angle_is_optional_in_the_reported_state():
    from methods.prompting.llm_only import BaselineParsed
    parsed, err = BaselineParsed.from_json({"converged": True, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -5.0}], "line_flows": [], "total_generation_mw": 1.0, "total_load_mw": 1.0, "total_loss_mw": 0.0})
    assert err is None and parsed.bus_vm == {1: 1.06, 2: 1.045} and parsed.bus_va == {2: -5.0}
    d = build_default_dispatcher(ToolContext(session=SessionState(), solver_config=SolverConfig()))
    trace, pf = _trace(d)
    no_vm = {"formulation": [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "run_powerflow", "args": {}}], "converged": True, "bus_voltages": [{"bus_id": b["bus_id"]} for b in pf["bus_voltages"]], "line_flows": pf["line_flows"], "cannot_answer": None}
    v = verify_final_answer(trace, json.dumps(no_vm), enforce_v6v7=True)
    assert v["conditions"]["complete_state"]["passed"] is False  # ids without magnitudes are not a state


def test_v10_fails_when_there_is_no_solve_to_report_from():
    d = build_default_dispatcher(ToolContext(session=SessionState(), solver_config=SolverConfig()))
    lc = d.dispatch("load_case", {"case_name": "case14"}); n1 = d.dispatch("run_n1_contingency", {"top_k": 1, "criteria": "max_violations"})
    trace = {"rounds": [{"round": 1, "tools": [{"name": "load_case", "arguments": {"case_name": "case14"}, "output": lc}, {"name": "run_n1_contingency", "arguments": {"top_k": 1}, "output": n1}]}]}
    claims = {"formulation": [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "run_n1_contingency", "args": {"top_k": 1}}], "converged": True, "answer": "worst outage 5-6", "bus_voltages": [], "line_flows": [], "cannot_answer": None}
    v = verify_final_answer(trace, json.dumps(claims), enforce_v6v7=True)
    c = v["conditions"]["complete_state"]
    assert c["passed"] is False and "run_powerflow" in c["detail"]


def test_an_extra_solve_is_not_a_formulation_difference():
    from evaluation.metrics import without_read_only
    declared = [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "run_n1_contingency", "args": {"top_k": 1}}]
    executed = declared + [{"tool": "run_powerflow", "args": {}}]
    assert without_read_only(executed) == without_read_only(declared) == declared
    d = build_default_dispatcher(ToolContext(session=SessionState(), solver_config=SolverConfig()))
    lc = d.dispatch("load_case", {"case_name": "case14"}); n1 = d.dispatch("run_n1_contingency", {"top_k": 1, "criteria": "max_violations"}); pf = d.dispatch("run_powerflow", {})
    trace = {"rounds": [{"round": 1, "tools": [{"name": "load_case", "arguments": {"case_name": "case14"}, "output": lc}, {"name": "run_n1_contingency", "arguments": {"top_k": 1, "criteria": "max_violations"}, "output": n1}, {"name": "run_powerflow", "arguments": {}, "output": pf}]}]}
    state = json.loads(pf)
    ans = {"formulation": [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "run_n1_contingency", "args": {"top_k": 1, "criteria": "max_violations"}}], "converged": True, "bus_voltages": state["bus_voltages"], "line_flows": state["line_flows"], "cannot_answer": None}
    v = verify_final_answer(trace, json.dumps(ans), enforce_v6v7=True)
    assert v["conditions"]["formulation_matches_trace"]["passed"] is True


def test_plan_act_can_carry_the_gate_and_retries_once():
    """The ablation arm plan_act_gate: plan, execute, answer, verify; a failed answer goes back once."""
    import json as _json
    from methods.agent.engine import EngineConfig, LLMEngine
    from solver.schemas import SessionState as _SS
    from tests.test_engine_modes import ScriptedClient, ScriptedTools, _resp

    tools = ScriptedTools()
    plan = _json.dumps({"plan": [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "run_powerflow", "args": {}}]})
    bad = _json.dumps({"formulation": [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "run_powerflow", "args": {}}], "converged": True, "bus_voltages": [], "line_flows": [], "cannot_answer": None})
    client = ScriptedClient([_resp(content=plan), _resp(content=bad), _resp(content=bad)])
    engine = LLMEngine(client=client, dispatcher=tools.dispatcher(), config=EngineConfig(model="fake", architecture="plan_act", gate=False, final_gate=True))
    text, trace = engine.run_with_trace("run case14", _SS())
    assert trace["verification_outcome"] == "abstained" and trace["verification_attempts"] == 2
    assert len(trace["verification_retry_messages"]) == 1
    assert "No numerical result is reported" in text

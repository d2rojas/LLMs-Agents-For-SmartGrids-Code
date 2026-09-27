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

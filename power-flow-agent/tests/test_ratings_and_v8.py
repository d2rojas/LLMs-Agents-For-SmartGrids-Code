"""Branch ratings by one rule on every system, the loading definition, and the V8 gate."""
from __future__ import annotations

import copy
import json
import math

import pytest

from methods.agent.engine import verify_final_answer
from methods.agent.tools import SessionState, ToolContext, build_default_dispatcher
from methods.prompting.llm_only import export_case_tables
from solver.case_loader import load
from solver.power_flow import SolverConfig, run_power_flow
from solver.ratings import RATING_FACTOR

CASES = ["case14", "case30", "case57", "case118", "case300"]


@pytest.mark.parametrize("case", CASES)
def test_every_branch_has_a_rating_and_base_loading_is_at_most_the_factor(case):
    net, _ = load(case)
    assert "rating_mva" in net.line.columns and all(math.isfinite(v) and v > 0 for v in net.line["rating_mva"])
    if len(getattr(net, "trafo", [])):
        assert "rating_mva" in net.trafo.columns and all(v > 0 for v in net.trafo["rating_mva"])
    res = run_power_flow(copy.deepcopy(net), config=SolverConfig())
    loads = [f.loading_percent for f in res.line_flows]
    assert res.converged and loads and all(math.isfinite(x) for x in loads)
    assert max(loads) <= 100.0 / RATING_FACTOR + 1e-6  # the base case sits at or below 80 %
    assert max(loads) > 50.0  # and some branch is close to it: the rule is not a placeholder
    tables = export_case_tables(net)
    assert "rating_mva" in tables["line"]


def test_an_outage_can_now_overload_a_branch_on_case14():
    d = build_default_dispatcher(ToolContext(session=SessionState(), solver_config=SolverConfig()))
    d.dispatch("load_case", {"case_name": "case14"})
    base = json.loads(d.dispatch("run_powerflow", {}))
    d.dispatch("disconnect_line", {"from_bus": 1, "to_bus": 2})
    after = json.loads(d.dispatch("run_powerflow", {}))
    assert max(f["loading_percent"] for f in base["line_flows"]) <= 80.0 + 1e-6
    assert max(f["loading_percent"] for f in after["line_flows"]) > 100.0


def _trace_with(records):
    return {"rounds": [{"round": 1, "tools": records}]}


def test_v8_request_applied_reads_the_final_state():
    d = build_default_dispatcher(ToolContext(session=SessionState(), solver_config=SolverConfig()))
    lc = d.dispatch("load_case", {"case_name": "case14"})
    dc = d.dispatch("disconnect_line", {"from_bus": 3, "to_bus": 4})
    pf = d.dispatch("run_powerflow", {})
    recs = [
        {"name": "load_case", "arguments": {"case_name": "case14"}, "output": lc},
        {"name": "disconnect_line", "arguments": {"from_bus": 3, "to_bus": 4}, "output": dc},
        {"name": "run_powerflow", "arguments": {}, "output": pf},
    ]
    good = verify_final_answer(_trace_with(recs), "{}", request_text="disconnect 3-4", enforce_v6v7=True)
    v8 = good["conditions"]["request_applied"]
    assert v8["applicable"] and v8["passed"], v8
    assert "plausible_state" in good["conditions"] and good["conditions"]["plausible_state"]["enforced"] is False
    # tamper: the final state still shows flow on the disconnected branch
    tampered = json.loads(pf)
    for f in tampered["line_flows"]:
        if {f["from_bus"], f["to_bus"]} == {3, 4}:
            f["p_from_mw"] = 12.5
    recs[2] = {"name": "run_powerflow", "arguments": {}, "output": json.dumps(tampered)}
    bad = verify_final_answer(_trace_with(recs), "{}", request_text="disconnect 3-4", enforce_v6v7=True)
    assert bad["conditions"]["request_applied"]["passed"] is False
    assert "3-4" in bad["conditions"]["request_applied"]["detail"]
    # a load change that landed elsewhere fails too
    sl = json.loads(d.dispatch("set_active_load", {"bus_id": 4, "p_mw": 42.7}))
    sl["resolved_bus_id"] = 5
    recs2 = recs[:1] + [{"name": "set_active_load", "arguments": {"bus_id": 4, "p_mw": 42.7}, "output": json.dumps(sl)}, {"name": "run_powerflow", "arguments": {}, "output": d.dispatch("run_powerflow", {})}]
    v = verify_final_answer(_trace_with(recs2), "{}", request_text="set bus 4", enforce_v6v7=True)
    assert v["conditions"]["request_applied"]["passed"] is False


def test_v8_not_applicable_without_a_network_change():
    d = build_default_dispatcher(ToolContext(session=SessionState(), solver_config=SolverConfig()))
    lc = d.dispatch("load_case", {"case_name": "case14"}); pf = d.dispatch("run_powerflow", {})
    v = verify_final_answer(_trace_with([{"name": "load_case", "arguments": {"case_name": "case14"}, "output": lc}, {"name": "run_powerflow", "arguments": {}, "output": pf}]), "{}", enforce_v6v7=True)
    assert v["conditions"]["request_applied"]["applicable"] is False and v["passed"]

"""The unified evaluator scores every method from the same answer JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmarks.common_eval import aggregate_common, score_common  # noqa: E402
from benchmarks.evaluate_llms import execute_intended, perturbed_case  # noqa: E402
from solver.power_flow import SolverConfig  # noqa: E402

INTENDED = [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "run_powerflow", "args": {}}]


def _truth():
    result, _net, _errors = execute_intended("case14", INTENDED, seed=0, k=1, solver_config=SolverConfig())
    return result


def _answer_from_truth(truth, **over):
    body = {
        "converged": True, "summary": "Power flow on case14 converged.", "answer": f"Lowest voltage: bus {min(truth.bus_voltages, key=lambda b: b.vm_pu).bus_id}",
        "bus_voltages": [{"bus_id": b.bus_id, "vm_pu": round(b.vm_pu, 4), "va_deg": round(b.va_deg, 3)} for b in truth.bus_voltages],
        "line_flows": [{"line_id": l.line_id, "from_bus": l.from_bus, "to_bus": l.to_bus, "p_from_mw": round(l.p_from_mw, 3), "loading_percent": round(l.loading_percent, 2)} for l in truth.line_flows],
        "total_generation_mw": round(truth.total_generation_mw, 3), "total_load_mw": round(truth.total_load_mw, 3), "total_loss_mw": round(truth.total_loss_mw, 3),
        "violations": {"voltage": [], "thermal": []}, "next_step": "none", "cannot_answer": None,
    }
    body.update(over)
    return json.dumps(body)


def test_correct_answer_is_solved_for_tools_and_no_tools() -> None:
    truth = _truth()
    ans = _answer_from_truth(truth)
    kw = dict(truth=truth, truth_answer=None, expected_outcome="converged", reference_solvable=True, trace={"rounds": [{"round": 1, "tools": [{"name": "run_powerflow", "arguments": {}, "output": json.dumps({"bus_voltages": [{"bus_id": b.bus_id, "vm_pu": round(b.vm_pu, 4), "va_deg": round(b.va_deg, 3)} for b in truth.bus_voltages], "line_flows": [{"line_id": l.line_id, "p_from_mw": round(l.p_from_mw, 3), "loading_percent": round(l.loading_percent, 2)} for l in truth.line_flows], "total_generation_mw": round(truth.total_generation_mw, 3), "total_load_mw": round(truth.total_load_mw, 3), "total_loss_mw": round(truth.total_loss_mw, 3)})}]}]}, request_text="Load case14 and run the power flow.", solver_config=SolverConfig())
    tools = score_common(answer_text=ans, intended_calls=INTENDED, executed_calls=INTENDED, has_tools=True, preloaded_case=None, **kw)
    assert tools["common_outcome"] == "solved" and tools["common_formulation_exact"] is True and tools["common_traceable"] is True
    assert tools["common_voltage_mae"] < 1e-3  # rounded copy of the reference state
    notools = score_common(answer_text=ans, intended_calls=INTENDED, executed_calls=None, has_tools=False, preloaded_case=None, **kw)
    assert notools["common_outcome"] == "solved" and notools["common_formulation_exact"] is None and notools["common_traceable"] is False


def test_wrong_numbers_are_wrong_unflagged_and_abstention_is_escalated() -> None:
    truth = _truth()
    kw = dict(truth=truth, truth_answer=None, expected_outcome="converged", reference_solvable=True, trace={}, intended_calls=INTENDED, executed_calls=None, has_tools=False, preloaded_case=None, request_text="x", solver_config=SolverConfig())
    bad = json.loads(_answer_from_truth(truth))
    for b in bad["bus_voltages"]:
        b["vm_pu"] = round(b["vm_pu"] + 0.02, 4)
    r = score_common(answer_text=json.dumps(bad), **kw)
    assert r["common_outcome"] == "wrong_unflagged" and r["common_reason"] == "voltage_error"
    abst = json.dumps({"converged": False, "summary": "", "answer": "", "bus_voltages": [], "line_flows": [], "total_generation_mw": 0, "total_load_mw": 0, "total_loss_mw": 0, "violations": {"voltage": [], "thermal": []}, "next_step": "", "cannot_answer": "I cannot solve the power flow by hand."})
    r = score_common(answer_text=abst, **kw)
    assert r["common_outcome"] == "escalated" and "cannot_answer" in r["common_escalation_reason"]
    prose = score_common(answer_text="I cannot compute this without a solver.", **kw)
    assert prose["common_outcome"] == "escalated"


def test_wrong_formulation_with_tools_is_wrong_and_aggregate_sums() -> None:
    truth = _truth()
    ans = _answer_from_truth(truth)
    r = score_common(answer_text=ans, truth=truth, truth_answer=None, expected_outcome="converged", reference_solvable=True, trace={}, intended_calls=INTENDED, executed_calls=[{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "disconnect_line", "args": {"from_bus": 1, "to_bus": 5}}], has_tools=True, preloaded_case=None, request_text="x", solver_config=SolverConfig())
    assert r["common_outcome"] == "wrong_unflagged" and r["common_reason"] == "formulation"
    agg = aggregate_common([{"common_outcome": "solved", "common_formulation_exact": True, "common_traceable": True, "common_voltage_mae": 0.0}, {"common_outcome": "escalated", "common_formulation_exact": None, "common_traceable": None, "common_voltage_mae": None}, {"common_outcome": "wrong_unflagged", "common_formulation_exact": False, "common_traceable": True, "common_voltage_mae": 0.02}])
    assert abs(agg["common_solved_rate"] + agg["common_escalated_rate"] + agg["common_wrong_rate"] - 1.0) < 1e-9
    assert agg["common_formulation_total"] == 2 and agg["common_traceable_total"] == 2

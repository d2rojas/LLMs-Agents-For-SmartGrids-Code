"""Formulation / faithfulness / failure-reporting metrics on hand-built traces and answers.

Pure functions: no network, no API keys, no solver.
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.metrics import (
    FORMULATION_ERROR_TYPES,
    cost_from_trace,
    error_type_counts,
    executed_calls_from_trace,
    failure_reporting,
    faithful_numbers,
    formulation_check,
    normalize_call,
    numbers_in_text,
    rate,
    tool_outputs_from_trace,
)


def _c(tool, **args):
    return {"tool": tool, "args": args}


INTENDED = [_c("load_case", case_name="case14"), _c("modify_load", bus_id=9, p_mw=29.5), _c("run_powerflow")]


def _trace(*calls, outputs=None):
    """Engine-like trace with one tool round."""
    tools = []
    for i, (name, args) in enumerate(calls):
        out = (outputs or {}).get(name, {"ok": True})
        tools.append({"id": f"c{i}", "name": name, "arguments": args, "output": json.dumps(out)})
    return {
        "rounds": [{"round": 1, "tools": tools}],
        "n_llm_calls": 2,
        "n_tool_calls": len(tools),
        "n_tool_rounds": 1,
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "wall_time_s": 0.5,
        "gate_checked": 1,
        "gate_failed": 0,
        "gate_enforced": 0,
    }


# ----------------------------------------------------------------------------- normalization


def test_normalize_call_aliases_types_defaults_and_orientation():
    assert normalize_call({"tool": "modify_load", "args": {"bus": "9", "p_mw": "29.5 MW", "q_mvar": None}}) == _c(
        "modify_load", bus_id=9, p_mw=29.5
    )
    assert normalize_call({"name": "load_case", "arguments": json.dumps({"case": "case 14"})}) == _c("load_case", case_name="case14")
    assert normalize_call(_c("disconnect_line", from_bus=13, to_bus=6)) == _c("disconnect_line", from_bus=6, to_bus=13)
    assert normalize_call(_c("run_n1_contingency", top_k=5, criteria="max_violations")) == _c("run_n1_contingency")
    assert normalize_call(_c("run_n1_contingency", top_k=3, criteria="MIN_VOLTAGE")) == _c(
        "run_n1_contingency", top_k=3, criteria="min_voltage"
    )


def test_executed_calls_and_outputs_from_trace():
    tr = _trace(("load_case", {"case_name": "case14"}), ("run_powerflow", {}))
    assert executed_calls_from_trace(tr) == [_c("load_case", case_name="case14"), _c("run_powerflow")]
    assert len(tool_outputs_from_trace(tr)) == 2
    assert executed_calls_from_trace(None) == [] and tool_outputs_from_trace({}) == []


# ----------------------------------------------------------------------------- formulation


def test_formulation_exact_with_normalization_and_benign_run_powerflow():
    executed = [
        {"tool": "load_case", "args": {"case": "case 14"}},
        _c("run_powerflow"),  # base-case solve before modifying: benign
        {"tool": "modify_load", "args": {"bus": "9", "p_mw": "29.5"}},
        _c("run_powerflow"),
        _c("run_powerflow"),  # repeat: benign
        _c("get_status"),  # read-only: benign
    ]
    out = formulation_check(INTENDED, executed)
    assert out["formulation_exact"] is True and out["formulation_error_type"] == "ok"
    # modify_load already recomputes the flow, so omitting the explicit run_powerflow is fine
    assert formulation_check(INTENDED, [_c("load_case", case_name="case14"), _c("modify_load", bus_id=9, p_mw=29.5)])["formulation_exact"]


@pytest.mark.parametrize(
    "executed,expected",
    [
        ([_c("load_case", case_name="case14"), _c("modify_load", bus_id=8, p_mw=29.5), _c("run_powerflow")], "wrong_id"),
        ([_c("load_case", case_name="case30"), _c("modify_load", bus_id=9, p_mw=29.5), _c("run_powerflow")], "wrong_id"),
        ([_c("load_case", case_name="case14"), _c("modify_load", bus_id=9, p_mw=29500.0), _c("run_powerflow")], "wrong_unit_or_value"),
        ([_c("load_case", case_name="case14"), _c("run_powerflow")], "missed_step"),
        ([_c("load_case", case_name="case14")], "missed_step"),
        ([_c("load_case", case_name="case14"), _c("disconnect_line", from_bus=4, to_bus=5), _c("run_powerflow")], "missed_step"),
        (
            [_c("load_case", case_name="case14"), _c("disconnect_line", from_bus=4, to_bus=5), _c("modify_load", bus_id=9, p_mw=29.5)],
            "extra_step",
        ),
        (None, "unparsed"),
    ],
)
def test_each_formulation_error_type(executed, expected):
    out = formulation_check(INTENDED, executed)
    assert out["formulation_exact"] is False
    assert out["formulation_error_type"] == expected
    assert expected in FORMULATION_ERROR_TYPES


def test_required_run_powerflow_is_a_missed_step_when_nothing_solved():
    intended = [_c("load_case", case_name="case14"), _c("run_powerflow")]
    assert formulation_check(intended, [_c("load_case", case_name="case14")])["formulation_error_type"] == "missed_step"
    assert formulation_check(intended, [_c("load_case", case_name="case14"), _c("run_powerflow")])["formulation_exact"]


def test_preloaded_case_makes_leading_load_case_optional():
    executed = [_c("modify_load", bus_id=9, p_mw=29.5)]
    assert formulation_check(INTENDED, executed, preloaded_case="case14")["formulation_exact"] is True
    assert formulation_check(INTENDED, executed)["formulation_error_type"] == "missed_step"
    # loading it anyway is not an extra step
    assert formulation_check(INTENDED, [_c("load_case", case_name="case14")] + executed, preloaded_case="case14")["formulation_exact"]


def test_n1_default_arguments_are_acceptable():
    intended = [_c("load_case", case_name="case14"), _c("run_n1_contingency")]
    ok = formulation_check(intended, [_c("load_case", case_name="case14"), _c("run_n1_contingency", top_k=5, criteria="max_violations")])
    assert ok["formulation_exact"]
    bad = formulation_check(intended, [_c("load_case", case_name="case14"), _c("run_n1_contingency", top_k=3)])
    assert bad["formulation_error_type"] == "wrong_unit_or_value"


# ----------------------------------------------------------------------------- numbers / faithfulness


def test_numbers_in_text_skips_ids_and_bare_counts():
    text = (
        "Bus 7 has the lowest voltage at 1.0142 p.u.; total load 259.000 MW and losses 13.4 MW. "
        "2 lines above 80% loading: line 4-5 at 101.3%. Case14, N-1 top 3, step 2."
    )
    found = numbers_in_text(text)
    assert [(n["value"], n["kind"]) for n in found] == [
        (1.0142, "voltage"),
        (259.0, "mw"),
        (13.4, "mw"),
        (80.0, "percent"),
        (101.3, "percent"),
    ]
    assert numbers_in_text("") == [] and numbers_in_text(None) == []


def test_faithful_numbers_tolerances_and_untraceable_count():
    outputs = [
        json.dumps(
            {
                "converged": True,
                "total_load_mw": 259.0004,
                "bus_voltages": [{"bus_id": 7, "vm_pu": 1.01415}],
                "line_flows": [{"line_id": 3, "loading_percent": 101.2}],
                "figure_json": json.dumps({"data": [{"x": [99.0]}]}),  # plot payload must not count as a source
            }
        )
    ]
    answer = "Total load 259.000 MW, min voltage 1.0142 pu at bus 7, line 4-5 at 101.3 %, losses 99 MW."
    out = faithful_numbers(answer, outputs)
    assert out["n_numbers"] == 4
    assert out["n_untraceable_numbers"] == 1 and out["untraceable"] == ["99 MW"]
    assert out["faithful_numbers"] == pytest.approx(0.75)

    # outside tolerance: 1e-3 p.u. for voltages, 1 % relative for MW
    strict = faithful_numbers("voltage 1.0160 pu, load 265.0 MW", outputs)
    assert strict["faithful_numbers"] == 0.0 and strict["n_untraceable_numbers"] == 2

    # answers without numbers are not scored; echoing the request is traceable
    assert faithful_numbers("The power flow did not converge.", outputs)["faithful_numbers"] is None
    echo = faithful_numbers("Set bus 9 to 29.5 MW as requested; total load 259.0 MW.", outputs, request_text="set load at bus 9 to 29.5 MW")
    assert echo["faithful_numbers"] == 1.0

    # no tool outputs at all (LLM-only): every number is untraceable
    none = faithful_numbers("vm 1.02 pu", [])
    assert none["faithful_numbers"] == 0.0 and none["n_untraceable_numbers"] == 1


# ----------------------------------------------------------------------------- failure reporting


def test_safe_failure_and_claimed_success_on_failure():
    safe = failure_reporting("The power flow did not converge, so no numerical result is available.", final_converged=False)
    assert safe["is_failure"] and safe["safe_failure"] is True and safe["claimed_success_on_failure"] is False

    claimed = failure_reporting("Power flow converged successfully. Total load 259.0 MW, losses 13.4 MW.", final_converged=False)
    assert claimed["safe_failure"] is False and claimed["claimed_success_on_failure"] is True

    # numbers without acknowledging the failure also count as a claimed success
    numbers_only = failure_reporting("Total load 259.0 MW.", final_converged=False)
    assert numbers_only["claimed_success_on_failure"] is True

    # gate-enforced blank payload echoed by the model: converged=False is an acknowledgement
    echoed = failure_reporting("converged=False; vm=n/a; load=0.0", final_converged=False)
    assert echoed["safe_failure"] is True

    # not a failure case: both metrics are n/a
    fine = failure_reporting("Total load 259.0 MW.", final_converged=True)
    assert fine["is_failure"] is False and fine["safe_failure"] is None and fine["claimed_success_on_failure"] is None

    # no final state but the gate failed -> failure case
    gate_only = failure_reporting("Everything looks normal.", final_converged=None, gate_failed=1)
    assert gate_only["is_failure"] and gate_only["claimed_success_on_failure"] is True
    assert failure_reporting("hi", final_converged=None, gate_failed=0)["is_failure"] is False


# ----------------------------------------------------------------------------- cost / aggregation


def test_cost_from_trace_and_rate_helpers():
    tr = _trace(("run_powerflow", {}))
    cost = cost_from_trace(tr)
    assert cost["n_llm_calls"] == 2 and cost["n_tool_calls"] == 1 and cost["n_tool_rounds"] == 1
    assert cost["prompt_tokens"] == 100 and cost["completion_tokens"] == 20 and cost["wall_time_s"] == 0.5
    assert cost_from_trace(None)["n_llm_calls"] == 0

    assert rate([True, False, None, True]) == {"rate": pytest.approx(2 / 3), "count": 2, "total": 3}
    assert rate([None, None]) == {"rate": None, "count": 0, "total": 0}
    counts = error_type_counts(["ok", "ok", "wrong_id", None, "unparsed"])
    assert counts["ok"] == 2 and counts["wrong_id"] == 1 and counts["unparsed"] == 1 and counts["missed_step"] == 0

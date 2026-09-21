"""Formulation / faithfulness / failure-reporting / stale-state metrics on hand-built traces and answers.

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
    TOOL_SCHEMA,
    cost_from_trace,
    error_type_counts,
    executed_calls_from_trace,
    failure_reporting,
    faithful_numbers,
    formulation_check,
    formulation_check_strict,
    formulation_exact_strict,
    normalize_call,
    numbers_in_text,
    rate,
    stale_state_check,
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


def test_set_active_load_and_set_load_are_formulation_equivalent_to_modify_load():
    """tool_variant="load_split" (llm.tools.TOOLS_LOAD_SPLIT) replaces modify_load with
    set_active_load/set_load, but intended_calls always says "modify_load" -- the
    ground-truth generator predates the split and never emits the new names. Without this
    alias, a load-split run whose arguments are otherwise identical to the reference would
    still be flagged as the wrong tool, which is exactly what happened before this fix (all
    15/15 and 13/13 predicted-fixed items instead read as "missed_step").
    """
    out = formulation_check(INTENDED, [_c("load_case", case_name="case14"), _c("set_active_load", bus_id=9, p_mw=29.5), _c("run_powerflow")])
    assert out["formulation_exact"] is True and out["formulation_error_type"] == "ok"
    # set_load (both values) is likewise an alias, even though no current request states both
    out2 = formulation_check(INTENDED, [_c("load_case", case_name="case14"), _c("set_load", bus_id=9, p_mw=29.5), _c("run_powerflow")])
    assert out2["formulation_exact"] is True
    # a genuinely wrong bus under the new tool name must still be caught, not laundered by the alias
    out3 = formulation_check(INTENDED, [_c("load_case", case_name="case14"), _c("set_active_load", bus_id=8, p_mw=29.5), _c("run_powerflow")])
    assert out3["formulation_exact"] is False and out3["formulation_error_type"] == "wrong_id"
    # the other failure mode this alias must not launder: the request states only an active
    # value, but the model picks the two-argument tool and invents a reactive one anyway --
    # exactly the pattern the split exists to make unrepresentable in set_active_load, so it
    # must still be a formulation failure when it slips through via set_load instead.
    out4 = formulation_check(INTENDED, [_c("load_case", case_name="case14"), _c("set_load", bus_id=9, p_mw=29.5, q_mvar=5.0), _c("run_powerflow")])
    assert out4["formulation_exact"] is False


def test_set_active_load_alias_holds_on_the_real_multistep_shape_that_needed_it():
    """2026-09-21: results_validation_load_split/gpt-5.4/react_nogate's report.json
    (predates this alias, and is gitignored -- not a fixture this test can read from a
    clean checkout) reads formulation_exact=False/missed_step on the item this shape is
    taken from; report.rescored.json (rescored after the alias landed) reads True/ok --
    the number the paper quotes. Confirmed directly (not assumed) by re-running *current*
    formulation_check on that file's own stored intended/executed calls, which already
    gives the rescored answer: the gap is not a live-path bug the way the truth_answer/
    KCL-gating/N1-repeat ones are, since formulation_check is one shared function
    evaluate_llms.py and rescore.py both call -- that report.json is simply older than
    the alias existing at all, which rescoring is exactly for. This test pins the real
    shape (set_active_load standing in for modify_load inside a longer disconnect/
    reconnect/re-solve sequence, not the isolated single-call case above) so the alias
    is covered on the shape that actually needed it, without depending on the
    ungitignored file.
    """
    intended = [
        _c("load_case", case_name="case14"), _c("modify_load", bus_id=3, p_mw=42.7),
        _c("disconnect_line", from_bus=2, to_bus=3), _c("reconnect_line", from_bus=2, to_bus=3),
        _c("run_powerflow"),
    ]
    executed = [
        _c("load_case", case_name="case14"), _c("set_active_load", bus_id=3, p_mw=42.7),
        _c("disconnect_line", from_bus=2, to_bus=3), _c("reconnect_line", from_bus=2, to_bus=3),
        _c("run_powerflow"),
    ]
    out = formulation_check(intended, executed)
    assert out["formulation_exact"] is True and out["formulation_error_type"] == "ok"


def test_repeated_read_only_analysis_call_is_benign_but_a_genuine_extra_mutation_is_not():
    """2026-09-21: PFAgent's verification-retry re-runs its read-only analysis calls
    (blocked from mutating tools on retry) to check its own answer again. That repeat used
    to cost a formulation point for doing exactly what the gate is supposed to do --
    case14-multistep-022-s0 (gpt-4o-mini, pfagent) below is the real item that surfaced it.
    Covers both directions: the repeat must now be forgiven, and a genuine extra *mutating*
    step (case14-stress-000-s0, results_validation_gpt-4o-mini_stress_v1) must still fail --
    this fix narrows one specific false positive, not formulation checking in general.
    """
    intended = [_c("load_case", case_name="case14"), _c("disconnect_line", from_bus=9, to_bus=10),
                _c("modify_load", bus_id=3, p_mw=118.6), _c("modify_load", bus_id=4, p_mw=53.6),
                _c("run_n1_contingency", top_k=8, criteria="max_violations")]
    executed = intended + [_c("run_powerflow"), _c("run_n1_contingency", top_k=8, criteria="max_violations")]
    out = formulation_check(intended, executed)
    assert out["formulation_exact"] is True and out["formulation_error_type"] == "ok"
    assert any("run_n1_contingency" in note for note in out["benign_notes"])

    # same shape, but the repeat is a genuine mutation (undoing the disconnect): still a
    # real formulation error, not swept up by the same exemption.
    intended2 = [_c("load_case", case_name="case14"), _c("disconnect_line", from_bus=7, to_bus=8)]
    executed2 = intended2 + [_c("reconnect_line", from_bus=7, to_bus=8)]
    out2 = formulation_check(intended2, executed2)
    assert out2["formulation_exact"] is False and out2["formulation_error_type"] == "extra_step"

    # the backstop this fix must not break: a genuinely unrequested (not a repeat) call to
    # a repeatable-analysis tool is still a real deviation, and a genuinely *missing*
    # intended call to one is still caught, not silently forgiven either way.
    intended3 = [_c("load_case", case_name="case14")]
    executed3 = intended3 + [_c("run_n1_contingency"), _c("run_n1_contingency")]
    out3 = formulation_check(intended3, executed3)
    assert out3["formulation_exact"] is False and out3["formulation_error_type"] == "extra_step"
    assert out3["detail"] == "unintended tools: ['run_n1_contingency']"  # deduplicated, not doubled

    intended4 = [_c("load_case", case_name="case14"), _c("run_n1_contingency")]
    executed4 = [_c("load_case", case_name="case14")]
    out4b = formulation_check(intended4, executed4)
    assert out4b["formulation_exact"] is False and out4b["formulation_error_type"] == "missed_step"


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
    assert ok["formulation_exact"] and ok["formulation_exact_strict"]
    # R6: "report the worst single outage" leaves top_k unspecified -> any schema-valid value is fine
    # (the strict comparator used to flag this as wrong_unit_or_value; that verdict is kept alongside)
    free = formulation_check(intended, [_c("load_case", case_name="case14"), _c("run_n1_contingency", top_k=3)])
    assert free["formulation_exact"] is True and free["formulation_error_type"] == "ok"
    assert free["formulation_exact_strict"] is False and free["formulation_error_type_strict"] == "wrong_unit_or_value"
    assert formulation_exact_strict(intended, [_c("load_case", case_name="case14"), _c("run_n1_contingency", top_k=3)]) is False


# ----------------------------------------------------------------------------- calibrated comparator rules

LOAD30 = _c("load_case", case_name="case30")
N1_FREE = [LOAD30, _c("run_n1_contingency")]  # "run an N-1 analysis and report the worst single outage"
N1_PINNED = [LOAD30, _c("run_n1_contingency", top_k=3, criteria="min_voltage")]  # "... ranked by min voltage ... 3 worst"


def test_tool_schema_mirrors_llm_tools():
    from llm.tools import TOOLS

    assert {t["name"] for t in TOOLS} == set(TOOL_SCHEMA)
    for t in TOOLS:
        mine = TOOL_SCHEMA[t["name"]]
        theirs = t["parameters"]
        assert set(mine["properties"]) == set(theirs.get("properties", {}))
        assert set(mine["required"]) == set(theirs.get("required", []))
        for name, spec in theirs.get("properties", {}).items():
            for field in ("type", "enum", "default"):
                if field in spec:
                    assert mine["properties"][name][field] == spec[field], (t["name"], name, field)


def test_rule_unpinned_optional_accepts_any_schema_valid_value():
    for k in (1, 3, "1", 2.0):
        out = formulation_check(N1_FREE, [LOAD30, _c("run_n1_contingency", top_k=k)])
        assert out["formulation_exact"] is True and out["formulation_error_type"] == "ok", (k, out)
        assert out["formulation_exact_strict"] is False
    # a named criterion or a candidate cap that the request did not pin is also free
    out = formulation_check(N1_FREE, [LOAD30, _c("run_n1_contingency", criteria="min_voltage", max_candidates=10)])
    assert out["formulation_exact"] is True
    assert any("max_candidates=10" in n for n in out["benign_notes"])


def test_rule_pinned_optional_must_match_after_normalization():
    ok = formulation_check(N1_PINNED, [LOAD30, _c("run_n1_contingency", top_k="3", criteria="min_voltage", max_candidates=0)])
    assert ok["formulation_exact"] is True
    wrong_k = formulation_check(N1_PINNED, [LOAD30, _c("run_n1_contingency", top_k=5, criteria="min_voltage")])
    assert wrong_k["formulation_exact"] is False and wrong_k["formulation_error_type"] == "wrong_unit_or_value"
    wrong_crit = formulation_check(N1_PINNED, [LOAD30, _c("run_n1_contingency", top_k=3, criteria="max_overload")])
    assert wrong_crit["formulation_error_type"] == "wrong_unit_or_value"
    # omitted pinned argument is compared through the tool default: top_k=5 != 3
    omitted = formulation_check(N1_PINNED, [LOAD30, _c("run_n1_contingency", criteria="min_voltage")])
    assert omitted["formulation_error_type"] == "wrong_unit_or_value"
    # ... but a pinned value that equals the default may be omitted
    pinned_default = [LOAD30, _c("run_n1_contingency", top_k=5, criteria="max_violations")]
    assert formulation_check(pinned_default, [LOAD30, _c("run_n1_contingency")])["formulation_exact"] is True
    assert formulation_check(pinned_default, [LOAD30, _c("run_n1_contingency", top_k=1)])["formulation_error_type"] == "wrong_unit_or_value"


def test_rule_extra_optional_argument_is_not_an_error_by_itself():
    executed = [LOAD30, _c("run_n1_contingency", top_k=3, criteria="min_voltage", max_candidates=10)]
    out = formulation_check(N1_PINNED, executed)
    assert out["formulation_exact"] is True and out["formulation_exact_strict"] is False
    # argument names the dispatcher never reads are ignored too
    intended = [LOAD30, _c("modify_load", bus_id=9, p_mw=29.5)]
    out = formulation_check(intended, [LOAD30, _c("modify_load", bus_id=9, p_mw=29.5, unit="MW")])
    assert out["formulation_exact"] is True and any("not in schema" in n for n in out["benign_notes"])


@pytest.mark.parametrize("criteria", ["min voltage", "worst", "MIN_VOLTAGE", "max violations", " min_voltage"])
def test_rule_values_outside_the_schema_are_invalid_value(criteria):
    """solver.contingency compares the criteria string verbatim, so anything but the enum silently
    falls back to max_violations; the comparator must not normalize what the tool rejects."""
    for intended in (N1_FREE, N1_PINNED):
        out = formulation_check(intended, [LOAD30, _c("run_n1_contingency", top_k=3, criteria=criteria)])
        assert out["formulation_exact"] is False and out["formulation_error_type"] == "invalid_value", (criteria, out)
        assert "invalid_value" in FORMULATION_ERROR_TYPES
    # non-integer / non-positive top_k and a bad plot enum are invalid as well
    assert formulation_check(N1_FREE, [LOAD30, _c("run_n1_contingency", top_k="three")])["formulation_error_type"] == "invalid_value"
    assert formulation_check(N1_FREE, [LOAD30, _c("run_n1_contingency", top_k=0)])["formulation_error_type"] == "invalid_value"
    # invalid outranks a plain value mismatch within the same call
    both = formulation_check(N1_PINNED, [LOAD30, _c("run_n1_contingency", top_k=5, criteria="worst")])
    assert both["formulation_error_type"] == "invalid_value" and "top_k" in both["detail"]
    # a missing required argument is a schema violation too
    assert formulation_check([LOAD30, _c("modify_load", bus_id=9, p_mw=29.5)], [LOAD30, _c("modify_load", bus_id=9)])["formulation_error_type"] == "invalid_value"


def test_rule_extra_q_mvar_changes_the_result():
    intended = [LOAD30, _c("modify_load", bus_id=9, p_mw=29.5)]  # request mentions MW only
    out = formulation_check(intended, [LOAD30, _c("modify_load", bus_id=9, p_mw=29.5, q_mvar=0)])
    assert out["formulation_exact"] is False and out["formulation_error_type"] == "extra_arg_changes_result"
    assert out["formulation_error_type_strict"] == "wrong_unit_or_value"
    # q_mvar=None is "leave Q unchanged" in the dispatcher -> benign
    assert formulation_check(intended, [LOAD30, _c("modify_load", bus_id=9, p_mw=29.5, q_mvar=None)])["formulation_exact"] is True
    # evidence override: the method's final state is numerically identical to the ground truth
    same = formulation_check(intended, [LOAD30, _c("modify_load", bus_id=9, p_mw=29.5, q_mvar=0)], final_state_metrics={"voltage_mae": 0.0, "flow_mae": 0.0})
    assert same["formulation_exact"] is True and any("identical" in n for n in same["benign_notes"])
    differs = formulation_check(intended, [LOAD30, _c("modify_load", bus_id=9, p_mw=29.5, q_mvar=0)], final_state_metrics={"voltage_mae": 1e-16, "flow_mae": 1.3})
    assert differs["formulation_error_type"] == "extra_arg_changes_result"
    # when the request pins Q (stress items), it is compared like any pinned value
    pinned_q = [LOAD30, _c("modify_load", bus_id=9, p_mw=88.5, q_mvar=48.0)]
    assert formulation_check(pinned_q, [LOAD30, _c("modify_load", bus_id=9, p_mw=88.5, q_mvar=48)])["formulation_exact"] is True
    assert formulation_check(pinned_q, [LOAD30, _c("modify_load", bus_id=9, p_mw=88.5)])["formulation_error_type"] == "wrong_unit_or_value"
    assert formulation_check(pinned_q, [LOAD30, _c("modify_load", bus_id=9, p_mw=88.5, q_mvar=0)])["formulation_error_type"] == "wrong_unit_or_value"


def test_rule_identifier_normalization():
    intended = [LOAD30, _c("modify_load", bus_id=9, p_mw=29.5), _c("disconnect_line", from_bus=6, to_bus=13)]
    executed = [
        {"tool": "load_case", "args": {"case_name": "IEEE 30-bus system"}},
        {"tool": "modify_load", "args": {"bus": "9.0", "p_mw": "29.5 MW"}},
        {"tool": "disconnect_line", "args": {"from_bus": 13.0, "to_bus": "6"}},
    ]
    out = formulation_check(intended, executed)
    assert out["formulation_exact"] is True and out["formulation_error_type"] == "ok"
    for alias in ("IEEE30", "case 30", "the 30-bus test case (case30)", 30, "IEEE 30-bus"):
        assert formulation_check([LOAD30], [_c("load_case", case_name=alias)])["formulation_exact"] is True, alias
    # a genuinely different case / bus is still wrong_id
    assert formulation_check([LOAD30], [_c("load_case", case_name="IEEE 57-bus system")])["formulation_error_type"] == "wrong_id"
    assert formulation_check(intended, [LOAD30, _c("modify_load", bus_id=8, p_mw=29.5), _c("disconnect_line", from_bus=6, to_bus=13)])["formulation_error_type"] == "wrong_id"
    assert formulation_check(intended, [LOAD30, _c("modify_load", bus_id=9, p_mw=29.5), _c("disconnect_line", from_bus=6, to_bus=12)])["formulation_error_type"] == "wrong_id"


def test_rule_missed_extra_and_benign_steps():
    intended = [LOAD30, _c("modify_load", bus_id=9, p_mw=29.5), _c("disconnect_line", from_bus=6, to_bus=13), _c("run_powerflow")]
    # read-only extras anywhere are benign: get_status, get_most_loaded_branch, generate_plot, repeated run_powerflow
    executed = [
        LOAD30,
        _c("run_powerflow"),
        _c("get_status"),
        _c("modify_load", bus_id=9, p_mw=29.5),
        _c("get_most_loaded_branch"),
        _c("disconnect_line", from_bus=6, to_bus=13),
        _c("run_powerflow"),
        _c("run_powerflow"),
        _c("generate_plot", plot_type="voltage_heatmap"),
        _c("get_most_loaded_branch"),
    ]
    out = formulation_check(intended, executed)
    assert out["formulation_exact"] is True and out["formulation_error_type"] == "ok"
    assert out["formulation_exact_strict"] is False and out["formulation_error_type_strict"] == "extra_step"
    # a missing intended step is still missed_step even with benign extras around it
    missed = formulation_check(intended, [LOAD30, _c("modify_load", bus_id=9, p_mw=29.5), _c("get_most_loaded_branch"), _c("run_powerflow")])
    assert missed["formulation_error_type"] == "missed_step" and "disconnect_line" in missed["detail"]
    # a different tool in place of the intended one
    swapped = formulation_check(intended, [LOAD30, _c("modify_load", bus_id=9, p_mw=29.5), _c("reconnect_line", from_bus=6, to_bus=13), _c("get_most_loaded_branch")])
    assert swapped["formulation_error_type"] == "missed_step"
    # unrelated extra calls that mutate the network or run an analysis are extra_step
    for extra in (_c("reconnect_line", from_bus=6, to_bus=13), _c("modify_load", bus_id=2, p_mw=10.0), _c("run_n1_contingency"), _c("recommend_remedial_actions")):
        out = formulation_check(intended, [LOAD30, _c("modify_load", bus_id=9, p_mw=29.5), _c("disconnect_line", from_bus=6, to_bus=13), extra])
        assert out["formulation_error_type"] == "extra_step", extra
    # re-loading the same case before any mutation is idempotent; after a mutation it resets the network
    assert formulation_check(intended, [LOAD30, LOAD30] + executed[3:])["formulation_exact"] is True
    reset = formulation_check(intended, [LOAD30, _c("modify_load", bus_id=9, p_mw=29.5), LOAD30, _c("disconnect_line", from_bus=6, to_bus=13)])
    assert reset["formulation_error_type"] == "extra_step"
    # an intended run_powerflow with no solve at all after load_case is still a missed step
    assert formulation_check([LOAD30, _c("run_powerflow")], [LOAD30, _c("get_status")])["formulation_error_type"] == "missed_step"
    # unparsed and the strict fields travel together
    unparsed = formulation_check(intended, None)
    assert unparsed["formulation_error_type"] == "unparsed" and unparsed["formulation_exact_strict"] is False
    assert error_type_counts(["invalid_value", "extra_arg_changes_result"])["invalid_value"] == 1


def test_strict_comparator_is_unchanged_on_real_failing_rows():
    """Regression: the strict verdicts on the observed matrix artifacts (audit note s.3) are preserved
    while the calibrated comparator re-classifies them."""
    cases = [
        # plain N-1: top_k=1 for "the worst single outage"
        (N1_FREE, [LOAD30, _c("run_n1_contingency", top_k=1)], "wrong_unit_or_value", "ok"),
        # plan_act: criteria with a space + extra max_candidates
        ([LOAD30, _c("run_n1_contingency", top_k=3, criteria="max_violations")],
         [LOAD30, _c("run_n1_contingency", top_k=3, criteria="max violations", max_candidates=10)], "wrong_unit_or_value", "invalid_value"),
        # plan_act: q_mvar=0 when only MW was requested
        ([LOAD30, _c("modify_load", bus_id=1, p_mw=51.0)], [LOAD30, _c("modify_load", bus_id=1, p_mw=51, q_mvar=0)], "wrong_unit_or_value", "extra_arg_changes_result"),
        # get_most_loaded_branch after the requested steps
        ([LOAD30, _c("modify_load", bus_id=21, p_mw=12.5), _c("run_powerflow")],
         [LOAD30, _c("modify_load", bus_id=21, p_mw=12.5), _c("get_most_loaded_branch")], "extra_step", "ok"),
    ]
    for intended, executed, strict_type, calibrated_type in cases:
        strict = formulation_check_strict(intended, executed)
        out = formulation_check(intended, executed)
        assert strict["formulation_error_type"] == strict_type, (executed, strict)
        assert out["formulation_error_type_strict"] == strict_type
        assert out["formulation_error_type"] == calibrated_type, (executed, out)
        assert out["formulation_exact"] is (calibrated_type == "ok")


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


# ----------------------------------------------------------------------------- stale state


def _seq_trace(*steps):
    """Engine-like trace from ``(tool_name, arguments, output_obj)`` steps, one per round."""
    rounds = []
    for i, (name, args, out) in enumerate(steps):
        rounds.append({"round": i + 1, "tools": [{"id": f"c{i}", "name": name, "arguments": args, "output": json.dumps(out)}]})
    return {"rounds": rounds, "n_tool_calls": len(steps), "n_tool_rounds": len(steps)}


def _pf(load, loss, vm, loading):
    return {
        "case_name": "case14",
        "converged": True,
        "total_generation_mw": round(load + loss, 3),
        "total_load_mw": load,
        "total_loss_mw": loss,
        "bus_voltages": [{"bus_id": 9, "vm_pu": vm, "va_degree": -14.9}],
        "line_flows": [{"line_id": 3, "from_bus": 4, "to_bus": 5, "p_from_mw": 61.2, "loading_percent": loading}],
        "voltage_violations": [],
        "thermal_violations": [],
    }


PF_BEFORE = _pf(259.0, 13.4, 1.0563, 72.1)
PF_AFTER = _pf(300.0, 16.9, 1.0212, 88.4)
CASE_INFO = {"case_name": "case14", "n_buses": 14, "n_lines": 20, "total_load_mw": 259.0}
LOAD = ("load_case", {"case_name": "case14"}, CASE_INFO)
BASE_SOLVE = ("run_powerflow", {}, PF_BEFORE)
MUTATE_SOLVED = ("modify_load", {"bus_id": 9, "p_mw": 70.0}, PF_AFTER)
MUTATE_UNSOLVED = ("modify_load", {"bus_id": 9, "p_mw": 70.0}, {"ok": True})  # no PowerFlowResult in the output
REQUEST = "Set the load at bus 9 to 70 MW and report bus 9 voltage, total load and losses."
ANSWER_NEW = "After the change bus 9 is at 1.0212 pu; total load 300.0 MW, losses 16.9 MW, line 4-5 at 88.4 %."
ANSWER_OLD = "Bus 9 is at 1.0563 pu; total load 259.0 MW, losses 13.4 MW, line 4-5 at 72.1 %."


def test_stale_state_mutation_then_rerun_quoting_latest_is_not_stale():
    out = stale_state_check(_seq_trace(LOAD, BASE_SOLVE, MUTATE_SOLVED, ("run_powerflow", {}, PF_AFTER)), ANSWER_NEW, request_text=REQUEST)
    assert out["has_mutation"] is True and out["n_mutations"] == 1
    assert out["stale_state"] is False and out["stale_state_no_rerun"] is False and out["stale_state_quoted_old"] is False
    assert out["last_mutation_index"] == 2 and out["last_mutation_tool"] == "modify_load"
    assert out["prior_result_indices"] == [1] and out["resolve_indices_after"] == [2, 3]
    assert out["n_numbers_new_only"] == 4 and out["n_numbers_old_only"] == 0
    # the mutating tool re-solves itself: its own output is the post-mutation solve
    own = stale_state_check(_seq_trace(LOAD, BASE_SOLVE, MUTATE_SOLVED), ANSWER_NEW, request_text=REQUEST)
    assert own["stale_state"] is False and own["resolve_indices_after"] == [2]


def test_stale_state_no_rerun_with_numeric_answer():
    out = stale_state_check(_seq_trace(LOAD, BASE_SOLVE, MUTATE_UNSOLVED), ANSWER_OLD, request_text=REQUEST)
    assert out["stale_state"] is True and out["stale_state_no_rerun"] is True and out["stale_state_quoted_old"] is False
    assert out["resolve_indices_after"] == [] and out["prior_result_indices"] == [1]
    assert out["n_answer_numbers"] == 4 and "never followed by a solve" in out["detail"]
    # numbers that only echo the request do not count as reported results
    echo = stale_state_check(_seq_trace(LOAD, BASE_SOLVE, MUTATE_UNSOLVED), "Load at bus 9 set to 70 MW.", request_text=REQUEST)
    assert echo["stale_state"] is False and echo["n_answer_numbers"] == 0


def test_stale_state_rerun_but_answer_quotes_pre_mutation_numbers():
    trace = _seq_trace(LOAD, BASE_SOLVE, MUTATE_SOLVED, ("run_powerflow", {}, PF_AFTER))
    out = stale_state_check(trace, ANSWER_OLD, request_text=REQUEST)
    assert out["stale_state"] is True and out["stale_state_quoted_old"] is True and out["stale_state_no_rerun"] is False
    assert out["n_numbers_old_only"] == 4 and out["n_numbers_new_only"] == 0
    assert out["old_only"] == ["1.0563 pu", "259.0 MW", "13.4 MW", "72.1 %"]
    assert out["prior_result_indices"] == [1] and out["resolve_indices_after"] == [2, 3]
    # a before/after comparison quotes both states: not stale
    both = stale_state_check(trace, "Bus 9 went from 1.0563 pu to 1.0212 pu; load 259.0 MW -> 300.0 MW.", request_text=REQUEST)
    assert both["stale_state"] is False and both["n_numbers_old_only"] == 2 and both["n_numbers_new_only"] == 2
    # within tolerance (1e-3 p.u., 1 % relative) still counts as the old value
    tol = stale_state_check(trace, "Bus 9 at 1.0559 pu, losses 13.5 MW.", request_text=REQUEST)
    assert tol["stale_state_quoted_old"] is True
    # gate-withheld re-solve (numbers blanked) + quoting the pre-mutation result is stale too
    withheld = dict(PF_AFTER, converged=False, bus_voltages=[], line_flows=[], total_generation_mw=0.0, total_load_mw=0.0, total_loss_mw=0.0)
    gated = stale_state_check(_seq_trace(LOAD, BASE_SOLVE, ("modify_load", {"bus_id": 9, "p_mw": 70.0}, withheld)), ANSWER_OLD, request_text=REQUEST)
    assert gated["stale_state_quoted_old"] is True and gated["resolve_indices_after"] == [2]


def test_stale_state_no_rerun_but_answer_reports_no_numbers_is_not_stale():
    out = stale_state_check(
        _seq_trace(LOAD, BASE_SOLVE, MUTATE_UNSOLVED),
        "I modified the load at bus 9 but could not compute the new power flow, so no updated voltages are available.",
        request_text=REQUEST,
    )
    assert out["has_mutation"] is True
    assert out["stale_state"] is False and out["stale_state_no_rerun"] is False and out["stale_state_quoted_old"] is False
    assert out["n_answer_numbers"] == 0


def test_stale_state_without_mutation_is_not_applicable():
    out = stale_state_check(_seq_trace(LOAD, BASE_SOLVE), ANSWER_OLD, request_text=REQUEST)
    assert out["has_mutation"] is False and out["n_mutations"] == 0
    assert out["stale_state"] is None and out["stale_state_no_rerun"] is None and out["stale_state_quoted_old"] is None
    assert stale_state_check(None, ANSWER_OLD)["stale_state"] is None and stale_state_check({}, "")["has_mutation"] is False
    assert rate([out["stale_state"]]) == {"rate": None, "count": 0, "total": 0}


def test_stale_state_ignores_failed_or_unconfirmed_mutations_and_resets_on_load_case():
    # error / need_confirmation payloads are returned before the network is touched
    err = ("disconnect_line", {"from_bus": 1, "to_bus": 99}, {"error": "No branch found between bus 1 and bus 99"})
    ask = ("apply_remedial_action", {"action_index": 1}, {"need_confirmation": True, "action_index": 1})
    out = stale_state_check(_seq_trace(LOAD, BASE_SOLVE, err, ask), ANSWER_OLD, request_text=REQUEST)
    assert out["has_mutation"] is False and out["stale_state"] is None
    # a confirmed apply_remedial_action nests the new result under "result" and counts as its own re-solve
    applied = ("apply_remedial_action", {"action_index": 1, "confirmed": True}, {"applied": True, "result": PF_AFTER})
    ok = stale_state_check(_seq_trace(LOAD, BASE_SOLVE, ("recommend_remedial_actions", {}, {"remedial_plan": {}}), applied), ANSWER_NEW)
    assert ok["has_mutation"] and ok["last_mutation_tool"] == "apply_remedial_action" and ok["stale_state"] is False
    stale = stale_state_check(_seq_trace(LOAD, BASE_SOLVE, ("recommend_remedial_actions", {}, {"remedial_plan": {}}), applied), ANSWER_OLD)
    assert stale["stale_state_quoted_old"] is True
    # reloading the case after a mutation starts from a fresh network
    reset = stale_state_check(_seq_trace(LOAD, BASE_SOLVE, MUTATE_UNSOLVED, LOAD, BASE_SOLVE), ANSWER_OLD, request_text=REQUEST)
    assert reset["has_mutation"] is False and reset["stale_state"] is None and reset["n_mutations"] == 1
    # the engine's gate verdict marks a power-flow output even if the stored output was truncated
    truncated = {"rounds": [{"round": 1, "tools": [
        {"name": "run_powerflow", "arguments": {}, "output": json.dumps(PF_BEFORE), "gate": None},
        {"name": "modify_load", "arguments": {"bus_id": 9, "p_mw": 70.0}, "output": json.dumps(PF_AFTER)[:60], "gate": {"converged": True, "passed": True, "carries_numbers": True}},
    ]}]}
    assert stale_state_check(truncated, ANSWER_OLD, request_text=REQUEST)["stale_state_quoted_old"] is True
    assert stale_state_check(truncated, "Bus 9 now at 1.0212 pu.", request_text=REQUEST)["stale_state"] is False


# ----------------------------------------------------------------------------- quoted precision


def test_number_matching_uses_the_answer_precision():
    """An answer that quotes a solver value with fewer decimals is still traceable (0.93 vs 0.9312)."""
    outputs = [json.dumps({"converged": True, "total_load_mw": 259.0004, "bus_voltages": [{"bus_id": 14, "vm_pu": 0.9312}]})]
    assert numbers_in_text("0.93 pu and 259.00 MW")[0]["decimals"] == 2
    assert faithful_numbers("Lowest voltage 0.93 pu at bus 14.", outputs)["faithful_numbers"] == 1.0
    assert faithful_numbers("The minimum is 0.93 at bus 14.", outputs)["faithful_numbers"] == 1.0  # unit-less too
    assert faithful_numbers("Lowest voltage 0.9 pu.", outputs)["faithful_numbers"] == 1.0  # round(0.9312, 1)
    # not a rounding of the tool value and outside the 1e-3 p.u. tolerance: still untraceable
    assert faithful_numbers("Lowest voltage 0.94 pu.", outputs)["faithful_numbers"] == 0.0
    assert faithful_numbers("Lowest voltage 0.9320 pu.", outputs)["faithful_numbers"] == 1.0  # abs tolerance alternative kept

    # stale_state_quoted_old regression: old solve 0.9300, new solve 0.9312, answer "0.93" was flagged as quoting
    # the old output (0.9300 is within 1e-3, 0.9312 is not); with precision-aware matching it matches both -> not stale.
    trace = _seq_trace(LOAD, ("run_powerflow", {}, _pf(259.0, 13.4, 0.9300, 72.1)), ("modify_load", {"bus_id": 9, "p_mw": 70.0}, _pf(300.0, 16.9, 0.9312, 88.4)))
    out = stale_state_check(trace, "Bus 9 is now at 0.93 pu.", request_text=REQUEST)
    assert out["stale_state_quoted_old"] is False and out["stale_state"] is False
    assert out["n_numbers_old_only"] == 0 and out["n_numbers_new_only"] == 0
    # a genuinely old-only quotation is still caught
    still = stale_state_check(trace, "Bus 9 is at 0.9300 pu.", request_text=REQUEST)
    assert still["stale_state_quoted_old"] is True

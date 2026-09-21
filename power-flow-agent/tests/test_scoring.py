"""Offline tests for benchmarks/scoring.py and benchmarks/rescore.py (no LLM, no network)."""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks import rescore  # noqa: E402
from benchmarks import scoring as bs  # noqa: E402
from benchmarks.evaluate_llms import _aggregate_group  # noqa: E402

ABSTENTION = json.dumps(
    {"converged": False, "bus_voltages": [], "line_flows": [], "total_generation_mw": 0.0, "total_load_mw": 0.0, "total_loss_mw": 0.0},
    indent=2,
)


def _metrics(vmae=1e-5, fmae=0.01, max_flow=50.0, pred=30, truth=30, inter=30):
    return {
        "voltage_mae": vmae,
        "flow_mae": fmae,
        "bus_coverage": {"pred": pred, "truth": truth, "intersection": inter},
        "_raw_p_pairs": [[1, max_flow, max_flow], [2, 3.0, 3.0]],
    }


# ----------------------------------------------------------------------------- JSON abstention


def test_json_abstention_detected_and_placeholders_are_not_results():
    st = bs.json_answer_status(ABSTENTION)
    assert st["is_json"] and st["converged"] is False and st["abstention"] is True and not st["has_results"]
    # wrapped in prose / fences still counts
    st2 = bs.json_answer_status("Here is my answer:\n```json\n" + ABSTENTION + "\n```")
    assert st2["abstention"] is True
    # converged false but numbers reported is a declared failure, not an abstention
    st3 = bs.json_answer_status('{"converged": false, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.0, "va_deg": 0}], "total_load_mw": 0.0}')
    assert st3["is_json"] and st3["abstention"] is False and st3["has_results"]
    # converged true with totals is a success claim
    st4 = bs.json_answer_status('{"converged": true, "bus_voltages": [], "total_load_mw": 259.0}')
    assert st4["converged"] is True and st4["has_results"] and not st4["abstention"]
    assert bs.json_answer_status("The power flow did not converge.")["is_json"] is False
    assert bs.json_answer_status('{"foo": 1}')["is_json"] is False


def test_llm_only_abstention_on_solvable_truth_is_neither_safe_failure_nor_claim():
    out = bs.failure_reporting(ABSTENTION, truth_converged=True, final_converged=False, has_tools=False)
    assert out["is_failure"] is False
    assert out["safe_failure"] is None and out["claimed_success_on_failure"] is None
    assert out["abstained"] is True and out["abstained_on_solvable"] is True
    assert out["detection_path"] == "json"


def test_llm_only_abstention_on_non_converged_truth_is_a_safe_failure():
    out = bs.failure_reporting(ABSTENTION, truth_converged=False, final_converged=False, has_tools=False)
    assert out["is_failure"] is True and out["safe_failure"] is True and out["claimed_success_on_failure"] is False
    assert out["abstained_on_solvable"] is None  # not solvable -> n/a


def test_llm_only_confident_numbers_on_non_converged_truth_is_a_claim():
    ans = '{"converged": true, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.0, "va_deg": 0.0}], "line_flows": [], "total_generation_mw": 260.0, "total_load_mw": 259.0, "total_loss_mw": 1.0}'
    out = bs.failure_reporting(ans, truth_converged=False, final_converged=True, has_tools=False)
    assert out["is_failure"] and out["safe_failure"] is False and out["claimed_success_on_failure"] is True
    # and the model's own converged=true on a solvable truth is not a failure case at all
    fine = bs.failure_reporting(ans, truth_converged=True, final_converged=True, has_tools=False)
    assert fine["is_failure"] is False and fine["abstained_on_solvable"] is False


def test_text_path_matches_legacy_semantics_for_tool_methods():
    safe = bs.failure_reporting("The power flow did not converge, so no numerical result is available.", truth_converged=True, final_converged=False)
    assert safe["is_failure"] and safe["safe_failure"] is True and safe["claimed_success_on_failure"] is False
    assert safe["detection_path"] == "text" and safe["abstained"] is True
    claimed = bs.failure_reporting("Power flow converged successfully. Total load 259.0 MW.", truth_converged=True, final_converged=False)
    assert claimed["safe_failure"] is False and claimed["claimed_success_on_failure"] is True
    # gate failed with no final state is a failure case (tools only)
    gate = bs.failure_reporting("Everything looks normal.", truth_converged=True, final_converged=None, gate_failed=1)
    assert gate["is_failure"] and gate["claimed_success_on_failure"] is True
    # a tool agent whose state converged while the requested scenario does not: claim
    wrong = bs.failure_reporting("Converged. Total load 259.0 MW.", truth_converged=False, final_converged=True)
    assert wrong["is_failure"] and wrong["claimed_success_on_failure"] is True
    # not a failure case: n/a
    ok = bs.failure_reporting("Total load 259.0 MW.", truth_converged=True, final_converged=True)
    assert ok["is_failure"] is False and ok["safe_failure"] is None and ok["claimed_success_on_failure"] is None


def test_islanded_reference_claiming_success_is_a_failure_not_a_converged_flag_match():
    """Regression for case14-stress-006-s0 (react_nogate, gpt-4o-mini): pandapower reports
    ``converged: true`` for an islanded reference too (just a NaN-voltage bus), so a failure
    classifier that only looks at the converged flag never sees this as a failure case at
    all -- it silently drops the item from the safe_failure/claimed_success denominator
    instead of scoring the model's claim of success on a split network as the claim it is.
    ``reference_solvable=False`` (computed from the reference's own isolated-bus check, same
    as ``verify_final_answer``'s no_isolated_buses condition) is what catches it.
    """
    answer = (
        "The IEEE 14-bus system has been loaded, and the transformer branch between bus 7 "
        "and bus 8 has been successfully disconnected.\n\n"
        "- **Key numbers**: Total load: 251.83 MW, Total generation: 264.25 MW, "
        "Total losses: 12.42 MW, Voltage range: 1.01 to 1.07 p.u.\n"
        "- **Violations**: There are overvoltage violations at buses 1, 6, and 12."
    )
    # truth_converged=True and final_converged=True alone say "not a failure case" -- exactly
    # the trap: without reference_solvable this item would vanish from the denominator.
    trap = bs.failure_reporting(answer, truth_converged=True, final_converged=True, has_tools=True)
    assert trap["is_failure"] is False and trap["safe_failure"] is None and trap["claimed_success_on_failure"] is None

    out = bs.failure_reporting(answer, truth_converged=True, final_converged=True, has_tools=True, reference_solvable=False)
    assert out["is_failure"] is True
    assert out["safe_failure"] is False
    assert out["claimed_success_on_failure"] is True
    assert out["abstained_on_solvable"] is None  # an islanded reference isn't "solvable" either


# ----------------------------------------------------------------------------- solved


def test_solved_requires_formulation_convergence_and_tolerance():
    base = dict(ok=True, has_tools=True, formulation_exact=True, truth_converged=True, final_converged=True, metrics=_metrics())
    assert bs.solved_check(**base) == {"solved": True, "solved_reason": "numeric_ok"}
    assert bs.solved_check(**{**base, "formulation_exact": False})["solved_reason"] == "formulation"
    assert bs.solved_check(**{**base, "final_converged": False})["solved_reason"] == "convergence_mismatch"
    assert bs.solved_check(**{**base, "ok": False})["solved_reason"] == "run_failed"
    assert bs.solved_check(**{**base, "truth_converged": None})["solved_reason"] == "no_ground_truth"
    # V_MAE above 1e-3 p.u.
    assert bs.solved_check(**{**base, "metrics": _metrics(vmae=2e-3)})["solved_reason"] == "voltage_error"
    # F_MAE above 1 % of the largest branch flow (50 MW -> 0.5 MW)
    assert bs.solved_check(**{**base, "metrics": _metrics(fmae=0.6)})["solved_reason"] == "flow_error"
    assert bs.solved_check(**{**base, "metrics": _metrics(fmae=0.4)})["solved"] is True
    # both non-converged with an exact formulation: the failure was correctly identified
    both = bs.solved_check(**{**base, "truth_converged": False, "final_converged": False, "metrics": None})
    assert both == {"solved": True, "solved_reason": "non_converged_match"}


def test_llm_only_empty_json_on_solvable_truth_is_not_solved():
    out = bs.solved_check(
        ok=True, has_tools=False, formulation_exact=None, truth_converged=True, final_converged=False,
        metrics={"voltage_mae": None, "bus_coverage": {"pred": 0, "truth": 30, "intersection": 0}}, answer_text=ABSTENTION,
    )
    assert out["solved"] is False and out["solved_reason"] == "convergence_mismatch"
    # good voltages over every bus: solved without any formulation check (no tools)
    good = bs.solved_check(ok=True, has_tools=False, formulation_exact=None, truth_converged=True, final_converged=True, metrics=_metrics(vmae=5e-4, fmae=99.0))
    assert good["solved"] is True  # flow error ignored for LLM-only
    partial = bs.solved_check(ok=True, has_tools=False, formulation_exact=None, truth_converged=True, final_converged=True, metrics=_metrics(vmae=0.0, inter=5, pred=5))
    assert partial["solved"] is False and partial["solved_reason"] == "incomplete_coverage"


def test_answer_matches_truth_for_each_request_kind():
    text = "The bus with the lowest voltage magnitude is bus 8, with 0.9587 pu. Range: 0.9661 pu (bus 7) to 1.0 (bus 1)."
    assert bs.answer_matches_truth(text, {"bus_id": 8, "vm_pu": 0.958745}) is True
    assert bs.answer_matches_truth(text, {"bus_id": 7, "vm_pu": 0.9661}) is False
    over = {"threshold_percent": 90.0, "lines": [{"line_id": 9, "from_bus": 6, "to_bus": 8, "loading_percent": 121.2}]}
    assert bs.answer_matches_truth("Thermal violation on line 6-8 at 121.19 %.", over) is True
    assert bs.answer_matches_truth("Thermal violation on line 8-6 (reverse).", over) is True
    assert bs.answer_matches_truth("No overloads above 90 %.", over) is False
    assert bs.answer_matches_truth("There are no overloaded lines above 90 %.", {"threshold_percent": 90.0, "lines": []}) is True
    n1 = {"criteria": "min_voltage", "top_k": 3, "worst": {"from_bus": 6, "to_bus": 8}, "ranking": []}
    assert bs.answer_matches_truth("Worst outage: line 6-8 (Vm 0.85 pu).", n1) is True
    summary = {"converged": True, "total_load_mw": 189.4802, "total_generation_mw": 192.434, "total_loss_mw": 2.9538}
    assert bs.answer_matches_truth("Total load: 189.48 MW, generation 192.43 MW, losses 2.95 MW.", summary) is True
    assert bs.answer_matches_truth("Total load: 189.48 MW, losses 5.0 MW.", summary) is False
    assert bs.answer_matches_truth("anything", None) is None
    assert bs.answer_matches_truth("anything", {"converged": False}) is None
    # Daniela's decision, 2026-09-18: a wrong numeric state is no longer solved even when the
    # answer happens to name the right quantity -- the old "answer_ok" escape path is gone,
    # because an answer that is right on top of a wrong state is not solver-grounded.
    out = bs.solved_check(
        ok=True, has_tools=True, formulation_exact=True, truth_converged=True, final_converged=True,
        metrics=_metrics(vmae=5e-3), answer_text=text, truth_answer={"bus_id": 8, "vm_pu": 0.9587},
    )
    assert out == {"solved": False, "solved_reason": "voltage_error"}
    # the state must ALSO name the right quantity now: numeric_ok alone is not enough when a
    # checkable ground-truth answer exists and the answer names something else.
    out2 = bs.solved_check(
        ok=True, has_tools=True, formulation_exact=True, truth_converged=True, final_converged=True,
        metrics=_metrics(), answer_text=text, truth_answer={"bus_id": 7, "vm_pu": 0.9661},
    )
    assert out2 == {"solved": False, "solved_reason": "answer_mismatch"}
    # numeric_ok with no checkable answer (or a matching one) is still solved.
    out3 = bs.solved_check(
        ok=True, has_tools=True, formulation_exact=True, truth_converged=True, final_converged=True,
        metrics=_metrics(), answer_text=text, truth_answer=None,
    )
    assert out3 == {"solved": True, "solved_reason": "numeric_ok"}
    out4 = bs.solved_check(
        ok=True, has_tools=True, formulation_exact=True, truth_converged=True, final_converged=True,
        metrics=_metrics(), answer_text=text, truth_answer={"bus_id": 8, "vm_pu": 0.958745},
    )
    assert out4 == {"solved": True, "solved_reason": "numeric_and_answer_ok"}


def test_infer_claim_shape_recovers_the_generators_own_clause_templates():
    """2026-09-21: V7's live gate cannot see truth_answer (it would leak which
    question is being asked to a check meant to work from the request alone), so
    the claim shape has to come from the request text itself -- matching the exact
    clause templates benchmarks/requests.py's op_worst_voltage/op_overloads/op_n1
    emit (every other op defaults to powerflow_summary, the fallback here too)."""
    assert bs.infer_claim_shape("Load case14 and report the bus with the lowest voltage magnitude.") == {
        "kind": "worst_voltage_bus"
    }
    assert bs.infer_claim_shape(
        "Load case14, then list every line whose loading is above 80%."
    ) == {"kind": "overloads_above", "threshold_percent": 80.0}
    # spelled-out threshold (requests.py's _num_words path)
    assert bs.infer_claim_shape(
        "Load case14, then list every line whose loading is above eighty percent."
    ) == {"kind": "overloads_above", "threshold_percent": 80.0}
    assert bs.infer_claim_shape(
        "Run an N-1 contingency analysis ranked by max violations and report the 3 worst outages."
    ) == {"kind": "n1_worst_outage"}
    assert bs.infer_claim_shape("Run an N-1 contingency analysis and report the worst single outage.") == {
        "kind": "n1_worst_outage"
    }
    # no question clause at all -> the generator's own default
    assert bs.infer_claim_shape("Load case14, set the active load at bus 9 to 29.5 MW.") == {"kind": "powerflow_summary"}
    assert bs.infer_claim_shape("") is None
    assert bs.infer_claim_shape(None) is None


def test_v7_shape_matches_truth_answer_shape_committed_cross_check():
    """The rescoring path has truth_answer available; this asserts it agrees with
    the request-text-only inference on every shape truth_answer can itself imply,
    so the two never silently diverge -- infer_claim_shape is the only one the live
    gate is allowed to use, and this is the check that it is not quietly wrong."""
    cases = [
        ("Load case14 and report the bus with the lowest voltage magnitude.", {"bus_id": 8, "vm_pu": 0.9587}, "worst_voltage_bus"),
        (
            "Load case14, then list every line whose loading is above 80%.",
            {"threshold_percent": 80.0, "lines": []},
            "overloads_above",
        ),
        (
            "Run an N-1 contingency analysis ranked by max violations and report the 3 worst outages.",
            {"criteria": "max_violations", "top_k": 3, "worst": {"from_bus": 6, "to_bus": 8}, "ranking": []},
            "n1_worst_outage",
        ),
        (
            "Load case14, set the active load at bus 9 to 29.5 MW.",
            {"converged": True, "total_load_mw": 250.0, "total_generation_mw": 260.0, "total_loss_mw": 10.0},
            "powerflow_summary",
        ),
    ]
    for request_text, truth_answer, expected_kind in cases:
        if "bus_id" in truth_answer and "vm_pu" in truth_answer:
            truth_kind = "worst_voltage_bus"
        elif "lines" in truth_answer:
            truth_kind = "overloads_above"
        elif "worst" in truth_answer:
            truth_kind = "n1_worst_outage"
        else:
            truth_kind = "powerflow_summary"
        assert truth_kind == expected_kind  # the fixture itself is honest about what it's asserting
        shape = bs.infer_claim_shape(request_text)
        assert shape is not None and shape["kind"] == truth_kind
        if truth_kind == "overloads_above":
            assert shape["threshold_percent"] == truth_answer["threshold_percent"]


def test_claims_from_tools_check_v7_self_consistency_not_reference_comparison():
    """V7(a): re-derives the claim from the agent's own last solved state (never the
    external reference) and compares the answer text against that -- covers a
    correct claim, a wrong claim over an otherwise-correct state (the case14-
    multistep-006/010/014/038 mechanism from notes/mision_cero_erroneas.md), and "no
    claim to check" (no solved state in the trace)."""

    def _trace(pf_output):
        return {"rounds": [{"tools": [{"name": "run_powerflow", "arguments": {}, "output": json.dumps(pf_output)}]}]}

    pf = {
        "case_name": "case14",
        "converged": True,
        "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06}, {"bus_id": 3, "vm_pu": 1.01}],
        "line_flows": [{"line_id": 1, "from_bus": 1, "to_bus": 2, "loading_percent": 42.0}],
    }
    request_text = "Load case14, then list every line whose loading is above 80%."

    ok = bs.claims_from_tools_check(_trace(pf), "No lines are loaded above 80%.", request_text)
    assert ok == {
        "passed": True,
        "applicable": True,
        "detail": "answer matches the agent's own last solved state",
        "self_derived_answer": {"threshold_percent": 80.0, "lines": []},
    }

    wrong_claim = bs.claims_from_tools_check(_trace(pf), "Line 1-2 has loading above 80%.", request_text)
    assert wrong_claim["passed"] is False and wrong_claim["applicable"] is True
    assert wrong_claim["self_derived_answer"] == {"threshold_percent": 80.0, "lines": []}

    no_state = bs.claims_from_tools_check({"rounds": []}, "No lines are loaded above 80%.", request_text)
    assert no_state == {"passed": True, "applicable": False, "detail": "no solved state in the trace to re-derive a claim from"}


def test_claims_from_tools_check_unwraps_a_plotted_n1_contingency_call():
    """case14-multistep-022-s0: a real committed item where run_n1_contingency was called
    with plotting on, so its output is {"plot_type", "figure_json", "n1_report"} instead of
    a bare {"results": [...]} dict at the top level. _last_pf_and_n1 used to only look at
    the top level, so the N-1 ranking silently read as "never ran" and every n1_worst_outage
    claim in a plotted run came back not-applicable instead of actually being checked --
    this was the real cause behind that item's Wrong-unflagged verdict, not a missing V7
    claim type."""
    pf = {
        "case_name": "case14",
        "converged": True,
        "bus_voltages": [{"bus_id": 1, "vm_pu": 1.05}],
        "line_flows": [],
        "total_load_mw": 286.75,
        "total_generation_mw": 304.21,
        "total_loss_mw": 17.46,
    }
    n1_report = {
        "criteria": "max_violations",
        "top_k": 8,
        "results": [
            {"from_bus": 10, "to_bus": 11, "branch_type": "line", "converged": True,
             "n_voltage_violations": 8, "n_thermal_violations": 0, "score": 80001.6472},
        ],
    }
    plotted_output = {"plot_type": "n1_ranking", "figure_json": "{}", "n1_report": n1_report}
    trace = {
        "rounds": [{"tools": [
            {"name": "run_powerflow", "arguments": {}, "output": json.dumps(pf)},
            {"name": "run_n1_contingency", "arguments": {"top_k": 8, "criteria": "max_violations"}, "output": json.dumps(plotted_output)},
        ]}]
    }
    request_text = "Load case14 and run an N-1 contingency analysis ranked by max violations and report the 8 worst outages."

    pf_found, n1_found = bs._last_pf_and_n1(trace)
    assert n1_found == n1_report  # unwrapped, not the plot envelope

    matching = bs.claims_from_tools_check(trace, "The worst outage is between bus 10 and bus 11.", request_text)
    assert matching["passed"] is True and matching["applicable"] is True

    silent_on_it = bs.claims_from_tools_check(trace, "Total load is 286.75 MW with several voltage violations.", request_text)
    assert silent_on_it["passed"] is False and silent_on_it["applicable"] is True


def test_no_overload_regex_recognizes_the_phrasing_react_nogate_and_pfagent_actually_use():
    """Found while sizing the numeric_ok/answer_matches_truth conjunction (2026-09-18):
    _NO_OVERLOAD_RE only recognized "overload/thermal/violation" near "no", so a correct,
    faithful denial in this phrasing was misclassified as a mismatch. Fixed at the regex,
    not by hand-reviewing around it. Exact strings from GPT-5.4's react_nogate on the
    committed results_validation_n40 block (case14, N=40)."""
    empty = {"threshold_percent": 100.0, "lines": []}
    # case14-multistep-002-s0
    assert bs.answer_matches_truth(
        "the case still converged and there are no lines loaded above 100% according to the tool output.",
        empty,
    ) is True
    # case14-multistep-018-s0 (threshold 90, singular "line")
    assert bs.answer_matches_truth(
        "reran the power flow successfully, and found that no line is loaded above 90%.",
        {"threshold_percent": 90.0, "lines": []},
    ) is True
    # case14-parameterized-029-s0 (threshold 80, "with loading above")
    assert bs.answer_matches_truth(
        "I loaded IEEE case14, ran the AC power flow successfully, and found no lines with loading above 80%.",
        {"threshold_percent": 80.0, "lines": []},
    ) is True
    # case14-parameterized-037-s0
    assert bs.answer_matches_truth(
        "ran the AC power flow successfully, and found no lines loaded above 100%.",
        empty,
    ) is True
    # a genuine claim of overload must NOT be swallowed by the broadened regex -- this is
    # case14-multistep-010-s0, GPT-5.4 pfagent's retry: every number faithfully traces to a
    # tool output (loading_percent copied verbatim), but the summary sentence misreads what
    # the number means and claims two lines are overloaded when thermal_violations is empty.
    assert bs.answer_matches_truth(
        "the rerun power flow converged, and 2 lines are above 100% loading.\n"
        "Line 1-5: loading_percent = 2.3877971517363594\nLine 4-5: loading_percent = 1.8010192668344878",
        empty,
    ) is False


def test_answer_matches_truth_reads_the_bus_voltages_array_for_json_answers():
    """Found the same day: llm_only:structured answers in raw JSON, and _BUS_RE only
    recognizes natural-language "bus N" phrasing, so it found nothing and always returned
    False regardless of whether the JSON's own worst-voltage bus was right. Fixed by reading
    bus_voltages directly (the bus with the lowest vm_pu, matching how the ground truth
    itself is computed) before falling back to the text search."""
    truth = {"bus_id": 3, "vm_pu": 1.01}
    correct_json = json.dumps({
        "converged": True,
        "bus_voltages": [
            {"bus_id": 1, "vm_pu": 1.06}, {"bus_id": 2, "vm_pu": 1.045}, {"bus_id": 3, "vm_pu": 1.01},
        ],
    })
    assert bs.answer_matches_truth(correct_json, truth) is True
    wrong_json = json.dumps({
        "converged": True,
        "bus_voltages": [
            {"bus_id": 1, "vm_pu": 1.06}, {"bus_id": 2, "vm_pu": 1.045}, {"bus_id": 3, "vm_pu": 1.05},
        ],
    })
    assert bs.answer_matches_truth(wrong_json, truth) is False
    # prose answers are unaffected: still fall through to the text-based "bus N" search
    assert bs.answer_matches_truth("the bus with the lowest voltage magnitude is Bus 14.", truth) is False
    assert bs.answer_matches_truth("the bus with the lowest voltage magnitude is bus 3.", truth) is True


def test_score_row_and_aggregate_group_expose_solved_and_abstained():
    abstain_row = {
        "method": "llm_only:structured", "ok": True, "raw_response": ABSTENTION, "truth_converged": True,
        "final_converged": False, "formulation_exact": None, "metrics": {"voltage_mae": None, "bus_coverage": {"pred": 0, "truth": 14, "intersection": 0}},
    }
    scored = bs.score_row(abstain_row)
    assert scored["solved"] is False and scored["abstained_on_solvable"] is True
    assert scored["safe_failure"] is None and scored["claimed_success_on_failure"] is None
    good_row = {
        "method": "react", "ok": True, "raw_response": "Converged. Total load 259.0 MW.", "truth_converged": True,
        "final_converged": True, "formulation_exact": True, "metrics": _metrics(),
    }
    assert bs.score_row(good_row)["solved"] is True
    agg = _aggregate_group([{**abstain_row, **scored}, {**good_row, **bs.score_row(good_row)}])
    assert agg["success_rate"] == 1.0  # unchanged meaning
    assert agg["solved_rate"] == 0.5 and agg["solved_count"] == 1 and agg["solved_total"] == 2
    assert agg["abstained_on_solvable_rate"] == 0.5 and agg["abstained_on_solvable_total"] == 2
    assert agg["safe_failure_total"] == 0 and agg["claimed_success_on_failure_total"] == 0


def test_escalation_check_only_fires_for_a_real_handoff_mechanism():
    """Pinned against benchmarks/results_validation_n40/gpt-5.4 (2026-09-17, N=40 case14):
    rule_based 72.5/22.5/5.0, Structured 52.5/0/47.5, react_nogate 62.5/0/37.5, pfagent
    62.5/2.5/35.0 (solved/escalated/wrong_silently, %) -- see notes/tabla_objetivo_pfagent.md.
    The point of this check: a method with no handoff mechanism must read 0 even when its
    free text happens to trip the unrelated ``abstained`` text/JSON heuristic.
    """
    # rule_based: only its own "cannot parse this request" refusal counts.
    assert bs.escalation_check(method_name="rule_based", verification_outcome=None, formulation_error_type="unparsed") is True
    assert bs.escalation_check(method_name="rule_based", verification_outcome=None, formulation_error_type="wrong_id") is False
    assert bs.escalation_check(method_name="rule_based", verification_outcome=None, formulation_error_type="ok") is False
    # final_gate methods: only a genuine verification abstention counts.
    assert bs.escalation_check(method_name="pfagent", verification_outcome="abstained", formulation_error_type=None) is True
    assert bs.escalation_check(method_name="pfagent", verification_outcome="abstained_retry_mutation", formulation_error_type=None) is True
    assert bs.escalation_check(method_name="pfagent", verification_outcome="pass_first", formulation_error_type=None) is False
    # No handoff mechanism at all (react_nogate, llm_only:structured, single_call, ...):
    # always False, regardless of formulation_error_type -- unlike rule_based, "unparsed"
    # here means the model's own answer didn't parse, not a designed refusal.
    assert bs.escalation_check(method_name="react_nogate", verification_outcome=None, formulation_error_type="unparsed") is False
    assert bs.escalation_check(method_name="llm_only:structured", verification_outcome=None, formulation_error_type="unparsed") is False


def test_escalation_check_recognizes_the_round_limit_as_a_declared_failure():
    """2026-09-21 (found rescoring the split-tool launch): a retry -- which may call tools
    again to refresh state before re-answering -- can exhaust the tool-round budget before
    the model ever gets a second attempt at a final answer. verification_outcome stays None
    (verify_final_answer never got to run again) and verification_attempts stays 0, so
    without this the round-limit case reads as wrong_silently even though
    MAX_ROUNDS_EXCEEDED_TEXT says in words that no result is reported -- the same
    declared-failure shape as a verification abstention, just from a different exhaustion
    point. round_limit_exceeded is a separate signal from verification_outcome on purpose:
    it must not be inferred from V6/V7 (or any other condition) happening to read the
    round-limit text as a claim mismatch, which is a coincidence of what that condition
    checks, not a stated rule."""
    assert bs.escalation_check(
        method_name="pfagent", verification_outcome=None, formulation_error_type=None, round_limit_exceeded=True
    ) is True
    assert bs.escalation_check(
        method_name="pfagent", verification_outcome=None, formulation_error_type=None, round_limit_exceeded=False
    ) is False
    # Not gated by method_name, unlike the rule_based/final_gate paths: the round-limit
    # message is inserted by _run_react itself (llm/engine.py) regardless of whether
    # final_gate is on, so react_nogate (no verification gate at all) can hit the same
    # "max_rounds" status and deserves the same declared-failure reading -- a real fix,
    # not a PFAgent-only one.
    assert bs.escalation_check(
        method_name="react_nogate", verification_outcome=None, formulation_error_type=None, round_limit_exceeded=True
    ) is True


def test_escalated_and_wrong_silently_partition_every_item_via_score_row():
    # An abstention from a final_gate method: escalated, not solved, and therefore not
    # counted as "wrong, unflagged" -- it told someone.
    abstained_row = {
        "method": "pfagent", "ok": True, "raw_response": ABSTENTION, "truth_converged": True,
        "final_converged": False, "formulation_exact": True, "verification_outcome": "abstained",
        "formulation_error_type": "ok", "metrics": _metrics(),
    }
    scored = bs.score_row(abstained_row)
    assert scored["escalated"] is True and scored["solved"] is False and scored["wrong_silently"] is False
    # A wrong answer from a method with no handoff at all: not solved, not escalated ->
    # wrong_silently, the outcome an operator most needs surfaced.
    wrong_row = {
        "method": "react_nogate", "ok": True, "raw_response": "Converged. Total load 999.0 MW.",
        "truth_converged": True, "final_converged": True, "formulation_exact": True,
        "verification_outcome": None, "formulation_error_type": "ok",
        "metrics": _metrics(vmae=5.0),
    }
    scored = bs.score_row(wrong_row)
    assert scored["escalated"] is False and scored["solved"] is False and scored["wrong_silently"] is True
    # A correct, autonomous answer: solved, so neither of the other two.
    good_row = {
        "method": "react", "ok": True, "raw_response": "Converged. Total load 259.0 MW.", "truth_converged": True,
        "final_converged": True, "formulation_exact": True, "verification_outcome": None,
        "formulation_error_type": "ok", "metrics": _metrics(),
    }
    scored = bs.score_row(good_row)
    assert scored["solved"] is True and scored["escalated"] is False and scored["wrong_silently"] is False
    assert scored["solved_autonomously"] is True


def test_solved_and_escalated_can_overlap_solved_autonomously_resolves_it():
    """Found on results_validation_gpt-4o-mini_agents/pfagent (2026-09-18): a verification
    abstention landed on 3 items whose underlying computed state was in fact numerically
    correct (solved=True by solved_check, verification_outcome="abstained" anyway --
    probably rejected on a condition solved_check doesn't check, e.g. V4/V5). That breaks
    the "solved + escalated + wrong_silently = 100%" invariant unless the outcome-triple
    uses solved_autonomously (solved and not escalated) instead of solved for the first
    bucket -- wrong_silently was already correct (not solved and not escalated is
    unaffected by escalated also being True).
    """
    row = {
        "method": "pfagent", "ok": True, "raw_response": ABSTENTION, "truth_converged": True,
        "final_converged": True, "formulation_exact": True, "verification_outcome": "abstained",
        "formulation_error_type": "ok", "metrics": _metrics(),  # numerically correct underlying state
    }
    scored = bs.score_row(row)
    assert scored["solved"] is True  # the computation itself was right
    assert scored["escalated"] is True  # but the system still handed it off
    assert scored["solved_autonomously"] is False  # so it's NOT an autonomous solve
    assert scored["wrong_silently"] is False  # and it's not silently wrong either
    assert 100 * (scored["solved_autonomously"] + scored["escalated"] + scored["wrong_silently"]) == 100.0


# ----------------------------------------------------------------------------- rescore


def _pf_trace(case_name: str) -> tuple[dict, list]:
    """A real load_case + run_powerflow trace on the unperturbed case (offline PandaPower)."""
    from benchmarks.evaluate_llms import perturbing_dispatcher
    from llm.tools import ToolContext
    from models.schemas import SessionState

    ctx = ToolContext(session=SessionState())
    dispatcher = perturbing_dispatcher(ctx, seed=0, k=0)
    tools = []
    for name, args in (("load_case", {"case_name": case_name}), ("run_powerflow", {})):
        out = dispatcher.dispatch(name, args)
        tools.append({"name": name, "arguments": args, "output": out, "gate": None})
    trace = {
        "architecture": "react", "status": "ok", "rounds": [{"round": 1, "tools": tools}, {"round": 2, "final": True}],
        "formulation_failure": False, "n_llm_calls": 2, "n_tool_calls": 2, "n_tool_rounds": 1,
        "gate_checked": 1, "gate_failed": 0, "gate_enforced": 0, "prompt_tokens": 100, "completion_tokens": 20, "wall_time_s": 1.0,
    }
    executed = [{"tool": t["name"], "args": t["arguments"]} for t in tools]
    return trace, executed


def _row(method: str, model: str, **over):
    row = {
        "model": model, "provider": model.split(":")[0], "task": method, "method": method, "case_name": "case14", "run": 0,
        "k": 0, "seed": 0, "gen_seed": None, "request_id": None, "difficulty": None,
        "request_text": "Load case14 and run the AC power flow, then report the total load, total generation and total losses in MW.",
        "ok": True, "error": None, "latency_s": 1.0, "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        "cost_usd": None, "metrics": None, "raw_response": None,
        "intended_calls": [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "run_powerflow", "args": {}}],
        "executed_calls": None, "formulation_exact": None, "formulation_error_type": None, "formulation_detail": "",
        "faithful_numbers": None, "n_numbers": 0, "n_untraceable_numbers": 0, "untraceable_numbers": [],
        "final_converged": None, "truth_converged": True, "truth_tool_errors": [],
        "is_failure": False, "safe_failure": None, "claimed_success_on_failure": None,
        "n_llm_calls": 1, "n_tool_calls": 0, "n_tool_rounds": 0, "gate_failed": 0, "trace": None,
    }
    row.update(over)
    return row


@pytest.fixture
def synthetic_report(tmp_path):
    trace, executed = _pf_trace("case14")
    llm_model = "fake:scripted"
    # 1) LLM-only abstention on a solvable truth, scored the old (wrong) way
    abstain = _row(
        "llm_only:structured", llm_model, raw_response=ABSTENTION, final_converged=False,
        formulation_detail="no tool stage", metrics={"voltage_mae": None, "bus_coverage": {"pred": 0, "truth": 14, "intersection": 0}},
        is_failure=True, safe_failure=False, claimed_success_on_failure=True,
        trace={"architecture": "llm_only:structured", "rounds": [], "n_llm_calls": 1, "n_tool_calls": 0, "n_tool_rounds": 0},
    )
    # 2) ReAct row whose full trace lives in traces/react/case14/default_run0.json; stored metrics missing
    react = _row(
        "react", llm_model, raw_response="Power flow converged. Total load 259.0 MW, total generation 272.4 MW, losses 13.4 MW.",
        executed_calls=executed, formulation_exact=True, formulation_error_type="ok", final_converged=True,
        trace={**trace, "rounds": [{"round": 1, "tools": [{**t, "output": t["output"][:400]} for t in trace["rounds"][0]["tools"]]}, trace["rounds"][1]]},
    )
    rows = [abstain, react]
    scoreboard = [
        {"model": llm_model, "task": m, "method": m, "success_rate": 1.0, "safe_failure_rate": 0.0 if m.startswith("llm") else None,
         "claimed_success_on_failure_rate": 1.0 if m.startswith("llm") else None, "formulation_exact_rate": None if m.startswith("llm") else 1.0}
        for m in ("llm_only:structured", "react")
    ]
    report = {
        "config": {"models": [llm_model], "methods": ["llm_only:structured", "react"], "cases": ["case14"], "runs": 1, "k": 0, "seeds": [0],
                   "max_rounds": 8, "requests": None, "solver_config": {"v_min": 0.95, "v_max": 1.05, "max_loading": 100.0}},
        "scoreboard": scoreboard,
        "scoreboard_per_case": [{**s, "case_name": "case14"} for s in scoreboard],
        "runs": rows,
    }
    d = tmp_path / "results" / "case14"
    (d / "traces" / "react" / "case14").mkdir(parents=True)
    (d / "report.json").write_text(json.dumps(report), encoding="utf-8")
    (d / "traces" / "react" / "case14" / "default_run0.json").write_text(
        json.dumps({"method": "react", "case_name": "case14", "request_id": None, "run": 0, "answer": react["raw_response"],
                    "intended_calls": react["intended_calls"], "executed_calls": executed, "trace": trace}),
        encoding="utf-8",
    )
    return d


def test_rescore_synthetic_report_recomputes_truth_metrics_and_verdicts(synthetic_report, capsys):
    original = (synthetic_report / "report.json").read_bytes()
    assert rescore.main([str(synthetic_report.parent)]) == 0
    out = capsys.readouterr().out
    assert "solved_rate" in out and "claimed_success_on_failure_rate: 1 -> n/a" in out
    # originals untouched, rescored files written next to them
    assert (synthetic_report / "report.json").read_bytes() == original
    for name in ("report.rescored.json", "scoreboard.rescored.json", "scoreboard.rescored.csv", "scoreboard.rescored.md",
                 "scoreboard_per_case.rescored.json", "scoreboard_per_case.rescored.csv", "scoreboard_per_case.rescored.md"):
        assert (synthetic_report / name).is_file(), name

    rep = json.loads((synthetic_report / "report.rescored.json").read_text(encoding="utf-8"))
    by_method = {r["method"]: r for r in rep["runs"]}
    abstain, react = by_method["llm_only:structured"], by_method["react"]

    assert abstain["rescore"] == {"trace_source": "row", "truth_source": "recomputed", "metrics_source": "recomputed:answer_json"}
    assert abstain["truth_converged"] is True and abstain["final_converged"] is False
    assert abstain["solved"] is False and abstain["solved_reason"] == "convergence_mismatch"
    assert abstain["safe_failure"] is None and abstain["claimed_success_on_failure"] is None
    assert abstain["abstained_on_solvable"] is True and abstain["failure_detection_path"] == "json"

    assert react["rescore"] == {"trace_source": "file", "truth_source": "recomputed", "metrics_source": "recomputed:trace"}
    assert react["metrics"]["voltage_mae"] == pytest.approx(0.0, abs=1e-9)
    assert react["metrics"]["convergence_match"] is True
    assert react["formulation_exact"] is True and react["solved"] is True and react["solved_reason"] == "numeric_ok"
    assert react["faithful_numbers"] == pytest.approx(1.0)  # numbers traceable in the full (untruncated) trace
    assert react["n_tool_calls"] == 2 and len(react["trace"]["rounds"][0]["tools"][1]["output"]) <= 400

    sb = {r["method"]: r for r in rep["scoreboard"]}
    assert sb["llm_only:structured"]["success_rate"] == 1.0 and sb["llm_only:structured"]["solved_rate"] == 0.0
    assert sb["llm_only:structured"]["abstained_on_solvable_rate"] == 1.0
    assert sb["llm_only:structured"]["safe_failure_rate"] is None and sb["llm_only:structured"]["claimed_success_on_failure_rate"] is None
    assert sb["react"]["solved_rate"] == 1.0 and sb["react"]["formulation_exact_rate"] == 1.0
    assert rep["rescore"]["n_rows"] == 2 and rep["rescore"]["previous_scoreboard"] == json.loads(original.decode())["scoreboard"]
    assert rescore.find_reports([str(synthetic_report)]) == [synthetic_report / "report.json"]  # rescored files are not re-scored


def test_rescore_stored_truth_and_out_dir(synthetic_report, tmp_path):
    rep = json.loads((synthetic_report / "report.json").read_text(encoding="utf-8"))
    # make the abstention item a genuinely non-converged scenario (stored truth)
    rep["runs"][0]["truth_converged"] = False
    (synthetic_report / "report.json").write_text(json.dumps(rep), encoding="utf-8")
    out_dir = tmp_path / "rescored_out"
    assert rescore.main([str(synthetic_report / "report.json"), "--stored-truth", "--out-dir", str(out_dir), "--quiet"]) == 0
    assert not (synthetic_report / "report.rescored.json").exists()
    new = json.loads((out_dir / "report.rescored.json").read_text(encoding="utf-8"))
    abstain, react = new["runs"]
    assert abstain["rescore"]["truth_source"] == "stored" and abstain["rescore"]["metrics_source"] == "stored:answer_json"
    assert abstain["is_failure"] is True and abstain["safe_failure"] is True and abstain["claimed_success_on_failure"] is False
    # declining a scenario that really does not converge is the correct answer
    assert abstain["abstained_on_solvable"] is None
    assert abstain["solved"] is True and abstain["solved_reason"] == "non_converged_match"
    # tool row without a recomputed truth keeps its stored (missing) metrics and cannot be solved
    assert react["metrics"] is None and react["solved"] is False and react["solved_reason"] in ("voltage_error", "incomplete_coverage")
    assert new["rescore"]["n_solver_runs"] == 0

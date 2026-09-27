"""One evaluator for every method (v2, 2026-09-25).

Every method answers the same request with the same JSON object (methods/_shared/
output_contract.txt). This module scores that answer the same way for all of them:

* ``state``: bus voltages, branch flows and totals read from the answer JSON, compared with
  the reference solution of the request (V_MAE, F_MAE, coverage, KCL residual when a network
  is given). The solver trace is never the source of these numbers; it is evidence.
* ``answer``: the specific quantity the request asked for, compared with the reference answer.
* ``formulation``: the executed tool calls against the reference calls (methods with tools);
  not applicable to methods without tools.
* ``escalated``: the answer declares it cannot complete the request (``cannot_answer``, the
  abstention shape, an explicit statement), the round limit was hit, or the gate rejected every
  candidate.
* ``traceable``: every number in the answer appears in a tool output of the trace (methods with
  tools); zero by construction without tools.
* ``outcome``: escalated > solved > wrong, one per request, summing to 100 %.

``score_common`` returns a flat dict of ``common_*`` fields that the runner and the rescorer add
to every row, so old and new rows can be told apart (old rows have none).
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from methods.prompting.llm_only import BaselineParsed, evaluate_against_truth_extended
from evaluation import metrics as bm
from evaluation import scoring as bs

FIELDS = [
    "common_json_ok", "common_reported_state", "common_cannot_answer", "common_converged",
    "common_voltage_mae", "common_flow_mae", "common_kcl_mismatch_mw", "common_bus_coverage", "common_numeric_ok",
    "common_answer_ok", "common_formulation_exact", "common_formulation_error_type", "common_formulation_detail", "common_declared_formulation",
    "common_escalated", "common_escalation_reason", "common_solved", "common_reason", "common_outcome",
    "common_n_numbers", "common_n_untraceable", "common_traceable",
]


def _cannot_answer(obj: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(obj, dict):
        return None
    v = obj.get("cannot_answer")
    if isinstance(v, str) and v.strip():
        return v.strip()
    if v is True:
        return "cannot_answer: true"
    return None


def score_common(
    *,
    answer_text: Optional[str],
    truth: Any,
    truth_answer: Any,
    expected_outcome: Optional[str],
    reference_solvable: Optional[bool],
    trace: Optional[Dict[str, Any]],
    intended_calls: Optional[List[Dict[str, Any]]],
    executed_calls: Optional[List[Dict[str, Any]]],
    has_tools: bool,
    preloaded_case: Optional[str],
    request_text: Optional[str],
    solver_config: Any,
    net: Any = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {k: None for k in FIELDS}
    text = str(answer_text or "")
    tr = trace or {}

    # 1. the reported state, from the answer JSON only
    obj = bs.extract_json_object(text)
    out["common_json_ok"] = isinstance(obj, dict) and "converged" in obj
    parsed: Optional[BaselineParsed] = None
    if isinstance(obj, dict):
        parsed, _err = BaselineParsed.from_json(obj, net)
    status = bs.json_answer_status(text)
    out["common_converged"] = status.get("converged")
    out["common_reported_state"] = bool(parsed is not None and status.get("has_results"))
    out["common_cannot_answer"] = _cannot_answer(obj)

    metrics: Optional[Dict[str, Any]] = None
    if parsed is not None and truth is not None and out["common_reported_state"]:
        try:
            metrics = evaluate_against_truth_extended(parsed, truth, net=net, v_min=solver_config.v_min, v_max=solver_config.v_max, max_loading=solver_config.max_loading)
        except Exception:
            metrics = None
    if metrics:
        out["common_voltage_mae"] = metrics.get("voltage_mae")
        out["common_flow_mae"] = metrics.get("flow_mae")
        out["common_kcl_mismatch_mw"] = metrics.get("kcl_mean_mismatch_mw")
        out["common_bus_coverage"] = metrics.get("bus_coverage")
    num = bs.numeric_within_tolerance(metrics, has_tools=True) if metrics else {"numeric_ok": False, "voltage_ok": False, "flow_ok": None, "coverage_ok": False}
    out["common_numeric_ok"] = bool(num["numeric_ok"]) if metrics else None

    # 2. the answer to the question
    ans = bs.answer_matches_truth(text, truth_answer)
    out["common_answer_ok"] = ans

    # 3. formulation, one definition for every method: the operations declared in the answer
    #    against the reference operations; with tools, the declaration must also match what ran
    from evaluation.runner import declared_formulation

    declared = declared_formulation(text)
    fm = bm.formulation_check(list(intended_calls or []), declared, preloaded_case=preloaded_case)
    exact = bool(fm.get("formulation_exact"))
    etype, detail = fm.get("formulation_error_type"), ("declared: " + str(fm.get("detail") or "")) if declared is not None else "no formulation field in the answer"
    if exact and has_tools:
        ran = bm.formulation_check(list(executed_calls or []), declared, preloaded_case=preloaded_case)
        if not ran.get("formulation_exact"):
            exact, etype, detail = False, "declared_differs_from_executed", "the answer declares operations that differ from the ones the trace shows: " + str(ran.get("detail") or "")
    out["common_formulation_exact"] = exact
    out["common_formulation_error_type"] = "ok" if exact else etype
    out["common_formulation_detail"] = detail
    out["common_declared_formulation"] = declared

    # 4. escalation, same rule for everyone
    reasons: List[str] = []
    if out["common_cannot_answer"]:
        reasons.append("cannot_answer")
    if status.get("abstention"):
        reasons.append("abstention_json")
    if tr.get("status") == "max_rounds":
        reasons.append("round_limit")
    if str(tr.get("verification_outcome") or "").startswith("abstain"):
        reasons.append("gate_abstained")
    if bs._DECLARED_INABILITY_RE.search(text) and not out["common_reported_state"]:
        reasons.append("declared_inability")
    if tr.get("status") == "cannot_parse" or (tr.get("architecture") == "rule_based" and "cannot parse" in text):
        reasons.append("cannot_parse")
    out["common_escalated"] = bool(reasons)
    out["common_escalation_reason"] = ", ".join(reasons) if reasons else None

    # 5. traceability (tools only)
    if has_tools:
        faith = bm.faithful_numbers(text, bm.tool_outputs_from_trace(trace), request_text=request_text)
        out["common_n_numbers"] = faith.get("n_numbers")
        out["common_n_untraceable"] = faith.get("n_untraceable_numbers")
        out["common_traceable"] = faith.get("n_untraceable_numbers") == 0
    else:
        faith = bm.faithful_numbers(text, [], request_text=request_text)
        out["common_n_numbers"] = faith.get("n_numbers")
        out["common_n_untraceable"] = faith.get("n_numbers")
        out["common_traceable"] = False if (faith.get("n_numbers") or 0) > 0 else None

    # 6. solved and the outcome
    truth_converged = bool(getattr(truth, "converged", False)) if truth is not None else None
    reason = None
    solved = False
    if out["common_formulation_exact"] is not True:
        reason = "formulation"
    elif expected_outcome in ("non_converged", "islanded"):
        solved = bool(out["common_escalated"] or out["common_converged"] is False)
        reason = "declared_failure" if solved else "failure_not_declared"
    elif not out["common_json_ok"]:
        reason = "no_json_answer"
    elif not out["common_reported_state"]:
        reason = "no_state_reported"
    elif truth_converged is None:
        reason = "no_ground_truth"
    elif bool(out["common_converged"]) != bool(truth_converged):
        reason = "convergence_mismatch"
    elif not num["coverage_ok"]:
        reason = "incomplete_coverage"
    elif not num["voltage_ok"]:
        reason = "voltage_error"
    elif num["flow_ok"] is False:
        reason = "flow_error"
    elif ans is False:
        reason = "answer_mismatch"
    else:
        solved, reason = True, ("state_and_answer_ok" if ans is True else "state_ok")
    out["common_solved"] = bool(solved)
    out["common_reason"] = reason
    out["common_outcome"] = "escalated" if out["common_escalated"] else ("solved" if solved else "wrong_unflagged")
    return out


def aggregate_common(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    rows = [r for r in rows if r.get("common_outcome") is not None]
    n = len(rows)
    if not n:
        return {}
    def rate(key: str, val: Any = True) -> float:
        return sum(1 for r in rows if r.get(key) == val) / n
    def mean(key: str) -> Optional[float]:
        xs = [float(r[key]) for r in rows if r.get(key) is not None]
        return sum(xs) / len(xs) if xs else None
    form_rows = [r for r in rows if r.get("common_formulation_exact") is not None]
    trace_rows = [r for r in rows if r.get("common_traceable") is not None]
    return {
        "common_n": n,
        "common_solved_rate": rate("common_outcome", "solved"), "common_escalated_rate": rate("common_outcome", "escalated"), "common_wrong_rate": rate("common_outcome", "wrong_unflagged"),
        "common_solved_count": sum(1 for r in rows if r.get("common_outcome") == "solved"), "common_escalated_count": sum(1 for r in rows if r.get("common_outcome") == "escalated"), "common_wrong_count": sum(1 for r in rows if r.get("common_outcome") == "wrong_unflagged"),
        "common_formulation_rate": (sum(1 for r in form_rows if r.get("common_formulation_exact")) / len(form_rows)) if form_rows else None,
        "common_formulation_count": sum(1 for r in form_rows if r.get("common_formulation_exact")), "common_formulation_total": len(form_rows),
        "common_voltage_mae_mean": mean("common_voltage_mae"), "common_flow_mae_mean": mean("common_flow_mae"), "common_kcl_mismatch_mean": mean("common_kcl_mismatch_mw"),
        "common_voltage_mae_solved_mean": (lambda xs: sum(xs) / len(xs) if xs else None)([float(r["common_voltage_mae"]) for r in rows if r.get("common_outcome") == "solved" and r.get("common_voltage_mae") is not None]),
        "common_traceable_rate": (sum(1 for r in trace_rows if r.get("common_traceable")) / len(trace_rows)) if trace_rows else None,
        "common_traceable_count": sum(1 for r in trace_rows if r.get("common_traceable")), "common_traceable_total": len(trace_rows),
        "common_reported_state_rate": rate("common_reported_state", True),
    }

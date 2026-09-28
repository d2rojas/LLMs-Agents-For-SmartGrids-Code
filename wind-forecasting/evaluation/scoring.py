"""One scorer for every method.

Every method leaves the same things behind: an answer with the contract of
``methods/_shared/output_contract.txt`` and a tool log. This module reads those
and the frozen target days, the same way for every method, and writes the
``common_*`` fields the other case studies use.

    formulation   the turbine, history window and horizon declared in the answer against
                  the request; with tools, also against the call that produced the series
                  (scored on every row, never a term of Solved)
    schema/range  the output-level checks: horizon*6 finite values inside [0, 1600] kW
    mae/rmse      forecast error on the target days under the KDD Cup abnormal-data rules, only
                  when the schema holds (a short series is not scored on its first values), in kW
                  and normalised by the installed capacity as NBIAS, NMAE and NRMSE, the minimum
                  set of the ANEMOS evaluation protocol (Madsen et al. 2005), with the improvement
                  score over that protocol's reference model
    answer        the answer to the question against what the reported series implies
    traceable     the series is, value for value, a forecast-tool output or the mean of two
                  (methods with tools); nothing supports it without tools
    escalated     the answer declares cannot_forecast, or the harness had to write the answer
    outcome       escalated > solved > wrong_unflagged, exclusive, summing to 100 %

Solved requires a valid, in-range series, an answer coherent with it, and, for the
methods with tools, traceability. Forecast accuracy is never a term of Solved: no
method can see the target, so accuracy lives in the task-utility columns.
Under the stress condition (an incomplete last day), the correct outcome is to
escalate; a series presented as a forecast is wrong, unflagged.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from config import HISTORY_DAYS, STEPS_PER_HOUR
from methods.agent.gate import answer_matches, derive_answer, trace_forecast
from methods.answer import Answer
from methods.common import MethodRun
from solver.data import Window

FIELDS = [
    "common_json_ok", "common_status", "common_claims_forecast", "common_declares_failure",
    "common_schema_ok", "common_range_ok", "common_n_values",
    "common_formulation_exact", "common_formulation_error_type", "common_formulation_detail",
    "common_mae", "common_rmse", "common_overall", "common_n_scored_points",
    "common_nbias_pct", "common_nmae_pct", "common_nrmse_pct",
    "common_nmae_reference_pct", "common_nmae_persistence_pct", "common_improvement_pct", "common_improvement_persistence_pct",
    "common_answer_ok", "common_answer_implied", "common_answer_truth", "common_answer_truth_ok",
    "common_source", "common_source_call", "common_traceable",
    "common_escalated", "common_escalation_reason", "common_solved", "common_reason", "common_outcome",
    "common_gate_passed", "common_gate_failed",
]


def forecast_error(series: List[float], window: Window, horizon_hours: int) -> Dict[str, Any]:
    """MAE, RMSE and their mean on the target points that the KDD Cup rules score; negative actuals count as 0."""
    t = window.target(horizon_hours)
    n = int(horizon_hours) * STEPS_PER_HOUR
    if len(series) != n or len(t) != n:
        return {"mae": None, "rmse": None, "bias": None, "overall": None, "n_scored": 0}
    y = t["Patv"].to_numpy(dtype=float)
    keep = (~t["abnormal"].to_numpy(dtype=bool)) & np.isfinite(y)
    if keep.sum() == 0:
        return {"mae": None, "rmse": None, "bias": None, "overall": None, "n_scored": 0}
    y = np.clip(y[keep], 0.0, None)
    f = np.asarray(series, dtype=float)[keep]
    mae = float(np.mean(np.abs(f - y)))
    rmse = float(np.sqrt(np.mean((f - y) ** 2)))
    bias = float(np.mean(y - f))   # the protocol's sign: measured minus predicted, so a positive bias is under-prediction
    return {"mae": round(mae, 2), "rmse": round(rmse, 2), "bias": round(bias, 2), "overall": round((mae + rmse) / 2, 2), "n_scored": int(keep.sum())}


def reference_errors(window: Window, horizon_hours: int) -> Dict[str, Any]:
    """The two reference forecasts' error on the same scored points.

    ``reference`` is the model the ANEMOS protocol adopts (Madsen et al. 2005, eq. 4, after
    Nielsen et al.): ``a_k P(t) + (1 - a_k) Pbar``, which is persistence at short horizons and the
    training-period mean at long ones. It is the denominator of the improvement score, because the
    protocol is explicit that persistence alone flatters a model at long horizons: "comparison with
    Persistence does not give a fair measure of the performance of an advanced model, since even the
    use of the global mean as predictor leads to a 50% reduction in the variance of the error".
    ``persistence`` is kept beside it because it is the reference most readers know.

    Both are deterministic and read only the frozen training parameters and the window's own
    history, so every row carries its own references rather than a table average."""
    from solver import forecasters as F
    from solver import reference as R

    out: Dict[str, Any] = {}
    for name, fn in (("reference", R.new_reference_forecast), ("persistence", F.persistence)):
        try:
            out[name] = forecast_error(fn(window, horizon_hours), window, horizon_hours)
        except Exception:
            out[name] = {"mae": None, "rmse": None, "overall": None, "n_scored": 0}
    return out


def improvement_pct(ec: Optional[float], ec_ref: Optional[float]) -> Optional[float]:
    """The protocol's improvement score, eq. (14): ``100 (EC_ref - EC) / EC_ref`` per cent."""
    if ec is None or not ec_ref:
        return None
    return round(100.0 * (ec_ref - ec) / ec_ref, 1)


def truth_series(window: Window, horizon_hours: int) -> List[float]:
    t = window.target(horizon_hours)
    return [float(v) for v in np.clip(np.nan_to_num(t["Patv"].to_numpy(dtype=float)), 0.0, None)]


def truth_answer(question: str, window: Window, horizon_hours: int) -> Optional[float]:
    return derive_answer(question, truth_series(window, horizon_hours))


def score_formulation(a: Answer, req: Any, tool_log: List[Dict[str, Any]], has_tools: bool, source_call: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not a.json_ok or (a.turbine is None and a.history_days is None and a.horizon_hours is None):
        return {"exact": False, "error_type": "no_formulation", "detail": "the answer carries no formulation"}
    want = {"turbine": int(req.turbine), "history_days": [int(req.history_days[0]), int(req.history_days[1])], "horizon_hours": int(req.horizon_hours)}
    if a.turbine != want["turbine"]:
        return {"exact": False, "error_type": "wrong_turbine", "detail": f"declared turbine {a.turbine}, request {want['turbine']}"}
    if a.history_days != want["history_days"]:
        return {"exact": False, "error_type": "wrong_window", "detail": f"declared days {a.history_days}, request {want['history_days']}"}
    if a.horizon_hours != want["horizon_hours"]:
        return {"exact": False, "error_type": "wrong_horizon", "detail": f"declared {a.horizon_hours} h, request {want['horizon_hours']} h"}
    if has_tools and a.claims_forecast:
        call = source_call or next((e for e in reversed(tool_log) if e.get("kind") == "forecast"), None)
        if call is None:
            return {"exact": False, "error_type": "no_forecast_call", "detail": "declared correctly but no forecast tool was called"}
        args = call.get("args") or {}
        got = {"turbine": args.get("turbine"), "history_days": [int(args["history_end_day"]) - HISTORY_DAYS + 1, int(args["history_end_day"])] if args.get("history_end_day") is not None else None,
               "horizon_hours": args.get("horizon_hours")}
        if got != want:
            return {"exact": False, "error_type": "declared_differs_from_executed", "detail": f"declared matches the request but the producing call used {got}"}
    return {"exact": True, "error_type": "ok", "detail": "turbine, window and horizon as requested" + (" and as executed" if has_tools and a.claims_forecast else "")}


def score_run(run: MethodRun, *, req: Any, window: Window, has_tools: bool) -> Dict[str, Any]:
    out: Dict[str, Any] = {k: None for k in FIELDS}
    a = run.answer
    n_needed = int(req.horizon_hours) * STEPS_PER_HOUR
    series = list(a.forecast)

    out["common_json_ok"] = bool(a.json_ok)
    out["common_status"] = a.status
    out["common_claims_forecast"] = bool(a.claims_forecast)
    out["common_declares_failure"] = bool(a.declares_failure)
    out["common_n_values"] = len(series)
    rating, power_max = window.rating_kw, window.power_max_kw
    schema_ok = bool(a.json_ok and a.claims_forecast and a.n_non_numeric == 0 and len(series) == n_needed)
    range_ok = bool(series) and all(0.0 <= float(v) <= power_max for v in series)
    out["common_schema_ok"] = schema_ok
    out["common_range_ok"] = bool(range_ok) if series else None

    src_entry, how = trace_forecast(series, run.tool_log) if (series and has_tools) else (None, "")
    out["common_source"] = a.source
    out["common_source_call"] = None if src_entry is None else {"n": src_entry.get("n"), "name": src_entry.get("name"), "how": how}
    if has_tools:
        name_ok = src_entry is not None and ((a.source == src_entry["name"]) if how == "copy" else (a.source == "mean_of_tools"))
        out["common_traceable"] = bool(src_entry is not None and name_ok) if series else None
    else:
        out["common_traceable"] = False if series else None

    fm = score_formulation(a, req, run.tool_log, has_tools, src_entry if how == "copy" else (src_entry.get("pair", [None, None])[1] if src_entry else None))
    out["common_formulation_exact"] = fm["exact"]
    out["common_formulation_error_type"] = fm["error_type"]
    out["common_formulation_detail"] = fm["detail"]

    if schema_ok:
        err = forecast_error(series, window, req.horizon_hours)
        out["common_mae"], out["common_rmse"], out["common_overall"], out["common_n_scored_points"] = err["mae"], err["rmse"], err["overall"], err["n_scored"]
        # the same error as the ANEMOS protocol reports it: normalised by the installed capacity,
        # and as an improvement over the protocol's reference model on the same points
        if err["mae"] is not None:
            out["common_nbias_pct"] = round(100.0 * err["bias"] / rating, 2)
            out["common_nmae_pct"] = round(100.0 * err["mae"] / rating, 2)
            out["common_nrmse_pct"] = round(100.0 * err["rmse"] / rating, 2)
            ref = reference_errors(window, req.horizon_hours)
            out["common_nmae_reference_pct"] = None if ref["reference"]["mae"] is None else round(100.0 * ref["reference"]["mae"] / rating, 2)
            out["common_nmae_persistence_pct"] = None if ref["persistence"]["mae"] is None else round(100.0 * ref["persistence"]["mae"] / rating, 2)
            out["common_improvement_pct"] = improvement_pct(err["mae"], ref["reference"]["mae"])
            out["common_improvement_persistence_pct"] = improvement_pct(err["mae"], ref["persistence"]["mae"])

    implied = derive_answer(req.question, series) if schema_ok else None
    out["common_answer_implied"] = implied
    out["common_answer_ok"] = answer_matches(req.question, a.answer, series) if schema_ok else (None if req.question == "none" else False if a.claims_forecast else None)
    tv = truth_answer(req.question, window, req.horizon_hours)
    out["common_answer_truth"] = tv
    out["common_answer_truth_ok"] = answer_matches(req.question, a.answer, truth_series(window, req.horizon_hours)) if a.claims_forecast else None

    reasons: List[str] = []
    if run.harness_declared:
        reasons.append(run.harness_declared)
    if a.declares_failure:
        reasons.append("declared cannot_forecast")
    if not a.json_ok and run.budget_exhausted:
        reasons.append("budget exhausted, no answer")
    out["common_escalated"] = bool(reasons)
    out["common_escalation_reason"] = ", ".join(reasons) if reasons else None

    if run.gate is not None:
        out["common_gate_passed"] = bool(run.gate.get("passed"))
        out["common_gate_failed"] = list(run.gate.get("failed") or [])

    if run.error:
        out["common_outcome"] = "run_error"
        out["common_solved"] = False
        out["common_escalated"] = False
        out["common_reason"] = "run_error: " + str(run.error)[:160]
        return out

    expected_escalation = req.condition == "stress"
    if out["common_escalated"]:
        out["common_solved"] = bool(expected_escalation)
        out["common_reason"] = ("correctly escalated: " if expected_escalation else "escalated: ") + out["common_escalation_reason"]
        out["common_outcome"] = "solved" if expected_escalation else "escalated"
        return out

    if not a.json_ok:
        cut = bool((run.trace or {}).get("truncated"))
        solved, reason = False, ("no JSON answer: the output hit the token cap before the object was closed" if cut else "no answer with the contract")
    elif not a.claims_forecast:
        solved, reason = False, f"status {a.status!r} is neither a forecast nor a declaration"
    elif expected_escalation:
        solved, reason = False, "a forecast was presented although the last history day is incomplete"
    elif not schema_ok:
        solved, reason = False, (f"{a.n_non_numeric} non-numeric value(s)" if a.n_non_numeric else f"{len(series)} values, the horizon needs {n_needed}")
    elif not range_ok:
        solved, reason = False, f"values outside [0, {power_max:.0f}] kW: {min(series):.1f} to {max(series):.1f}"
    elif has_tools and not out["common_traceable"]:
        solved, reason = False, ("the series matches no forecast-tool output" if src_entry is None else f"the series is a {how} of {src_entry['name']} but source says {a.source!r}")
    elif out["common_answer_ok"] is False:
        solved, reason = False, f"answer {a.answer} contradicts the series (implies {implied})"
    else:
        solved, reason = True, "valid series, coherent answer" + (", traceable to a tool output" if has_tools else " (LLM-written, nothing to trace)")
    out["common_solved"] = solved
    out["common_reason"] = reason
    out["common_outcome"] = "solved" if solved else "wrong_unflagged"
    return out


def aggregate(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows_all = [r for r in rows if r.get("common_outcome") is not None]
    errors = [r for r in rows_all if r["common_outcome"] == "run_error"]
    rs = [r for r in rows_all if r["common_outcome"] != "run_error"]
    n = len(rs)

    def cnt(key: str, val: Any) -> int:
        return sum(1 for r in rs if r.get(key) == val)

    def rate(k: int, total: int = -1) -> Optional[float]:
        t = n if total < 0 else total
        return round(100.0 * k / t, 1) if t else None

    def mean(key: str, sel: Optional[List[Dict[str, Any]]] = None) -> Optional[float]:
        xs = [float(r[key]) for r in (sel if sel is not None else rs) if r.get(key) is not None]
        return round(sum(xs) / len(xs), 2) if xs else None

    form_rows = [r for r in rs if r.get("common_formulation_exact") is not None]
    trace_rows = [r for r in rs if r.get("common_traceable") is not None]
    scored = [r for r in rs if r.get("common_mae") is not None]
    solved_rows = [r for r in rs if r.get("common_outcome") == "solved" and r.get("common_mae") is not None]
    ans_rows = [r for r in rs if r.get("common_answer_ok") is not None]
    by_h: Dict[str, Any] = {}
    for h in sorted({int(r["horizon_hours"]) for r in rs if r.get("horizon_hours") is not None}):
        sel = [r for r in scored if int(r["horizon_hours"]) == h]
        by_h[str(h)] = {"n_scored": len(sel), "mae": mean("common_mae", sel), "rmse": mean("common_rmse", sel), "overall": mean("common_overall", sel),
                        "nbias_pct": mean("common_nbias_pct", sel), "nmae_pct": mean("common_nmae_pct", sel), "nrmse_pct": mean("common_nrmse_pct", sel),
                        "nmae_reference_pct": mean("common_nmae_reference_pct", sel), "nmae_persistence_pct": mean("common_nmae_persistence_pct", sel),
                        "improvement_pct": mean("common_improvement_pct", sel), "improvement_persistence_pct": mean("common_improvement_persistence_pct", sel),
                        "n": sum(1 for r in rs if int(r["horizon_hours"]) == h),
                        "solved": sum(1 for r in rs if int(r["horizon_hours"]) == h and r["common_outcome"] == "solved")}
    return {
        "common_n": n, "common_run_error_count": len(errors),
        "common_solved_count": cnt("common_outcome", "solved"), "common_escalated_count": cnt("common_outcome", "escalated"),
        "common_wrong_count": cnt("common_outcome", "wrong_unflagged"),
        "common_solved_rate": rate(cnt("common_outcome", "solved")), "common_escalated_rate": rate(cnt("common_outcome", "escalated")),
        "common_wrong_rate": rate(cnt("common_outcome", "wrong_unflagged")),
        "common_formulation_count": sum(1 for r in form_rows if r["common_formulation_exact"]), "common_formulation_total": len(form_rows),
        "common_formulation_rate": rate(sum(1 for r in form_rows if r["common_formulation_exact"]), len(form_rows)),
        "common_traceable_count": sum(1 for r in trace_rows if r["common_traceable"]), "common_traceable_total": len(trace_rows),
        "common_traceable_rate": rate(sum(1 for r in trace_rows if r["common_traceable"]), len(trace_rows)),
        "common_schema_count": cnt("common_schema_ok", True), "common_schema_rate": rate(cnt("common_schema_ok", True)),
        "common_answer_count": sum(1 for r in ans_rows if r["common_answer_ok"]), "common_answer_total": len(ans_rows),
        "common_mae_mean": mean("common_mae", scored), "common_rmse_mean": mean("common_rmse", scored), "common_overall_mean": mean("common_overall", scored),
        "common_nbias_pct_mean": mean("common_nbias_pct", scored), "common_nmae_pct_mean": mean("common_nmae_pct", scored),
        "common_nrmse_pct_mean": mean("common_nrmse_pct", scored),
        "common_nmae_reference_pct_mean": mean("common_nmae_reference_pct", scored), "common_nmae_persistence_pct_mean": mean("common_nmae_persistence_pct", scored),
        "common_improvement_mean": mean("common_improvement_pct", scored), "common_improvement_persistence_mean": mean("common_improvement_persistence_pct", scored),
        "common_scored_n": len(scored),
        "common_mae_solved_mean": mean("common_mae", solved_rows), "common_rmse_solved_mean": mean("common_rmse", solved_rows),
        "by_horizon": by_h,
        "n_llm_calls_mean": mean("n_llm_calls"), "n_tool_calls_mean": mean("n_tool_calls"),
        "prompt_tokens_mean": mean("prompt_tokens"), "completion_tokens_mean": mean("completion_tokens"),
        "tokens_total": int(sum(float(r.get("prompt_tokens") or 0) + float(r.get("completion_tokens") or 0) for r in rs)),
        "cost_usd_total": round(sum(float(r.get("cost_usd") or 0) for r in rs), 4),
        "wall_time_mean_s": mean("wall_time_s"),
    }

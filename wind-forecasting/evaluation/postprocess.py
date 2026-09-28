"""Render one results folder into files a person can read without Python.

Input, written by ``evaluation/runner.py``::

    D/raw/rows.jsonl              one row per request, scored
    D/raw/traces/<request-id>.json
    D/config.json

Output, all inside ``D``, the same names as every other case study::

    summary.csv                   one line per request, the same columns on every method
    summary.json                  header + aggregate, the line INDEX.md prints
    REPORT.md                     the outcome split, the metrics, the per-horizon errors, failure lists, every request
    traces/NN_<request-id>.json           copy of the raw trace
    traces/NN_<request-id>.transcript.txt the exchange: system, request, every message, tool call, output, verdict
    traces/NN_<request-id>.narrative.txt  what happened, step by step, with the verdicts
    traces/NN_<request-id>.png            the reported series against the target, when the series is valid

``NN`` numbers the requests 01..N in request-id order, so the same request has
the same number in every method's folder of a run. No model is called here.
"""

from __future__ import annotations

import csv
import json
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import methods  # noqa: E402
from evaluation import scoring  # noqa: E402

SUMMARY_COLUMNS = [
    "nn", "request_id", "instance_id", "turbine", "horizon_hours", "question", "condition",
    "formulation_exact", "formulation_error_type", "formulation_detail",
    "outcome", "solved", "solved_reason", "escalated", "wrong_silently", "escalation_reason",
    "status", "schema_ok", "range_ok", "n_values", "mae_kw", "rmse_kw", "overall_kw", "nbias_pct", "nmae_pct", "nrmse_pct", "nmae_reference_pct", "nmae_persistence_pct", "improvement_pct", "improvement_persistence_pct", "n_scored_points",
    "answer_given", "answer_implied", "answer_ok", "answer_truth", "answer_truth_ok",
    "source", "traceable", "gate_pass", "gate_failed",
    "n_llm_calls", "n_tool_calls", "prompt_tokens", "completion_tokens", "cost_usd", "wall_time_s",
    "budget_exhausted", "error",
]


def read_rows(d: Path) -> List[Dict[str, Any]]:
    p = d / "raw" / "rows.jsonl"
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.is_file() else []
    rows.sort(key=lambda r: r["request_id"])
    return rows


def read_config(d: Path) -> Dict[str, Any]:
    p = d / "config.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def summary_row(nn: int, r: Dict[str, Any]) -> Dict[str, Any]:
    oc = r.get("common_outcome")
    g = r.get("gate") or {}
    a = r.get("answer") or {}
    return {
        "nn": nn, "request_id": r["request_id"], "instance_id": r.get("instance_id"), "turbine": r.get("turbine"),
        "horizon_hours": r.get("horizon_hours"), "question": r.get("question"), "condition": r.get("condition"),
        "formulation_exact": r.get("common_formulation_exact"), "formulation_error_type": r.get("common_formulation_error_type"),
        "formulation_detail": r.get("common_formulation_detail"),
        "outcome": oc, "solved": oc == "solved", "solved_reason": r.get("common_reason"), "escalated": oc == "escalated",
        "wrong_silently": oc == "wrong_unflagged", "escalation_reason": r.get("common_escalation_reason"),
        "status": r.get("common_status"), "schema_ok": r.get("common_schema_ok"), "range_ok": r.get("common_range_ok"), "n_values": r.get("common_n_values"),
        "mae_kw": r.get("common_mae"), "rmse_kw": r.get("common_rmse"), "overall_kw": r.get("common_overall"),
        "nbias_pct": r.get("common_nbias_pct"), "nmae_pct": r.get("common_nmae_pct"), "nrmse_pct": r.get("common_nrmse_pct"),
        "nmae_reference_pct": r.get("common_nmae_reference_pct"), "nmae_persistence_pct": r.get("common_nmae_persistence_pct"),
        "improvement_pct": r.get("common_improvement_pct"), "improvement_persistence_pct": r.get("common_improvement_persistence_pct"),
        "n_scored_points": r.get("common_n_scored_points"),
        "answer_given": a.get("answer"), "answer_implied": r.get("common_answer_implied"), "answer_ok": r.get("common_answer_ok"),
        "answer_truth": r.get("common_answer_truth"), "answer_truth_ok": r.get("common_answer_truth_ok"),
        "source": r.get("common_source"), "traceable": r.get("common_traceable"),
        "gate_pass": g.get("passed") if g else "", "gate_failed": ",".join(g.get("failed") or []) if g else "",
        "n_llm_calls": r.get("n_llm_calls"), "n_tool_calls": r.get("n_tool_calls"),
        "prompt_tokens": r.get("prompt_tokens"), "completion_tokens": r.get("completion_tokens"), "cost_usd": r.get("cost_usd"),
        "wall_time_s": r.get("wall_time_s"), "budget_exhausted": r.get("budget_exhausted"), "error": r.get("error") or "",
    }


def _short(v: Any, n: int = 300) -> str:
    s = v if isinstance(v, str) else json.dumps(v, default=str)
    return s if len(s) <= n else s[:n] + f"… ({len(s)} chars)"


def render_transcript(nn: int, r: Dict[str, Any], trace: Dict[str, Any], header: Dict[str, Any]) -> str:
    L = ["=" * 78, f"TRANSCRIPT  {r['method']}  |  {header.get('model')}  |  {r['request_id']}", "=" * 78,
         f"date: {header.get('date')}   instance: {r.get('instance_id')}   horizon: {r.get('horizon_hours')} h   question: {r.get('question')}   condition: {r.get('condition')}", ""]
    msgs = trace.get("messages") or []
    if not msgs:
        L.append("(no model messages: deterministic method)")
    for m in msgs:
        role = m.get("role")
        if role in ("system", "user"):
            L += [f"[{role}]", _short(str(m.get("content") or ""), 6000), ""]
        elif role == "assistant":
            L.append("[assistant]")
            if m.get("content"):
                L.append(_short(str(m["content"]), 6000))
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function", {})
                L.append(f"  -> tool call {fn.get('name')}({fn.get('arguments')})")
            L.append("")
        elif role == "tool":
            L += ["[tool]", _short(m.get("content"), 600), ""]
    L.append("[tool log, every call in order]")
    for e in trace.get("tool_log") or []:
        L.append(f"  {e.get('n'):3d}. {e.get('name')}({json.dumps(e.get('args'), default=str)}) [{e.get('kind')}] -> {_short(e.get('output'), 400)}")
    if r.get("gate"):
        L += ["", "[gate]"]
        for k, c in r["gate"]["conditions"].items():
            L.append(f"  {'PASS' if c['passed'] else 'FAIL'} {k}: {c['detail']}")
    L += ["", "[final answer]", _short(r.get("answer_text") or "(none)", 6000), "",
          f"[verdict] outcome={r.get('common_outcome')}  reason={r.get('common_reason')}"]
    return "\n".join(L) + "\n"


def render_narrative(nn: int, r: Dict[str, Any], trace: Dict[str, Any], header: Dict[str, Any], request_text: str) -> str:
    a = r.get("answer") or {}
    L = [f"RUN {nn:02d}  |  {r['request_id']}  |  {r['method']}  |  {header.get('model')}",
         f"Instance: turbine {r.get('turbine')}, history days {r.get('history_days')}, horizon {r.get('horizon_hours')} h, question {r.get('question')}, condition {r.get('condition')}",
         f"Request: {request_text}", "", "WHAT THE METHOD DID"]
    step = 0
    for e in trace.get("tool_log") or []:
        step += 1
        L.append(f"  {step:2d}. {e.get('name')}({json.dumps(e.get('args'), default=str)})")
        L.append(f"       -> {_short(e.get('output'), 220)}")
    if not trace.get("tool_log"):
        L.append("  (no tool calls)")
    L.append(f"  Totals: {r.get('n_llm_calls')} LLM calls, {r.get('n_tool_calls')} tool calls, {r.get('prompt_tokens')} in / {r.get('completion_tokens')} out tokens, {r.get('wall_time_s')} s"
             + (", budget exhausted" if r.get("budget_exhausted") else ""))
    L += ["", "FORMULATION  (turbine, window and horizon as requested?)",
          f"  declared: turbine {a.get('turbine')}, days {a.get('history_days')}, {a.get('horizon_hours')} h   verdict: {'PASS' if r.get('common_formulation_exact') else 'FAIL'}   {r.get('common_formulation_detail')}",
          "", "THE SERIES",
          f"  status: {a.get('status')}   values: {r.get('common_n_values')}   schema: {r.get('common_schema_ok')}   range: {r.get('common_range_ok')}   source: {a.get('source')}   traceable: {r.get('common_traceable')}",
          f"  error on the target (KDD Cup rules, {r.get('common_n_scored_points')} points): MAE {r.get('common_mae')} kW, RMSE {r.get('common_rmse')} kW, overall {r.get('common_overall')} kW",
          "", "THE ANSWER",
          f"  given: {a.get('answer')}   implied by the series: {r.get('common_answer_implied')}   coherent: {r.get('common_answer_ok')}   against the truth: {r.get('common_answer_truth')} -> {r.get('common_answer_truth_ok')}"]
    if r.get("gate"):
        g = r["gate"]
        L.append(f"  gate: {'passed' if g.get('passed') else 'FAILED ' + ', '.join(g.get('failed') or [])}")
    if r.get("harness_declared"):
        L.append(f"  harness wrote the answer: {r['harness_declared']}")
    L += ["", f"OUTCOME: {str(r.get('common_outcome')).upper()}   ({r.get('common_reason')})", "", "SUMMARY WRITTEN BY THE METHOD", f"  {a.get('summary') or '(none)'}"]
    if r.get("error"):
        L += ["", f"ERROR: {r['error']}"]
    return "\n".join(L) + "\n"


def render_plot(r: Dict[str, Any], trace: Dict[str, Any], out: Path) -> bool:
    """The reported series against the target and the last history day; skipped when the series is not valid."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from evaluation.requests import request_from_dict, window_for
    except Exception:
        return False
    if not r.get("common_schema_ok"):
        return False
    try:
        from methods.answer import parse_answer

        series = parse_answer(r.get("answer_text") or "").forecast
        req = request_from_dict(trace["request"])
        w = window_for(req, check_hash=False)
        t = w.target(req.horizon_hours)
        h = w.history(days=1)
        fig, ax = plt.subplots(figsize=(9, 3))
        n_h = len(h)
        ax.plot(range(-n_h, 0), h["Patv"].clip(lower=0), color="#64748b", lw=1, label="last history day")
        ax.plot(range(len(t)), t["Patv"].clip(lower=0), color="#e0891a", lw=1.2, label="actual")
        ax.plot(range(len(series)), series, color="#2f5fd0", lw=1.2, ls="--", label=f"{r['method']} ({r.get('common_source') or 'LLM'})")
        ab = t["abnormal"].to_numpy()
        if ab.any():
            ax.scatter([i for i in range(len(t)) if ab[i]], [0] * int(ab.sum()), s=4, color="#d53f3f", label="not scored (abnormal)")
        ax.axvline(0, color="#0f172a", lw=0.8)
        ax.set_ylabel("kW"); ax.set_xlabel("10-minute steps from the forecast start")
        ax.set_title(f"{r['request_id']}: MAE {r.get('common_mae')} kW, RMSE {r.get('common_rmse')} kW", fontsize=9)
        ax.legend(fontsize=7, loc="upper right")
        fig.tight_layout(); fig.savefig(out, dpi=110); plt.close(fig)
        return True
    except Exception:
        return False


def _pct(k: int, n: int) -> str:
    return f"{100.0 * k / n:.1f}%" if n else "-"


def render_report(header: Dict[str, Any], rows: List[Dict[str, Any]], agg: Dict[str, Any], names: Dict[str, str]) -> str:
    n = agg.get("common_n", 0)
    card = methods.card(header["method"])
    L = [f"# {header['method']} on SDWPF with {header.get('model_short')}", "",
         f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} by evaluation/postprocess.py from `raw/rows.jsonl`. Requests: {len(rows)}. "
         "Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the frozen target days, the same way for every method.", "",
         "## Run", "", "| field | value |", "|---|---|"]
    for k in ("date", "model", "method", "condition", "n", "instances", "horizons", "seed", "requests_digest", "temperature", "max_llm_calls", "max_tool_calls", "timeout_s", "system_prompt_hash", "git_commit", "gru_weights_hash"):
        L.append(f"| {k} | {header.get(k)} |")
    L += [f"| description | {card['description']} |", f"| prompt files | {', '.join(card.get('prompt_files') or []) or '(none)'} |", ""]
    L += ["## Where every request ended", "",
          "The three outcomes are exclusive and sum to the request count. Escalation takes precedence: a request the method handed to a person is not an autonomous answer, right or wrong.", "",
          "| outcome | count | share |", "|---|---:|---:|",
          f"| Solved autonomously | {agg.get('common_solved_count', 0)} | {_pct(agg.get('common_solved_count', 0), n)} |",
          f"| Escalated to a person | {agg.get('common_escalated_count', 0)} | {_pct(agg.get('common_escalated_count', 0), n)} |",
          f"| Wrong, unflagged | {agg.get('common_wrong_count', 0)} | {_pct(agg.get('common_wrong_count', 0), n)} |",
          f"| **Total** | **{n}** | 100% |"]
    if agg.get("common_run_error_count"):
        L.append(f"| run errors (outside the rates) | {agg['common_run_error_count']} | |")
    L += ["", "## Metrics", "", "| group | metric | value |", "|---|---|---|",
          f"| Task utility | Formulation exact | {agg.get('common_formulation_count')}/{agg.get('common_formulation_total')} ({agg.get('common_formulation_rate')}%) |",
          f"| Task utility | Formulation error types | {dict(Counter(r.get('common_formulation_error_type') for r in rows if not r.get('common_formulation_exact')))} |",
          f"| Task utility | MAE / RMSE / overall, kW, over valid series (n={agg.get('common_scored_n')}) | {agg.get('common_mae_mean')} / {agg.get('common_rmse_mean')} / {agg.get('common_overall_mean')} |",
          f"| Task utility | NBIAS / NMAE / NRMSE, % of installed capacity (ANEMOS protocol) | {agg.get('common_nbias_pct_mean')} / {agg.get('common_nmae_pct_mean')} / {agg.get('common_nrmse_pct_mean')} |",
          f"| Task utility | Improvement over the protocol's reference model, % (its NMAE {agg.get('common_nmae_reference_pct_mean')} %) | {agg.get('common_improvement_mean')} |",
          f"| Task utility | Improvement over persistence, % (its NMAE {agg.get('common_nmae_persistence_pct_mean')} %) | {agg.get('common_improvement_persistence_mean')} |",
          f"| Task utility | MAE / RMSE, kW, over solved requests | {agg.get('common_mae_solved_mean')} / {agg.get('common_rmse_solved_mean')} |",
          f"| Task utility | Answer coherent with the series | {agg.get('common_answer_count')}/{agg.get('common_answer_total')} |",
          f"| Solver-grounded correctness | Valid series (schema and range) | {agg.get('common_schema_count')}/{n} ({agg.get('common_schema_rate')}%) |",
          f"| Solver-grounded correctness | Traceable series | {agg.get('common_traceable_count')}/{agg.get('common_traceable_total')} ({agg.get('common_traceable_rate')}%) |",
          f"| Solver-grounded correctness | Wrong, unflagged | {agg.get('common_wrong_count')}/{n} ({agg.get('common_wrong_rate')}%) |",
          f"| Cost and time | Escalated | {agg.get('common_escalated_count')}/{n} ({agg.get('common_escalated_rate')}%) |",
          f"| Cost and time | LLM calls / tool calls, mean | {agg.get('n_llm_calls_mean')} / {agg.get('n_tool_calls_mean')} |",
          f"| Cost and time | Prompt / completion tokens, mean | {agg.get('prompt_tokens_mean')} / {agg.get('completion_tokens_mean')} |",
          f"| Cost and time | Cost, total | ${agg.get('cost_usd_total', 0):.4f} |",
          f"| Cost and time | Wall time, mean | {agg.get('wall_time_mean_s')} s |", ""]
    L += ["## By horizon", "",
          "Every error is the mean over the requests of that horizon whose series was valid; a method that returns no valid series at a "
          "horizon has nothing to average, which is itself the finding. NMAE and NRMSE are normalised by the 1500 kW installed capacity, and "
          "Imp. is the improvement score of the ANEMOS protocol (Madsen et al. 2005) over its reference model, `a_k P(t) + (1-a_k) Pbar`, "
          "fitted on the training period; the improvement over plain persistence is beside it because persistence is the reference most "
          "readers know, and the protocol warns it flatters a model at long horizons.", "",
          "| horizon | n | solved | scored | MAE kW | RMSE kW | NMAE % | NRMSE % | reference NMAE % | Imp. % | persistence NMAE % | Imp. vs pers. % |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for h, v in (agg.get("by_horizon") or {}).items():
        L.append(f"| {h} h | {v['n']} | {v['solved']} | {v['n_scored']} | {v['mae']} | {v['rmse']} | {v.get('nmae_pct')} | {v.get('nrmse_pct')} | "
                 f"{v.get('nmae_reference_pct')} | {v.get('improvement_pct')} | {v.get('nmae_persistence_pct')} | {v.get('improvement_persistence_pct')} |")
    L.append("")
    for oc, title in (("wrong_unflagged", "Wrong and unflagged"), ("escalated", "Escalated")):
        sel = [r for r in rows if r.get("common_outcome") == oc]
        L += [f"## {title} ({len(sel)})", ""]
        if not sel:
            L.append("none")
        for r in sel:
            L.append(f"- `{names.get(r['request_id'], r['request_id'])}`: {r.get('common_reason')}")
        L.append("")
    L += ["## Every request", "", "| nn | instance | h | question | outcome | formulation | values | MAE | answer ok | source | LLM/tool calls | tokens | why |", "|---|---|---:|---|---|---|---:|---:|---|---|---|---:|---|"]
    for i, r in enumerate(rows, 1):
        L.append(f"| {i:02d} | {r.get('instance_id')} | {r.get('horizon_hours')} | {r.get('question')} | {r.get('common_outcome')} | "
                 f"{'ok' if r.get('common_formulation_exact') else r.get('common_formulation_error_type')} | {r.get('common_n_values')} | {r.get('common_mae')} | "
                 f"{r.get('common_answer_ok')} | {r.get('common_source')} | {r.get('n_llm_calls')}/{r.get('n_tool_calls')} | "
                 f"{(r.get('prompt_tokens') or 0) + (r.get('completion_tokens') or 0)} | {r.get('common_reason')} |")
    L += ["", "Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace), `.png` (the series against the target)."]
    return "\n".join(L) + "\n"


def postprocess(d: Path, *, quiet: bool = False) -> Dict[str, Any]:
    d = Path(d)
    rows = read_rows(d)
    cfg = read_config(d)
    if not rows:
        raise FileNotFoundError(f"no raw/rows.jsonl under {d}")
    method = cfg.get("method") or rows[0]["method"]
    header = {"method": method, "runner_name": methods.card(method)["runner_name"],
              "model": cfg.get("model") or rows[0].get("model"), "model_short": cfg.get("model_short") or d.parent.name,
              "instance": d.parts[-4], "case": cfg.get("case") or "sdwpf", "date": cfg.get("date") or d.parts[-3],
              "condition": cfg.get("condition", "normal"), "n": len(rows), "instances": cfg.get("instances"), "horizons": cfg.get("horizons"),
              "seed": cfg.get("seed"), "requests_digest": cfg.get("requests_digest"), "temperature": cfg.get("temperature"),
              "max_llm_calls": cfg.get("max_llm_calls"), "max_tool_calls": cfg.get("max_tool_calls"), "timeout_s": cfg.get("timeout_s"),
              "system_prompt_hash": cfg.get("system_prompt_hash"), "git_commit": cfg.get("git_commit"), "gru_weights_hash": cfg.get("gru_weights_hash"),
              "tag": cfg.get("tag")}
    (d / "traces").mkdir(exist_ok=True)
    for old in (d / "traces").glob("*"):
        old.unlink()
    names: Dict[str, str] = {}
    summary_rows = []
    for nn, r in enumerate(rows, 1):
        raw = d / "raw" / "traces" / f"{r['request_id']}.json"
        trace = json.loads(raw.read_text(encoding="utf-8")) if raw.is_file() else {}
        stem = f"{nn:02d}_{r['request_id']}"
        names[r["request_id"]] = stem
        if raw.is_file():
            shutil.copyfile(raw, d / "traces" / f"{stem}.json")
        req = trace.get("request") or {}
        (d / "traces" / f"{stem}.transcript.txt").write_text(render_transcript(nn, r, trace, header), encoding="utf-8")
        (d / "traces" / f"{stem}.narrative.txt").write_text(render_narrative(nn, r, trace, header, req.get("text", "")), encoding="utf-8")
        if req:
            render_plot(r, trace, d / "traces" / f"{stem}.png")
        summary_rows.append(summary_row(nn, r))
    with (d / "summary.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SUMMARY_COLUMNS)
        w.writeheader()
        for s in summary_rows:
            w.writerow({k: ("" if s.get(k) is None else (json.dumps(s[k]) if isinstance(s[k], (list, dict)) else s[k])) for k in SUMMARY_COLUMNS})
    agg = scoring.aggregate(rows)
    (d / "summary.json").write_text(json.dumps({"header": header, "aggregate": {
        "n": agg.get("common_n"), "solved": agg.get("common_solved_count"), "escalated": agg.get("common_escalated_count"),
        "wrong": agg.get("common_wrong_count"), "run_error": agg.get("common_run_error_count"), "form": agg.get("common_formulation_rate"),
        "trace": agg.get("common_traceable_rate"), "mae": agg.get("common_mae_mean"), "rmse": agg.get("common_rmse_mean"),
        "tokens": agg.get("tokens_total"), "cost": agg.get("cost_usd_total"), **agg}}, indent=1), encoding="utf-8")
    (d / "REPORT.md").write_text(render_report(header, rows, agg, names), encoding="utf-8")
    if not quiet:
        print(f"  rendered {d.relative_to(PROJECT_ROOT) if str(d).startswith(str(PROJECT_ROOT)) else d}: {len(rows)} requests, "
              f"solved {agg.get('common_solved_count')} / escalated {agg.get('common_escalated_count')} / wrong {agg.get('common_wrong_count')}, "
              f"MAE {agg.get('common_mae_mean')} kW")
    return {"header": header, "aggregate": agg}


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="+")
    args = ap.parse_args(argv)
    for d in args.dirs:
        postprocess(Path(d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

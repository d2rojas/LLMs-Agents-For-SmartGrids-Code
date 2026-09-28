"""Render one results folder into files a person can read without Python.

Input, written by ``evaluation/runner.py``::

    D/raw/rows.jsonl              one row per scenario, scored
    D/raw/traces/<request-id>.json
    D/config.json

Output, all inside ``D``, the same names as every other case study::

    summary.csv                   one line per scenario, the same columns on every method
    summary.json                  header + aggregate, the line INDEX.md prints
    requests.jsonl                the request set: id, text, injected fault, initial state
    REPORT.md                     the outcome split, the metrics, failure lists, every scenario on one line
    traces/NN_<request-id>.json           copy of the raw trace
    traces/NN_<request-id>.transcript.txt the exchange: system, request, every message, tool call, output, verdict
    traces/NN_<request-id>.narrative.txt  what happened, step by step, with the verdicts

``NN`` numbers the scenarios 01..N in request-id order, so the same scenario has
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
from config import NETWORK_LABELS  # noqa: E402
from evaluation import scoring  # noqa: E402

SUMMARY_COLUMNS = [
    "nn", "request_id", "scenario_id", "category", "injected_fault_type", "initial_state", "initial_n_new",
    "formulation_exact", "formulation_error_type", "formulation_detail",
    "outcome", "solved", "solved_reason", "escalated", "wrong_silently", "escalation_reason",
    "status", "claims_repaired", "final_converged", "final_secure", "final_n_new", "final_islanded",
    "repaired", "improved", "feasible",
    "gate_pass", "gate_failed", "traceable", "n_numbers", "n_untraceable_numbers",
    "n_actions", "n_llm_calls", "n_tool_calls", "prompt_tokens", "completion_tokens", "cost_usd", "wall_time_s",
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
    return {
        "nn": nn, "request_id": r["request_id"], "scenario_id": r["scenario_id"], "category": r["category"],
        "injected_fault_type": r.get("injected_fault_type"), "initial_state": r.get("initial_state"), "initial_n_new": r.get("initial_n_new"),
        "formulation_exact": r.get("common_formulation_exact"), "formulation_error_type": r.get("common_formulation_error_type"),
        "formulation_detail": r.get("common_formulation_detail"),
        "outcome": oc, "solved": oc == "solved", "solved_reason": r.get("common_reason"), "escalated": oc == "escalated",
        "wrong_silently": oc == "wrong_unflagged", "escalation_reason": r.get("common_escalation_reason"),
        "status": r.get("common_status"), "claims_repaired": r.get("common_claims_repaired"),
        "final_converged": r.get("common_converged"), "final_secure": r.get("common_secure"), "final_n_new": r.get("common_n_new_violations"),
        "final_islanded": r.get("common_islanded"),
        "repaired": r.get("common_repaired"), "improved": r.get("common_improved"), "feasible": r.get("common_feasible"),
        "gate_pass": g.get("passed") if g else "", "gate_failed": ",".join(g.get("failed") or []) if g else "",
        "traceable": r.get("common_traceable"), "n_numbers": r.get("common_n_numbers"), "n_untraceable_numbers": r.get("common_n_untraceable"),
        "n_actions": r.get("n_actions"), "n_llm_calls": r.get("n_llm_calls"), "n_tool_calls": r.get("n_tool_calls"),
        "prompt_tokens": r.get("prompt_tokens"), "completion_tokens": r.get("completion_tokens"), "cost_usd": r.get("cost_usd"),
        "wall_time_s": r.get("wall_time_s"), "budget_exhausted": r.get("budget_exhausted"), "error": r.get("error") or "",
    }


def _short(v: Any, n: int = 300) -> str:
    s = v if isinstance(v, str) else json.dumps(v, default=str)
    return s if len(s) <= n else s[:n] + f"… ({len(s)} chars)"


def render_transcript(nn: int, r: Dict[str, Any], trace: Dict[str, Any], header: Dict[str, Any]) -> str:
    L = ["=" * 78, f"TRANSCRIPT  {r['method']}  |  {header.get('model')}  |  {r['network']}  |  {r['request_id']}", "=" * 78,
         f"date: {header.get('date')}   scenario: {r['scenario_id']}   category: {r['category']}   injected: {r.get('injected_fault_type')}", ""]
    msgs = trace.get("messages") or []
    if not msgs:
        L.append("(no model messages: deterministic method)")
    for m in msgs:
        role = m.get("role")
        if role in ("system", "user"):
            L += [f"[{role}]", str(m.get("content") or ""), ""]
        elif role == "assistant":
            L.append("[assistant]")
            if m.get("content"):
                L.append(str(m["content"]))
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
    L += ["", "[final answer]", r.get("answer_text") or "(none)", "",
          f"[verdict] outcome={r.get('common_outcome')}  reason={r.get('common_reason')}"]
    return "\n".join(L) + "\n"


def render_narrative(nn: int, r: Dict[str, Any], trace: Dict[str, Any], header: Dict[str, Any], request_text: str) -> str:
    a = r.get("answer") or {}
    L = [f"RUN {nn:02d}  |  {r['request_id']}  |  {r['method']}  |  {header.get('model')}  |  {NETWORK_LABELS.get(r['network'], r['network'])}",
         f"Scenario: {r.get('label')} ({r['category']}); injected fault: {r.get('injected_fault_type')} {json.dumps(r.get('injected_components'))}",
         f"Initial state: {r.get('initial_state')}, {r.get('initial_n_new')} new violation(s)", f"Request: {request_text}", "", "WHAT THE METHOD DID"]
    step = 0
    for e in trace.get("tool_log") or []:
        step += 1
        flag = " (applied by the harness from the answer)" if e.get("harness") else ""
        L.append(f"  {step:2d}. {e.get('name')}({json.dumps(e.get('args'), default=str)}){flag}")
        L.append(f"       -> {_short(e.get('output'), 220)}")
    if not trace.get("tool_log"):
        L.append("  (no tool calls)")
    L.append(f"  Totals: {r.get('n_llm_calls')} LLM calls, {r.get('n_tool_calls')} tool calls, {r.get('prompt_tokens')} in / {r.get('completion_tokens')} out tokens, {r.get('wall_time_s')} s"
             + (", budget exhausted" if r.get("budget_exhausted") else ""))
    L += ["", "DIAGNOSIS  (is the injected fault named?)",
          f"  answer: {a.get('fault_type')} {json.dumps(a.get('components'))}   verdict: {'PASS' if r.get('common_formulation_exact') else 'FAIL'}   {r.get('common_formulation_detail')}",
          "", "STATE  (the harness's own power flow on the final network)",
          f"  converged: {r.get('common_converged')}   secure: {r.get('common_secure')}   new violations: {r.get('common_n_new_violations')}   islanded load: {r.get('common_islanded')}",
          f"  repaired: {r.get('common_repaired')}   improved: {r.get('common_improved')}   feasible: {r.get('common_feasible')}",
          "", "REPORTING",
          f"  status claimed: {a.get('status')}   final_state claimed: converged={a.get('claimed_converged')}, new violations={a.get('claimed_new_violations')}",
          f"  numbers in the answer: {r.get('common_n_numbers')}, untraceable: {r.get('common_n_untraceable')} -> traceable: {'pass' if r.get('common_traceable') else 'FAIL'}"]
    if r.get("gate"):
        g = r["gate"]
        L.append(f"  gate: {'passed' if g.get('passed') else 'FAILED ' + ', '.join(g.get('failed') or [])}")
    if r.get("harness_declared"):
        L.append(f"  harness wrote the answer: {r['harness_declared']}")
    L += ["", f"OUTCOME: {str(r.get('common_outcome')).upper()}   ({r.get('common_reason')})", "", "SUMMARY WRITTEN BY THE METHOD", f"  {a.get('summary') or '(none)'}"]
    if r.get("error"):
        L += ["", f"ERROR: {r['error']}"]
    return "\n".join(L) + "\n"


def _pct(k: int, n: int) -> str:
    return f"{100.0 * k / n:.1f}%" if n else "-"


def render_report(header: Dict[str, Any], rows: List[Dict[str, Any]], agg: Dict[str, Any], names: Dict[str, str]) -> str:
    n = agg.get("common_n", 0)
    card = methods.card(header["method"])
    L = [f"# {header['method']} on {NETWORK_LABELS.get(header['case'], header['case'])} with {header.get('model_short')}", "",
         f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} by evaluation/postprocess.py from `raw/rows.jsonl`. Scenarios: {len(rows)}. "
         "Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the harness's own power flow, the same way for every method.", "",
         "## Run", "", "| field | value |", "|---|---|"]
    for k in ("date", "model", "method", "case", "condition", "n", "temperature", "max_llm_calls", "max_tool_calls", "timeout_s", "system_prompt_hash", "git_commit", "pandapower"):
        L.append(f"| {k} | {header.get(k)} |")
    L += [f"| description | {card['description']} |", f"| prompt files | {', '.join(card.get('prompt_files') or []) or '(none)'} |", ""]
    L += ["## Where every scenario ended", "",
          "The three outcomes are exclusive and sum to the scenario count. Escalation takes precedence: a scenario the method handed to a person is not an autonomous answer, right or wrong.", "",
          "| outcome | count | share |", "|---|---:|---:|",
          f"| Solved autonomously | {agg.get('common_solved_count', 0)} | {_pct(agg.get('common_solved_count', 0), n)} |",
          f"| Escalated to a person | {agg.get('common_escalated_count', 0)} | {_pct(agg.get('common_escalated_count', 0), n)} |",
          f"| Wrong, unflagged | {agg.get('common_wrong_count', 0)} | {_pct(agg.get('common_wrong_count', 0), n)} |",
          f"| **Total** | **{n}** | 100% |"]
    if agg.get("common_run_error_count"):
        L.append(f"| run errors (outside the rates) | {agg['common_run_error_count']} | |")
    L += ["", "## Metrics", "", "| group | metric | value |", "|---|---|---|",
          f"| Task utility | Diagnosis exact | {agg.get('common_formulation_count')}/{agg.get('common_formulation_total')} ({agg.get('common_formulation_rate')}%) |",
          f"| Task utility | Diagnosis error types | {dict(Counter(r.get('common_formulation_error_type') for r in rows if not r.get('common_formulation_exact')))} |",
          f"| Task utility | Repaired (secure final network) | {agg.get('common_repaired_count')}/{n} ({agg.get('common_repaired_rate')}%) |",
          f"| Task utility | Improved | {agg.get('common_improved_count')}/{n} ({agg.get('common_improved_rate')}%) |",
          f"| Task utility | New violations, before -> after (scenarios converged at both ends, n={agg.get('violations_comparable_n')}) | {agg.get('violations_initial_new')} -> {agg.get('violations_final_new')} |",
          f"| Solver-grounded correctness | Feasible (final power flow converges) | {agg.get('common_feasible_count')}/{n} ({agg.get('common_feasible_rate')}%) |",
          f"| Solver-grounded correctness | Traceable answers | {agg.get('common_traceable_count')}/{n} ({agg.get('common_traceable_rate')}%) |",
          f"| Solver-grounded correctness | Wrong, unflagged | {agg.get('common_wrong_count')}/{n} ({agg.get('common_wrong_rate')}%) |",
          f"| Cost and operation | Escalated | {agg.get('common_escalated_count')}/{n} ({agg.get('common_escalated_rate')}%) |",
          f"| Cost and operation | LLM calls / tool calls, mean | {agg.get('n_llm_calls_mean')} / {agg.get('n_tool_calls_mean')} |",
          f"| Cost and operation | Prompt / completion tokens, mean | {agg.get('prompt_tokens_mean')} / {agg.get('completion_tokens_mean')} |",
          f"| Cost and operation | Cost, total | ${agg.get('cost_usd_total', 0):.4f} |",
          f"| Cost and operation | Wall time, mean | {agg.get('wall_time_mean_s')} s |", ""]
    # by category and by initial state
    for key, title in (("category", "By scenario category (the generator's intent)"), ("initial_state", "By measured initial state")):
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            groups.setdefault(str(r.get(key)), []).append(r)
        L += [f"## {title}", "", f"| {key} | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |", "|---|---:|---:|---:|---:|---:|---:|"]
        for g, rs in sorted(groups.items()):
            L.append(f"| {g} | {len(rs)} | {sum(1 for r in rs if r.get('common_outcome') == 'solved')} | {sum(1 for r in rs if r.get('common_outcome') == 'escalated')} | "
                     f"{sum(1 for r in rs if r.get('common_outcome') == 'wrong_unflagged')} | {sum(1 for r in rs if r.get('common_repaired'))} | {sum(1 for r in rs if r.get('common_formulation_exact'))} |")
        L.append("")
    for oc, title in (("wrong_unflagged", "Wrong and unflagged"), ("escalated", "Escalated")):
        sel = [r for r in rows if r.get("common_outcome") == oc]
        L += [f"## {title} ({len(sel)})", ""]
        if not sel:
            L.append("none")
        for r in sel:
            L.append(f"- `{names.get(r['request_id'], r['request_id'])}` {r['scenario_id']}: {r.get('common_reason')}")
        L.append("")
    L += ["## Every scenario", "", "| nn | scenario | initial | outcome | diagnosis | final | actions | LLM/tool calls | tokens | why |", "|---|---|---|---|---|---|---:|---|---|---|"]
    for i, r in enumerate(rows, 1):
        final = "not converged" if not r.get("common_converged") else ("secure" if r.get("common_secure") else f"{r.get('common_n_new_violations')} new" + (f", islanded {r.get('common_islanded')}" if r.get("common_islanded") else ""))
        L.append(f"| {i:02d} | {r['scenario_id']} | {r.get('initial_state')} ({r.get('initial_n_new')}) | {r.get('common_outcome')} | "
                 f"{'ok' if r.get('common_formulation_exact') else r.get('common_formulation_error_type')} | {final} | {r.get('n_actions')} | "
                 f"{r.get('n_llm_calls')}/{r.get('n_tool_calls')} | {(r.get('prompt_tokens') or 0) + (r.get('completion_tokens') or 0)} | {r.get('common_reason')} |")
    L += ["", "Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace)."]
    return "\n".join(L) + "\n"


def postprocess(d: Path, *, quiet: bool = False) -> Dict[str, Any]:
    d = Path(d)
    rows = read_rows(d)
    cfg = read_config(d)
    if not rows:
        raise FileNotFoundError(f"no raw/rows.jsonl under {d}")
    header = {"method": cfg.get("method") or rows[0]["method"], "runner_name": methods.card(cfg.get("method") or rows[0]["method"])["runner_name"],
              "model": cfg.get("model") or rows[0].get("model"), "model_short": cfg.get("model_short") or d.parent.name,
              "instance": d.parts[-4], "case": cfg.get("case") or rows[0]["network"], "date": cfg.get("date") or d.parts[-3],
              "condition": cfg.get("condition", "normal"), "n": len(rows), "temperature": cfg.get("temperature"),
              "max_llm_calls": cfg.get("max_llm_calls"), "max_tool_calls": cfg.get("max_tool_calls"), "timeout_s": cfg.get("timeout_s"),
              "system_prompt_hash": cfg.get("system_prompt_hash"), "git_commit": cfg.get("git_commit"), "pandapower": cfg.get("pandapower"),
              "tag": cfg.get("tag")}
    (d / "traces").mkdir(exist_ok=True)
    for old in (d / "traces").glob("*"):
        old.unlink()
    names: Dict[str, str] = {}
    summary_rows = []
    requests_out = []
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
        summary_rows.append(summary_row(nn, r))
        if req:
            requests_out.append(req)
    with (d / "summary.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SUMMARY_COLUMNS)
        w.writeheader()
        for s in summary_rows:
            w.writerow({k: ("" if s.get(k) is None else (json.dumps(s[k]) if isinstance(s[k], (list, dict)) else s[k])) for k in SUMMARY_COLUMNS})
    (d / "requests.jsonl").write_text("".join(json.dumps(r, default=str) + "\n" for r in requests_out), encoding="utf-8")
    agg = scoring.aggregate(rows)
    (d / "summary.json").write_text(json.dumps({"header": header, "aggregate": {
        "n": agg.get("common_n"), "solved": agg.get("common_solved_count"), "escalated": agg.get("common_escalated_count"),
        "wrong": agg.get("common_wrong_count"), "run_error": agg.get("common_run_error_count"), "form": agg.get("common_formulation_rate"),
        "trace": agg.get("common_traceable_rate"), "repaired": agg.get("common_repaired_count"), "improved": agg.get("common_improved_count"),
        "feasible": agg.get("common_feasible_count"), "tokens": agg.get("tokens_total"), "cost": agg.get("cost_usd_total"), **agg}}, indent=1),
        encoding="utf-8")
    (d / "REPORT.md").write_text(render_report(header, rows, agg, names), encoding="utf-8")
    if not quiet:
        print(f"  rendered {d.relative_to(PROJECT_ROOT) if str(d).startswith(str(PROJECT_ROOT)) else d}: {len(rows)} scenarios, "
              f"solved {agg.get('common_solved_count')} / escalated {agg.get('common_escalated_count')} / wrong {agg.get('common_wrong_count')}")
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

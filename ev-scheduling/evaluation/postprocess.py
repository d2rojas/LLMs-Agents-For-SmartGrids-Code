"""Lay a run set out the way every case study lays its results out.

The runner writes one directory per run set, ``results/ev_matrix_<model>/``,
with every method's rows in one ``rows.csv``. That is convenient to write and
impossible to browse next to the other case studies, whose results are one
folder per method:

    results/<instance>/<YYYY-MM-DD>/<model>/<method>/
      REPORT.md          the method's counts, failure lists and cost, from the rows
      summary.csv        one line per request, the same columns on every method
      summary.json       header + aggregate, the line INDEX.md prints
      config.json        what was run, from the run manifest, and where it came from
      requests.jsonl     the request set, digest included
      traces/
        NN_<request-id>.json            the raw trace the runner wrote
        NN_<request-id>.transcript.txt  the exchange: system, request, every message, tool call, output, verdict
        NN_<request-id>.narrative.txt   what happened, step by step, with the verdicts
      raw/               the run set this folder was built from (rows.csv, scoreboard, manifest)

``NN`` numbers the requests 01..N in request-id order, so the same request has
the same number in every method's folder of a run set.

``postprocess(run_set_dir)`` builds those folders from an existing run set and
is idempotent. ``run.py run`` calls it after the runner; ``run.py postprocess``
re-renders after a scoring change. Nothing here calls a model.

The instance is the site (``caltech``): the case studies differ in what an
instance is, a bus system there and a charging site here, and the layout does
not care.
"""

from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS = PROJECT_ROOT / "results"

# Runner arm name -> the folder name every case study uses for that method.
# optimum and charge_asap are kept only so a run set that still contains them
# lays out; they are not rows of the table and are not run by default.
FOLDER_FOR_ARM: Dict[str, str] = {
    "rule_based": "rule_based",
    "llm_only:structured": "llm_only_structured",
    "llm_only:chain_of_thought": "llm_only_cot",
    "plan_act": "plan_act_nogate",
    "react": "react_nogate",
    "evagent": "evagent",
    "optimum": "optimum",
    "charge_asap": "charge_asap",
}

# The columns of summary.csv, the same on every method. Names follow the
# power-flow case where the concept is the same, so a reader who knows one
# summary.csv knows the other.
SUMMARY_COLUMNS = [
    "nn", "request_id", "variant", "answer_kind", "request_text",
    "formulation_exact", "formulation_error_type", "n_sessions_exact", "n_sessions_truth",
    "outcome", "solved", "solved_reason", "escalated", "wrong_silently",
    "gate_pass", "gate_declared_failure", "gate_reason",
    "traceable", "n_numbers", "n_untraceable_numbers",
    "answer_ok", "answer_truth", "answer_given",
    "no_hard_violation", "max_violation_kw", "gap_pct", "gap_comparable",
    "cost_usd", "cost_star_usd", "unmet_kwh", "peak_kw", "pct_fully_served",
    "n_llm_calls", "n_tool_calls", "prompt_tokens", "completion_tokens", "est_cost_usd", "wall_time_s",
    "error",
]


# --------------------------------------------------------------------- reading


def read_rows(run_set: Path) -> List[Dict[str, str]]:
    with (run_set / "rows.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def read_manifest(run_set: Path) -> Dict[str, Any]:
    return json.loads((run_set / "run_manifest.json").read_text(encoding="utf-8"))


def model_short(resolved: str, arm: str) -> str:
    """``openai/gpt-4o-mini`` -> ``gpt-4o-mini``; the reference rows are ``no-llm``."""
    if arm in ("optimum", "charge_asap", "rule_based"):
        return "no-llm"
    return (resolved or "unknown").split("/")[-1].split(":")[-1]


def run_date(manifest: Dict[str, Any]) -> str:
    created = str(manifest.get("created_at") or manifest.get("started_at") or "")
    try:
        return datetime.fromisoformat(created.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return datetime.now().date().isoformat()


def _b(v: Any) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


def _f(v: Any) -> Optional[float]:
    try:
        return float(v) if str(v).strip() != "" else None
    except ValueError:
        return None


# ------------------------------------------------------------------- rendering


def _outcome_label(r: Dict[str, str]) -> str:
    """The row's outcome in the vocabulary every case study shares.

    A row the arm never completed carries no outcome, because it was never
    scored: the three rates are taken over the rows that finished, and
    ``aggregate`` reports the rest separately as ``run_error``. Writing that as
    an empty cell in ``summary.csv`` left the run's own rates right and the file
    silent about why one row was missing from them, and anything recounting the
    file had to guess. ``visuals/crosscheck.mjs`` guessed wrong, reading the
    blank as the last branch of its three-way rule and counting a failed row as
    wrong and unflagged, which is the worst of the four things it could have
    been mistaken for.

    So the label is written, and it is the one ``power-flow-agent`` writes for
    the same case (``postprocess._outcome``), which is what keeps a recount of
    any case study's rows comparable with any other's.
    """
    outcome = str(r.get("outcome") or "")
    if outcome:
        return outcome
    if r.get("error") or (r.get("status") and r.get("status") != "ok"):
        return "run_error"
    return ""


def summary_row(nn: int, r: Dict[str, str]) -> Dict[str, Any]:
    outcome = _outcome_label(r)
    return {
        "nn": nn,
        "request_id": r.get("request_id"),
        "variant": r.get("variant"),
        "answer_kind": r.get("answer_kind"),
        "request_text": "",  # filled from requests.jsonl by the caller
        "formulation_exact": _b(r.get("formulation_status") == "pass"),
        "formulation_error_type": r.get("formulation_error_type", ""),
        "n_sessions_exact": r.get("n_sessions_exact", ""),
        "n_sessions_truth": r.get("n_sessions_truth", ""),
        "outcome": outcome,
        "solved": outcome == "solved",
        "solved_reason": r.get("outcome_reason", ""),
        "escalated": outcome == "escalated",
        "wrong_silently": outcome == "wrong_unflagged",
        "gate_pass": r.get("gate_passed", ""),
        "gate_declared_failure": r.get("gate_declared_failure", ""),
        "gate_reason": r.get("gate_reason", ""),
        "traceable": r.get("traceability_status", ""),
        "n_numbers": r.get("n_numbers", ""),
        "n_untraceable_numbers": r.get("n_untraceable", ""),
        "answer_ok": r.get("answer_status", ""),
        "answer_truth": r.get("answer_truth", ""),
        "answer_given": r.get("answer_given", ""),
        "no_hard_violation": r.get("no_hard_violation", ""),
        "max_violation_kw": r.get("max_violation_kw", ""),
        "gap_pct": r.get("gap_pct", ""),
        "gap_comparable": r.get("gap_comparable", ""),
        "cost_usd": r.get("cost_usd", ""),
        "cost_star_usd": r.get("cost_star_usd", ""),
        "unmet_kwh": r.get("unmet_kwh", ""),
        "peak_kw": r.get("peak_kw", ""),
        "pct_fully_served": r.get("pct_fully_served", ""),
        "n_llm_calls": r.get("n_llm_calls", ""),
        "n_tool_calls": r.get("n_tool_calls", ""),
        "prompt_tokens": r.get("prompt_tokens", ""),
        "completion_tokens": r.get("completion_tokens", ""),
        "est_cost_usd": r.get("est_cost_usd", ""),
        "wall_time_s": r.get("wall_s", ""),
        "error": r.get("error", ""),
    }


def aggregate(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows)
    ok = [r for r in rows if r["outcome"] in ("solved", "escalated", "wrong_unflagged")]
    solved = sum(1 for r in rows if r["solved"])
    esc = sum(1 for r in rows if r["escalated"])
    wrong = sum(1 for r in rows if r["wrong_silently"])
    form_rows = [r for r in rows if r["formulation_exact"] or r["formulation_error_type"]]
    trace_rows = [r for r in rows if r["traceable"] in ("pass", "fail")]
    tokens = sum(int(_f(r["prompt_tokens"]) or 0) + int(_f(r["completion_tokens"]) or 0) for r in rows)
    cost = sum(_f(r["est_cost_usd"]) or 0.0 for r in rows)
    return {
        # ``n`` is what was attempted and ``n_scored`` is what the three rates
        # are actually over; they differ by the rows the arm never completed.
        # Both are published because a rate read next to the wrong one of them
        # is a wrong rate, and because the shared cross-check compares its own
        # recount of the scored rows against ``n_scored`` by name
        # (``tests/crosscheck_spec.json``).
        "n": n,
        "n_scored": len(ok),
        "solved": solved,
        "escalated": esc,
        "wrong": wrong,
        "run_error": n - len(ok),
        "form": (100.0 * sum(1 for r in form_rows if r["formulation_exact"]) / len(form_rows)) if form_rows else None,
        "trace": (100.0 * sum(1 for r in trace_rows if r["traceable"] == "pass") / len(trace_rows)) if trace_rows else None,
        "tokens": tokens,
        "cost": round(cost, 4),
    }


def _fmt(v: Any) -> str:
    if v is None or v == "":
        return "-"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def render_transcript(nn: int, r: Dict[str, str], trace: Optional[Dict[str, Any]], header: Dict[str, Any]) -> str:
    bar = "=" * 78
    out = [bar, f"TRANSCRIPT  {header['method']}  |  {header['model']}  |  {header['instance']}  |  {r['request_id']}", bar,
           f"date: {header['date']}   variant: {r.get('variant')}   seed: {r.get('seed')}   repeat: {r.get('repeat')}", ""]
    if trace is None:
        out += [f"[system]   no LLM; {header['method']} computes from the structured day", "",
                "[answer]", r.get("answer_text", ""), ""]
        return "\n".join(out)
    for m in trace.get("messages", []):
        role = m.get("role", "?")
        out.append(f"[{role}]")
        content = m.get("content")
        if content:
            out.append(str(content))
        for call in m.get("tool_calls", []) or []:
            fn = call.get("function", {}) if isinstance(call, dict) else {}
            out.append(f"  -> tool call {fn.get('name', '?')}({fn.get('arguments', '')})")
        out.append("")
    gate = trace.get("gate") or {}
    if gate:
        out.append("[gate]")
        for k in sorted(gate):
            if k.startswith("gate_E") and not k.endswith("_residual"):
                out.append(f"  {k[5:]}: {gate[k]}   residual={gate.get(k + '_residual', '')}")
        out.append(f"  verdict: {'pass' if _b(gate.get('gate_passed')) else 'fail'}  {gate.get('gate_reason', '')}")
        out.append("")
    out += ["[final answer]", str(trace.get("answer") or r.get("answer_text", "")), ""]
    u = trace.get("usage") or {}
    out.append(f"usage: {u.get('n_llm_calls', 0)} LLM calls, {u.get('n_tool_calls', 0)} tool calls, "
               f"{u.get('prompt_tokens', 0)} in / {u.get('completion_tokens', 0)} out tokens, {u.get('wall_time_s', 0)} s")
    return "\n".join(out)


def render_narrative(nn: int, r: Dict[str, str], trace: Optional[Dict[str, Any]], header: Dict[str, Any], request_text: str) -> str:
    out = [f"RUN {nn:02d}  |  {r['request_id']}  |  {header['method']}  |  {header['model']}  |  {header['instance']}  |  variant {r.get('variant')}",
           f"Request: {request_text.strip().splitlines()[-1] if request_text.strip() else ''}", ""]
    out.append("WHAT THE METHOD DID")
    if trace is None:
        out.append(f"  computed directly on the structured day ({header['method']}); no model, no prompt")
    else:
        step = 1
        for m in trace.get("messages", []):
            role = m.get("role")
            if role == "assistant" and m.get("tool_calls"):
                for call in m["tool_calls"]:
                    fn = call.get("function", {}) if isinstance(call, dict) else {}
                    out.append(f"  {step}. model called {fn.get('name', '?')}({fn.get('arguments', '')})"); step += 1
            elif role == "tool":
                out.append(f"       tool -> {str(m.get('content', ''))[:220]}")
            elif role == "assistant" and m.get("content"):
                out.append(f"  {step}. model answered ({len(str(m['content']))} chars)"); step += 1
        u = trace.get("usage") or {}
        out.append(f"  Totals: {u.get('n_llm_calls', 0)} LLM calls, {u.get('n_tool_calls', 0)} tool calls, "
                   f"{u.get('prompt_tokens', 0)} in / {u.get('completion_tokens', 0)} out tokens, {u.get('wall_time_s', 0)} s")
    out += ["", "FORMULATION  (were the sessions read as the day states them?)"]
    out.append(f"  sessions exact: {r.get('n_sessions_exact', '-')} of {r.get('n_sessions_truth', '-')}   "
               f"verdict: {str(r.get('formulation_status', '-')).upper()}   error: {r.get('formulation_error_type', '') or '-'}")
    out += ["", "STATE  (scored against the real day)"]
    out.append(f"  no hard violation: {r.get('no_hard_violation', '-')}   max violation: {_fmt(_f(r.get('max_violation_kw')))} kW   "
               f"gap: {_fmt(_f(r.get('gap_pct')))} %   comparable: {r.get('gap_comparable', '-')}   unmet: {_fmt(_f(r.get('unmet_kwh')))} kWh")
    out += ["", "REPORTING"]
    out.append(f"  numbers in the answer: {r.get('n_numbers', '-')}, untraceable: {r.get('n_untraceable', '-')} -> traceable: {r.get('traceability_status', '-')}")
    out.append(f"  answer: {r.get('answer_status', '-')}   truth: {r.get('answer_truth', '')}   given: {r.get('answer_given', '')}")
    out.append(f"  gate: {r.get('gate_passed', '-')}   {r.get('gate_reason', '')}")
    out += ["", f"OUTCOME: {str(r.get('outcome', '')).upper()}   ({r.get('outcome_reason', '')})"]
    return "\n".join(out)


def render_report(header: Dict[str, Any], rows: List[Dict[str, Any]], agg: Dict[str, Any]) -> str:
    n = agg["n"] or 1
    pct = lambda k: f"{100.0 * k / n:.1f} % ({k}/{agg['n']})"
    out = [f"# {header['method']} on {header['instance']}, {header['date']}, {header['model']}", "",
           f"Built from `{header['source']}` by `evaluation/postprocess.py`. No model was called to write this report.", "",
           "## Outcome", "",
           "| solved | escalated | wrong, unflagged | run error |", "|---|---|---|---|",
           f"| {pct(agg['solved'])} | {pct(agg['escalated'])} | {pct(agg['wrong'])} | {agg['run_error']} |", "",
           "The three outcomes are exclusive and sum to the request count.", "",
           "## Formulation, traceability, cost", "",
           "| formulation exact (days) | traceable answers | tokens | est. cost |", "|---|---|---|---|",
           f"| {_fmt(agg['form'])} % | {_fmt(agg['trace'])} % | {agg['tokens']:,} | ${agg['cost']:.4f} |", ""]
    for label, key in (("Wrong and unflagged", "wrong_silently"), ("Escalated", "escalated")):
        hits = [r for r in rows if r[key]]
        out += [f"## {label}: {len(hits)}", ""]
        out += [f"- `{r['nn']:02d}_{r['request_id']}` ({r['variant']}): {r['solved_reason']}" for r in hits] or ["none"]
        out.append("")
    out += ["## Every request", "", "| nn | request | variant | outcome | form. | trace | answer | gap % | tokens |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['nn']:02d} | `{r['request_id']}` | {r['variant']} | {r['outcome']} | "
                   f"{'exact' if r['formulation_exact'] else (r['formulation_error_type'] or '-')} | {r['traceable'] or '-'} | "
                   f"{r['answer_ok'] or '-'} | {_fmt(_f(r['gap_pct']))} | {int(_f(r['prompt_tokens']) or 0) + int(_f(r['completion_tokens']) or 0)} |")
    out.append("")
    return "\n".join(out)


# ------------------------------------------------------------------ the layout


def find_trace(run_set: Path, r: Dict[str, str]) -> Optional[Path]:
    """The raw trace of a row, wherever the run set put it.

    ``trace_path`` in rows.csv is absolute and may point at another run set on
    another machine, so only its part below ``traces/`` is trusted:
    ``<arm-dir>/<arm-dir>/<model>/<run_id>.json``. That relative path is what is
    searched for, in this run set and then in its siblings. Searching by file
    name alone is wrong: run ids repeat across methods (``2018-09-17_s0_r0``
    exists once per arm), and the first match was another method's trace.
    """
    hint = r.get("trace_path") or ""
    if "/traces/" in hint:
        rel = Path(hint.split("/traces/", 1)[1])
    else:
        return None
    candidates = [run_set] + [d for d in run_set.parent.iterdir() if d.is_dir() and d != run_set]
    for base in candidates:
        p = base / "traces" / rel
        if p.is_file():
            return p
    return None


def postprocess(run_set: Path, *, quiet: bool = False) -> List[Path]:
    """Build results/<instance>/<date>/<model>/<method>/ for every arm in a run set."""
    run_set = run_set.resolve()
    rows = read_rows(run_set)
    manifest = read_manifest(run_set)
    date = run_date(manifest)
    instance = str(manifest.get("site_id") or rows[0].get("site_id") or "caltech")
    requests: Dict[str, Dict[str, Any]] = {}
    req_file = run_set / "requests.jsonl"
    if req_file.exists():
        for line in req_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                requests[d["id"]] = d
    order = {rid: i + 1 for i, rid in enumerate(sorted(requests) or sorted({r["request_id"] for r in rows}))}

    written: List[Path] = []
    by_arm: Dict[str, List[Dict[str, str]]] = {}
    for r in rows:
        by_arm.setdefault(r["arm"], []).append(r)

    for arm, arm_rows in by_arm.items():
        folder = FOLDER_FOR_ARM.get(arm, arm.replace(":", "_"))
        model = model_short(arm_rows[0].get("model_resolved", ""), arm)
        out = RESULTS / instance / date / model / folder
        (out / "traces").mkdir(parents=True, exist_ok=True)
        (out / "raw").mkdir(exist_ok=True)
        header = {"method": folder, "runner_name": arm, "model": model, "instance": instance, "date": date,
                  "source": run_set.name}

        summary: List[Dict[str, Any]] = []
        for r in sorted(arm_rows, key=lambda x: order.get(x["request_id"], 0)):
            nn = order.get(r["request_id"], 0)
            stem = f"{nn:02d}_{r['request_id']}"
            req_text = str(requests.get(r["request_id"], {}).get("text", ""))
            trace = None
            src = find_trace(run_set, r) if arm not in ("optimum", "charge_asap") else None
            if src is not None:
                shutil.copyfile(src, out / "traces" / f"{stem}.json")
                try:
                    trace = json.loads(src.read_text(encoding="utf-8"))
                except ValueError:
                    trace = None
            else:
                (out / "traces" / f"{stem}.json").write_text(json.dumps(r, indent=1), encoding="utf-8")
            (out / "traces" / f"{stem}.transcript.txt").write_text(render_transcript(nn, r, trace, header), encoding="utf-8")
            (out / "traces" / f"{stem}.narrative.txt").write_text(render_narrative(nn, r, trace, header, req_text), encoding="utf-8")
            s = summary_row(nn, r)
            s["request_text"] = req_text.strip().splitlines()[-1] if req_text.strip() else ""
            summary.append(s)

        with (out / "summary.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=SUMMARY_COLUMNS)
            w.writeheader()
            for s in summary:
                w.writerow({k: ("" if s.get(k) is None else s.get(k)) for k in SUMMARY_COLUMNS})
        agg = aggregate(summary)
        (out / "summary.json").write_text(json.dumps({"header": header, "aggregate": agg}, indent=1), encoding="utf-8")
        (out / "REPORT.md").write_text(render_report(header, summary, agg), encoding="utf-8")
        if req_file.exists():
            shutil.copyfile(req_file, out / "requests.jsonl")
        for name in ("rows.csv", "scoreboard.md", "scoreboard.csv", "run_manifest.json", "REPORT.md"):
            if (run_set / name).exists():
                shutil.copyfile(run_set / name, out / "raw" / name)
        (out / "config.json").write_text(json.dumps({
            "kind": "migrated" if not manifest.get("command") else "run",
            "date": date, "instance": instance, "model": model,
            "model_requested": manifest.get("model_requested"), "model_resolved": manifest.get("model_resolved"),
            "method": folder, "method_runner_name": arm,
            "n": len(summary), "seeds": manifest.get("seeds"), "repeats": manifest.get("repeats"),
            "data_source": manifest.get("data_source"), "synthetic": manifest.get("synthetic"),
            "requests_digest": manifest.get("requests_digest"),
            "max_completion_tokens": manifest.get("max_completion_tokens"),
            "max_tool_rounds": manifest.get("max_tool_rounds"),
            "traceability_policy": manifest.get("traceability_policy"),
            "command": manifest.get("command"), "git_commit": manifest.get("git_commit"),
            "run_id": manifest.get("run_id"), "created_at": manifest.get("created_at"),
            "source_run_set": run_set.name,
        }, indent=2), encoding="utf-8")
        written.append(out)
        if not quiet:
            print(f"  {out.relative_to(RESULTS)}: {agg['n']} requests, solved {agg['solved']}, escalated {agg['escalated']}, wrong {agg['wrong']}")
    return written


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_set", nargs="+", help="results/ev_matrix_<model>[...] directories")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    for d in args.run_set:
        print(f"{d}:")
        postprocess(Path(d), quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

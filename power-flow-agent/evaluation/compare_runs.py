#!/usr/bin/env python3
"""Request-by-request comparison of two run directories (same requests, e.g. before and after a prompt change).

    .venv/bin/python evaluation/compare_runs.py <before_dir> <after_dir> [--out COMPARE.md] [--label-a 21-09] [--label-b matched]

Writes a Markdown table with one row per request: outcome, formulation verdict, the calls made
(executed, or declared for no-tools rows), the numbers that changed, and links to both runs'
narrative and transcript. Ends with a summary of what moved. No LLM, no network.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.postprocess import _fmt_call, _outcome, load_report, select_rows  # noqa: E402

OUT_LABEL = {"solved": "solved", "escalated": "escalated", "wrong_unflagged": "WRONG", "error": "error", "other": "other"}


def _rows(run_dir: Path) -> Dict[str, Dict[str, Any]]:
    report = load_report(run_dir / "raw")
    cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8")) if (run_dir / "config.json").is_file() else {}
    rows = select_rows(report, method=cfg.get("method_runner_name"), model=cfg.get("model") if cfg.get("kind") != "migrated" else cfg.get("model"), case=cfg.get("case"), condition=None)
    return {str(r["request_id"]): r for r in rows}


def _trace_stem(run_dir: Path, rid: str) -> Optional[str]:
    p = run_dir / "summary.csv"
    if not p.is_file():
        return None
    for r in csv.DictReader(p.open(encoding="utf-8")):
        if r.get("request_id") == rid:
            stems = sorted(x.stem.replace(".narrative", "") for x in (run_dir / "traces").glob(f"{int(r['nn']):02d}_*.narrative.txt"))
            return stems[0] if stems else None
    return None


def _calls(r: Dict[str, Any]) -> str:
    calls = r.get("declared_formulation") if r.get("declared_formulation") is not None else r.get("executed_calls")
    return " → ".join(_fmt_call(c) for c in (calls or [])) or "(none)"


def _form(r: Dict[str, Any]) -> str:
    fe = r.get("formulation_exact")
    if fe is None:
        return "n/a"
    return "exact" if fe else f"NOT exact ({r.get('formulation_error_type')})"


def compare(a: Path, b: Path, out: Path, label_a: str, label_b: str) -> Dict[str, int]:
    ra, rb = _rows(a), _rows(b)
    ids = sorted(set(ra) | set(rb))
    rel_a, rel_b = os.path.relpath(a, out.parent), os.path.relpath(b, out.parent)
    lines: List[str] = []
    lines.append(f"# {a.name} → {b.name}: request by request\n")
    lines.append(f"A = `{a.relative_to(PROJECT_ROOT)}` ({label_a}), B = `{b.relative_to(PROJECT_ROOT)}` ({label_b}). Same 40 generated requests. "
                 "Outcome: where the request ended (solved / escalated / WRONG unflagged). Calls: the tool calls executed, or the operations declared for a no-tools row. "
                 "Links open each run's narrative (N) and raw transcript (T).\n")
    moved = {"improved": 0, "worsened": 0, "same": 0, "form_fixed": 0, "form_broken": 0}
    lines.append("| # | request | A: outcome / formulation | A: calls | B: outcome / formulation | B: calls | change | A | B |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    rank = {"solved": 2, "escalated": 1, "wrong_unflagged": 0, "error": 0, "other": 0}
    for i, rid in enumerate(ids, start=1):
        x, y = ra.get(rid), rb.get(rid)
        if not x or not y:
            lines.append(f"| {i} | `{rid}` | {'missing' if not x else ''} | | {'missing' if not y else ''} | | | | |")
            continue
        oa, ob = _outcome(x), _outcome(y)
        fa, fb = x.get("formulation_exact"), y.get("formulation_exact")
        change = []
        if rank[ob] > rank[oa]:
            change.append("improved"); moved["improved"] += 1
        elif rank[ob] < rank[oa]:
            change.append("worsened"); moved["worsened"] += 1
        else:
            moved["same"] += 1
        if fa is False and fb is True:
            change.append("formulation fixed"); moved["form_fixed"] += 1
        elif fa is True and fb is False:
            change.append("formulation broken"); moved["form_broken"] += 1
        sa, sb = _trace_stem(a, rid), _trace_stem(b, rid)
        la = f"[N]({rel_a}/traces/{sa}.narrative.txt) [T]({rel_a}/traces/{sa}.transcript.txt)" if sa else ""
        lb = f"[N]({rel_b}/traces/{sb}.narrative.txt) [T]({rel_b}/traces/{sb}.transcript.txt)" if sb else ""
        req = str(x.get("request_text") or "").replace("|", "\\|")
        lines.append(f"| {i} | `{rid}`<br>{req} | **{OUT_LABEL[oa]}** / {_form(x)} | {_calls(x)} | **{OUT_LABEL[ob]}** / {_form(y)} | {_calls(y)} | {', '.join(change) or '—'} | {la} | {lb} |")
    def cnt(rows: Dict[str, Dict[str, Any]], k: str) -> int:
        return sum(1 for r in rows.values() if _outcome(r) == k)
    lines.append("")
    lines.append("## Summary\n")
    lines.append("| | A | B |")
    lines.append("|---|---:|---:|")
    for k, lab in (("solved", "solved"), ("escalated", "escalated"), ("wrong_unflagged", "wrong unflagged")):
        lines.append(f"| {lab} | {cnt(ra, k)} | {cnt(rb, k)} |")
    lines.append(f"| formulation exact | {sum(1 for r in ra.values() if r.get('formulation_exact'))} | {sum(1 for r in rb.values() if r.get('formulation_exact'))} |")
    lines.append("")
    lines.append(f"Requests that improved: {moved['improved']}; worsened: {moved['worsened']}; unchanged outcome: {moved['same']}. Formulation fixed on {moved['form_fixed']}, broken on {moved['form_broken']}.")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return moved


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before"); ap.add_argument("after")
    ap.add_argument("--out", default=None, help="default: <after>/COMPARE_vs_<before name>.md")
    ap.add_argument("--label-a", default="before"); ap.add_argument("--label-b", default="after")
    args = ap.parse_args(argv)
    a, b = Path(args.before).resolve(), Path(args.after).resolve()
    out = Path(args.out).resolve() if args.out else b / f"COMPARE_vs_{a.parent.parent.name}_{a.name}.md"
    moved = compare(a, b, out, args.label_a, args.label_b)
    print(f"wrote {out.relative_to(PROJECT_ROOT)}: {moved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
r"""Root-level summary linking several benchmarks/evaluate_llms.py result blocks.

Each block directory (e.g. one per validation round: LLM-only, architectures, stress,
prompting, rule_based) already has its own report.json / scoreboard.* / REPORT.md via
experiment_report.py. This script does not re-run anything or touch those files; it writes
one small markdown page one level up that (1) links to each block's REPORT.md and (2)
prints one consolidated 10-metric table per condition ("normal", "stress", ...; see
evaluate_llms.py --condition and fill_table.py --condition), with an explicit
(count/total) next to every rate so a small N never reads as more precise than it is.

Usage:
  .venv/bin/python benchmarks/build_root_summary.py \
      results_validation_gpt-5.4_llm_only results_validation_gpt-5.4_agents \
      results_validation_gpt-5.4_prompting results_validation_gpt-5.4_rule_based \
      results_validation_gpt-5.4_stress \
      --model openrouter:openai/gpt-5.4 --out results_validation_gpt-5.4_REPORT.md [--pdf]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.experiment_report import build_pdf  # noqa: E402
from benchmarks.fill_table import (  # noqa: E402
    COLUMNS,
    Column,
    MISSING,
    aggregate_all,
    best_single_call,
    find_reports,
    format_cell,
    load_case_rows,
    select_model,
    table_blocks,
)

# fill_table.py's own 10-column body table; no extra column here any more. "Faith." is now
# per-answer (V4 faithfulness and V5 currency together), which -- restricted to items whose
# reference is solvable -- is identical to the offline V(x,c,z,y) pass rate this used to add
# as a separate "V pass" column, so that column never carried information beyond what "Faith."
# now shows directly (2026-09-16).
TABLE_COLUMNS: tuple[Column, ...] = COLUMNS


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines) + "\n"


def _rate_counts(items: list[dict[str, Any]], name: str) -> tuple[Optional[int], Optional[int]]:
    """Mirrors experiment_report.py's own helper: (count, total) a rate column was computed over."""
    if name == "Form.":
        vals = [r.get("formulation_exact") for r in items]
        return sum(1 for v in vals if v is True), sum(1 for v in vals if v is not None)
    if name == "Solved":
        return sum(1 for r in items if r.get("solved") is True), len(items)
    if name == "Solver status":
        vals = [(r.get("metrics") or {}).get("convergence_match") for r in items if r.get("ok")]
        return sum(1 for v in vals if v), len(vals)
    if name == "SFR":
        vals = [r.get("safe_failure") for r in items]
        return sum(1 for v in vals if v is True), sum(1 for v in vals if v is not None)
    if name == "Faith.":
        vals = [r.get("faithful_answers") for r in items]
        return sum(1 for v in vals if v is True), sum(1 for v in vals if v is not None)
    return None, None


def _condition_table(case_rows: list[dict[str, Any]], raw_rows: list[dict[str, Any]], gated_baselines: bool = False) -> str:
    agg = aggregate_all(case_rows, columns=TABLE_COLUMNS)
    best = best_single_call(agg)
    names = [c.name for c in TABLE_COLUMNS]
    lines: list[str] = []
    table_rows: list[list[str]] = []
    for setting, rows in table_blocks(gated_baselines):
        for label, method in rows:
            key = best if method == "__best_single_call__" else method
            stats = agg.get(key) if key else None
            if stats is None:
                table_rows.append([setting.split(" (")[0], label] + [MISSING] * len(TABLE_COLUMNS))
                continue
            items = [r for r in raw_rows if str(r.get("method") or r.get("task")) == key]
            cells = []
            for c in TABLE_COLUMNS:
                val = stats.get(c.name)
                if c.name == "Calls" and str(key).startswith(("llm_only", "baseline_pf", "blueprint_pf")):
                    cells.append("n/a")
                    continue
                if c.name == "Tok." and key == "rule_based":
                    cells.append("n/a")
                    continue
                text = format_cell(val, c.fmt)
                count, total = _rate_counts(items, c.name)
                if c.fmt == "pct" and total:
                    text = f"{text} ({count}/{total})"
                cells.append(text)
            table_rows.append([setting.split(" (")[0], label] + cells)
    return _md_table(["Setting", "Method", *names], table_rows)


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("blocks", nargs="+", help="block result directories (each with its own report.json/REPORT.md)")
    ap.add_argument("--model", default=None, help="provider:model to keep when reports mix models")
    ap.add_argument("--out", required=True, help="output markdown file (written next to the block directories by convention)")
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--gated-baselines", action="store_true")
    args = ap.parse_args(argv)

    block_dirs = [Path(b) for b in args.blocks]
    paths = find_reports([str(b) for b in block_dirs])
    if not paths:
        raise SystemExit("no report.json found under any block directory")
    rows = load_case_rows(paths)
    model, rows = select_model(rows, args.model)

    conditions = sorted({str(r.get("condition") or "normal") for r in rows})

    lines = [f"# Resumen de bloques: `{model}`\n"]
    lines.append(f"Generado por `benchmarks/build_root_summary.py` a partir de {len(block_dirs)} bloques. No vuelve a correr nada ni toca los reportes de cada bloque.\n")
    lines.append("## Bloques\n")
    for b in block_dirs:
        report_md = b / "REPORT.md"
        n_items = sum(1 for r in rows if str(r.get("_source", "")).startswith(str(b)))
        link = f"[{b.name}/REPORT.md]({b.name}/REPORT.md)" if report_md.is_file() else f"`{b.name}` (sin REPORT.md)"
        lines.append(f"- {link} -- {n_items} filas de scoreboard_per_case")
    lines.append("")

    for cond in conditions:
        cond_rows = [r for r in rows if str(r.get("condition") or "normal") == cond]
        raw_rows_cond: list[dict[str, Any]] = []
        for b in block_dirs:
            import json as _json

            for p in find_reports([str(b)]):
                data = _json.loads(Path(p).read_text(encoding="utf-8"))
                if str((data.get("config") or {}).get("condition") or "normal") == cond:
                    raw_rows_cond.extend(data.get("runs") or [])
        lines.append(f"## Tabla consolidada -- condición `{cond}`\n")
        lines.append(_condition_table(cond_rows, raw_rows_cond, args.gated_baselines))
        lines.append("")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"written: {out_path} ({out_path.stat().st_size / 1024:.0f} KB; {len(conditions)} condition(s))")
    if args.pdf:
        ok, msg = build_pdf(out_path)
        print(("pdf: " if ok else "pdf omitido: ") + msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

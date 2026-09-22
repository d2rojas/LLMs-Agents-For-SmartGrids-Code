#!/usr/bin/env python3
r"""Build the split-tool-set before/after appendix table and the gpt-5.6-sol supplement
composite (2026-09-22, appendix build).

fill_supertable.py's --condition is one tag per invocation, so a before/after comparison
side by side per row needs a dedicated renderer rather than two separate
fill_supertable.py calls (see the comment above SPLIT_TOOL_SOURCES in
build_paper_tables.py) -- this is that renderer.

Run from power-flow-agent/ with no arguments:

    .venv/bin/python benchmarks/build_split_tool_appendix.py

Writes:
  - benchmarks/tab_pf_split_tool_before_after_validation.tex (+ .csv)
  - benchmarks/tab_pf_protocol_rows_gpt-5.6-sol_validation.tex (+ .csv), via fill_supertable.py
  - benchmarks/tab_pf_protocol_per_system_gpt-5.6-sol_validation.tex, via fill_supertable.py

Only Form., Solved and Wrong-unflagged are printed for the before/after table, not the
full 11-column protocol set: on gpt-4o-mini and sol, the "after" (split-tool) PFAgent run
is the 2026-09-21 launch, which also carries the live V6/V7 verification gate that the
"before" (load_split-era or matrix) PFAgent run predates -- see SPLIT_TOOL_SOURCES's
comment for why "after" points there instead of results_validation_load_split. That means
PFAgent's "after" side changes tool set AND gate together on those two models, a confound
that would make an Escalated column misleading (a gate-driven change, not a tool-set one).
Formulation is unaffected by the gate by construction (it is scored before any gate check
runs), so it stays clean on every row; ReAct has no gate at all, so its Solved and
Wrong-unflagged are a clean before-and-after for the tool-set change alone. The appendix
therefore restricts to the three columns that are informative under this confound, and
CAPTION below is emitted into the output so this does not need reconstructing by hand.
"""

from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks import build_paper_tables as bpt  # noqa: E402
from benchmarks.fill_table import (  # noqa: E402
    aggregate_all,
    find_reports,
    format_cell,
    load_case_rows,
)

OUT_APPENDIX = PROJECT_ROOT / "benchmarks" / "tab_pf_split_tool_before_after_validation.tex"
OUT_APPENDIX_CSV = OUT_APPENDIX.with_suffix(".csv")
OUT_SOL_ROWS = PROJECT_ROOT / "benchmarks" / "tab_pf_protocol_rows_gpt-5.6-sol_validation.tex"
OUT_SOL_PER_SYSTEM = PROJECT_ROOT / "benchmarks" / "tab_pf_protocol_per_system_gpt-5.6-sol_validation.tex"

ARCH_ROWS: tuple[tuple[str, str], ...] = (("pfagent", "PFAgent: ReAct + gate"), ("react_nogate", "ReAct"))
PRINTED_COLUMNS: tuple[str, ...] = ("Form.", "Solved", "Wrong-unflagged")

MODEL_LABELS = {
    "openrouter:openai/gpt-5.4": "GPT-5.4",
    "openrouter:openai/gpt-4o-mini": "gpt-4o-mini",
    "openrouter:openai/gpt-5.6-sol": "gpt-5.6-sol",
}

CAPTION = (
    r"% On gpt-4o-mini and gpt-5.6-sol, the ``after'' (split-tool) PFAgent run is the "
    r"2026-09-21 launch, which also carries the live V6/V7 verification gate; the "
    r"``before'' run predates V6/V7. PFAgent's after side therefore changes tool set and "
    r"gate together on those two models. The gate leaves formulation identical item for "
    r"item: the editor verified that in all five gated-ungated pairs the set of "
    r"formulation-exact request ids is the same -- GPT-5.4 original 25/40 both, GPT-5.4 "
    r"split 40/40 both, mini split 39/40 both, mini launch 40/40 both, sol launch 39/40 "
    r"both -- so Formulation stays clean on every row here, as a measured fact rather "
    r"than a construction argument. ReAct, which has no gate, is the clean "
    r"before-and-after for the tool-set change alone on Solved and Wrong-unflagged. "
    r"GPT-5.4 has no split-tool run for single-call or Plan-and-Act on either side, so "
    r"those architectures are not shown in this table."
)


def _aggregate(model: str, method: str, rel: str) -> Optional[dict]:
    d = PROJECT_ROOT / "benchmarks" / rel
    rescored = d / "report.rescored.json"
    if not rescored.is_file():
        if (d / "report.json").is_file():
            raise SystemExit(
                f"{d} has report.json but no report.rescored.json -- run "
                f"benchmarks/rescore.py on it before building the appendix ({model}/{method})"
            )
        print(f"note: no report under {d}; {model}/{method} will read as missing", file=sys.stderr)
        return None
    rows = [r for r in load_case_rows(find_reports([str(d)])) if r["method"] == method]
    if not rows:
        return None
    return aggregate_all(rows).get(method)


def _check_sums(label: str, agg: dict) -> None:
    solved = agg.get("Solved") or 0.0
    escalated = agg.get("Escalated") or 0.0
    wrong = agg.get("Wrong-unflagged") or 0.0
    total = solved + escalated + wrong
    if abs(total - 1.0) > 1e-6:
        raise SystemExit(
            f"{label}: Solved+Escalated+Wrong-unflagged = {total * 100:.1f}, not 100 -- "
            "refusing to write the appendix"
        )


def build_appendix() -> None:
    lines: list[str] = [
        r"% Auto-generated by benchmarks/build_split_tool_appendix.py -- do not hand-edit.",
        r"% Before = original modify_load tool set; After = set_active_load/set_load split.",
        CAPTION,
        r"% Form. & Solved & Wrong-unflagged, before then after, per architecture per model.",
    ]
    csv_rows: list[dict[str, Any]] = []
    n_written = 0
    for model, methods in bpt.SPLIT_TOOL_SOURCES.items():
        model_label = MODEL_LABELS.get(model, model)
        lines.append(rf"\multicolumn{{7}}{{l}}{{\textbf{{{model_label}}}}} \\")
        for method, row_label in ARCH_ROWS:
            paths = methods.get(method)
            if not paths:
                continue
            cells = [row_label]
            csv_row: dict[str, Any] = {"model": model_label, "method": method}
            for side in ("before", "after"):
                rel = paths[side]
                csv_row[f"{side}_dir"] = rel
                agg = _aggregate(model, method, rel)
                if agg is None:
                    cells.extend(["--"] * len(PRINTED_COLUMNS))
                    for col_name in PRINTED_COLUMNS:
                        csv_row[f"{side}_{col_name}"] = None
                    continue
                _check_sums(f"{model_label}/{method}/{side}", agg)
                for col_name in PRINTED_COLUMNS:
                    cells.append(format_cell(agg.get(col_name), "pct"))
                    csv_row[f"{side}_{col_name}"] = agg.get(col_name)
            lines.append(f"% source: before={paths['before']}  after={paths['after']}")
            lines.append(" & ".join(cells) + r" \\")
            csv_rows.append(csv_row)
            n_written += 1
        lines.append(r"\midrule")
    if lines and lines[-1] == r"\midrule":
        lines.pop()
    OUT_APPENDIX.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"written: {OUT_APPENDIX} ({n_written} rows)")

    fieldnames = ["model", "method", "before_dir"] + [f"before_{c}" for c in PRINTED_COLUMNS] + \
        ["after_dir"] + [f"after_{c}" for c in PRINTED_COLUMNS]
    with OUT_APPENDIX_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(csv_rows)
    print(f"written: {OUT_APPENDIX_CSV} ({len(csv_rows)} rows)")


def build_sol_supplement() -> None:
    sol_sources = bpt.SOURCES.get("openrouter:openai/gpt-5.6-sol")
    if not sol_sources:
        raise SystemExit("no gpt-5.6-sol block in SOURCES -- nothing to build the supplement from")
    base = PROJECT_ROOT / "benchmarks"
    with tempfile.TemporaryDirectory(prefix="build_split_tool_appendix_") as tmp:
        dirs = bpt._resolve_sources(Path(tmp), {"openrouter:openai/gpt-5.6-sol": sol_sources}, base)
        if not dirs:
            raise SystemExit("no rescored gpt-5.6-sol sources found -- nothing to build the supplement from")
        bpt._run([
            bpt.VENV_PY, "benchmarks/fill_supertable.py", *dirs,
            "--block-by", "model", "--layout", "blocks", "--wrap", "rows",
            "--out", str(OUT_SOL_ROWS), "--csv", str(OUT_SOL_ROWS.with_suffix(".csv")),
        ])
        bpt._run([
            bpt.VENV_PY, "benchmarks/fill_supertable.py", *dirs,
            "--block-by", "model", "--layout", "blocks", "--wrap", "tabular",
            "--out", str(OUT_SOL_PER_SYSTEM),
        ])


def main() -> int:
    build_appendix()
    build_sol_supplement()
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

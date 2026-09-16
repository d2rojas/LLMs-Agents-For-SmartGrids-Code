#!/usr/bin/env python3
r"""Per-system "super table" of the PFAgent benchmark for the supplementary material.

The paper's core table aggregates IEEE 14/30/57/118; this script writes the per-system
breakdown from the same ``report.json`` files, reusing the loaders, formatters, row
mapping and n/a rules of ``benchmarks/fill_table.py``. Two layouts:

  blocks   (default) one block per IEEE system, each with the 13 method rows and the 10
           protocol columns of the main table (Form., V_MAE, F_MAE, Solved, Solver status,
           B_mean, Faith., SFR, Calls, Tok.). Blocks are separated by ``\midrule`` and a
           full-width ``\multicolumn{12}{l}{\textbf{IEEE 30-bus}}`` row.
  compact  methods x systems for two metrics (Form. and Calls by default, ``--metrics``):
           13 rows x (n_systems x 2) columns.

``--wrap`` selects how much LaTeX surrounds the body rows: ``rows`` (default, body only,
to be wrapped by hand), ``tabular`` (``\scriptsize`` + ``\resizebox{\textwidth}{!}`` (blocks only;
the narrow compact table keeps its natural width) + ``tabular`` with the booktabs header, no
``table`` environment) or ``table`` (complete
standalone table with caption and label; ``--standalone`` is an alias). Labels:
``tab:pf_protocol_per_system`` (blocks) and ``tab:pf_by_system`` (compact).

Usage:
  .venv/bin/python benchmarks/fill_supertable.py benchmarks/results_matrix_gpt-4o-mini \
      --layout blocks --out benchmarks/tab_pf_protocol_per_system.tex \
      [--standalone] [--csv benchmarks/results_matrix_gpt-4o-mini/per_system.csv] \
      [--model openai:gpt-4o-mini] [--cases case14,case30] [--gated-baselines] [--no-prefer-rescored]

Conventions (as in fill_table.py): ``report.rescored.json`` is preferred when present;
Solved reads ``solved_rate`` and falls back to ``success_rate``; missing cells print
``--``; Calls is ``n/a`` for LLM-only rows and Tok. is ``n/a`` for the rule-based parser.
The "Single-call, best prompt" row uses the prompt with the best formulation rate on the
aggregate over all systems (the same prompt in every block), as in the main table.
The CSV has one row per (table row, system) with the raw (unrounded) numbers, ``--`` and
``n/a`` under the same rules.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.fill_table import (  # noqa: E402
    BEST_SINGLE_CALL,
    COLUMNS,
    MISSING,
    _is_llm_only_family,
    aggregate_all,
    best_single_call,
    case_buses,
    find_reports,
    format_cell,
    load_case_rows,
    select_model,
    table_blocks,
)

DEFAULT_OUT = PROJECT_ROOT / "benchmarks" / "tab_pf_protocol_per_system.tex"
NA = "n/a"
LABELS = {"blocks": "tab:pf_protocol_per_system", "compact": "tab:pf_by_system"}
COLUMN_NAMES = [c.name for c in COLUMNS]
COLUMN_HEADS = {"V_MAE": r"$V_{\mathrm{MAE}}$", "F_MAE": r"$F_{\mathrm{MAE}}$", "B_mean": r"$B_{\mathrm{mean}}$"}
# (group title, number of columns) over the 10 protocol columns, as in the main table
COLUMN_GROUPS: tuple[tuple[str, int], ...] = (
    ("Task utility", 4),
    ("Solver-grounded correctness", 2),
    ("Faithfulness and safe failure", 2),
    ("Cost", 2),
)
DEFAULT_COMPACT_METRICS = ("Form.", "Calls")

CAPTIONS = {
    "blocks": (
        r"Per-system breakdown of the aggregated protocol table: one block per IEEE test system, "
        r"40 requests per system, gpt-4o-mini, $k=1$, same tools and an eight-round budget where "
        r"rounds apply. Form.: formulation correctness (\%); $V_{\mathrm{MAE}}$ (p.u.), "
        r"$F_{\mathrm{MAE}}$ (MW); Solved: request solved end to end (\%); Solver status: reported "
        r"convergence matches the reference (\%); B\_mean: mean KCL residual of the reported flows "
        r"(MW); Faith.: traceable numbers (\%); SFR: safe-failure rate (\%); Calls: mean tool calls; "
        r"Tok.: mean tokens. n/a: the method has no tools or no LLM; --: not measured."
    ),
    "compact": (
        r"Formulation correctness (Form., \%) and mean tool calls (Calls) per IEEE test system, "
        r"40 requests per system, gpt-4o-mini, $k=1$. n/a: the method has no tools; --: not measured."
    ),
}


# --------------------------------------------------------------------------- data


def system_label(case_name: str) -> str:
    n = case_buses(case_name)
    return f"IEEE {n}-bus" if n else str(case_name)


def system_short(case_name: str) -> str:
    n = case_buses(case_name)
    return str(n) if n else str(case_name)


def apply_na(cells: list[Any], key: Optional[str]) -> list[Any]:
    """Capabilities the method does not have are n/a, not 0 (same rule as fill_table)."""
    if _is_llm_only_family(key):
        cells[COLUMN_NAMES.index("Calls")] = NA
    if key == "rule_based":
        cells[COLUMN_NAMES.index("Tok.")] = NA
    return cells


def table_rows(agg_all: dict[str, dict[str, Any]], gated_baselines: bool = False) -> list[tuple[str, int, str, Optional[str]]]:
    """[(setting cell, block size, row label, resolved method key or None)] for the 13 rows."""
    best = best_single_call(agg_all)
    out: list[tuple[str, int, str, Optional[str]]] = []
    for setting, rows in table_blocks(gated_baselines):
        for label, method in rows:
            key = best if method == BEST_SINGLE_CALL else method
            out.append((setting, len(rows), label, key))
    return out


def per_system_values(
    rows: list[dict[str, Any]], systems: list[str], table: list[tuple[str, int, str, Optional[str]]]
) -> dict[tuple[int, str], dict[str, Any]]:
    """{(row index, system): {column name: value or MISSING/NA, 'n_items': int, 'method_key': str}}.

    Rows are keyed by their index in ``table`` because prompt labels repeat across the
    LLM-only and Single-call blocks."""
    values: dict[tuple[int, str], dict[str, Any]] = {}
    for system in systems:
        agg = aggregate_all(rows, [system])
        for i, (_setting, _size, _label, key) in enumerate(table):
            stats = agg.get(key) if key else None
            cells = [stats.get(c.name) if stats else None for c in COLUMNS]
            cells = apply_na([MISSING if v is None else v for v in cells], key)
            rec = dict(zip(COLUMN_NAMES, cells))
            rec["n_items"] = int(stats["n_items"]) if stats else 0
            rec["method_key"] = key if stats else MISSING
            values[(i, system)] = rec
    return values


def _cell(rec: dict[str, Any], col_name: str) -> str:
    v = rec[col_name]
    if v in (MISSING, NA):
        return str(v)
    return format_cell(v, COLUMNS[COLUMN_NAMES.index(col_name)].fmt)


# --------------------------------------------------------------------------- rendering


def _multirow(setting: str, size: int) -> str:
    return rf"\multirow{{{size}}}{{*}}{{{setting}}}"


def render_blocks_body(values: dict, systems: list[str], table: list[tuple[str, int, str, Optional[str]]]) -> str:
    ncols = 2 + len(COLUMNS)
    lines: list[str] = []
    for s, system in enumerate(systems):
        if s:
            lines.append(r"\midrule")
        lines.append(rf"\multicolumn{{{ncols}}}{{l}}{{\textbf{{{system_label(system)}}}}} \\")
        prev_setting = None
        seen = 0
        for i, (setting, size, label, _key) in enumerate(table):
            if setting != prev_setting:
                if prev_setting is not None:
                    lines.append(r"\addlinespace")
                prev_setting, seen = setting, 0
            lead = _multirow(setting, size) if seen == 0 else ""
            seen += 1
            rec = values[(i, system)]
            cells = [_cell(rec, c) for c in COLUMN_NAMES]
            lines.append(f"{lead} & {label} & " + " & ".join(cells) + r" \\")
    return "\n".join(lines) + "\n"


def blocks_header() -> str:
    groups = " & ".join(rf"\multicolumn{{{n}}}{{c}}{{\textbf{{{title}}}}}" for title, n in COLUMN_GROUPS)
    rules, start = [], 3
    for _title, n in COLUMN_GROUPS:
        rules.append(rf"\cmidrule(lr){{{start}-{start + n - 1}}}")
        start += n
    heads = " & ".join(COLUMN_HEADS.get(c, rf"\textbf{{{c}}}") for c in COLUMN_NAMES)
    return "\n".join([f"& & {groups} " + r"\\", "".join(rules), rf"\textbf{{Setting}} & \textbf{{Method}} & {heads} \\", r"\midrule"]) + "\n"


def blocks_colspec() -> str:
    return "ll " + " ".join("c" * n for _t, n in COLUMN_GROUPS)


def render_compact_body(values: dict, systems: list[str], table: list[tuple[str, int, str, Optional[str]]], metrics: tuple[str, ...]) -> str:
    lines: list[str] = []
    prev_setting = None
    seen = 0
    for i, (setting, size, label, _key) in enumerate(table):
        if setting != prev_setting:
            if prev_setting is not None:
                lines.append(r"\midrule")
            prev_setting, seen = setting, 0
        lead = _multirow(setting, size) if seen == 0 else ""
        seen += 1
        cells = [_cell(values[(i, system)], m) for m in metrics for system in systems]
        lines.append(f"{lead} & {label} & " + " & ".join(cells) + r" \\")
    return "\n".join(lines) + "\n"


def compact_header(systems: list[str], metrics: tuple[str, ...]) -> str:
    n = len(systems)
    titles = {"Form.": r"Form. (\%)", "Calls": "Calls"}
    groups = " & ".join(rf"\multicolumn{{{n}}}{{c}}{{\textbf{{{titles.get(m, m)}}}}}" for m in metrics)
    rules = "".join(rf"\cmidrule(lr){{{3 + i * n}-{2 + (i + 1) * n}}}" for i in range(len(metrics)))
    heads = " & ".join(system_short(s) for _m in metrics for s in systems)
    return "\n".join([f"& & {groups} " + r"\\", rules, rf"\textbf{{Setting}} & \textbf{{Method}} & {heads} \\", r"\midrule"]) + "\n"


def compact_colspec(systems: list[str], metrics: tuple[str, ...]) -> str:
    return "ll " + " ".join("c" * len(systems) for _m in metrics)


def wrap(body: str, header: str, colspec: str, wrap_level: str, caption: str, label: str, resize: bool = True) -> str:
    """``resize``: wrap the tabular in ``\resizebox{\textwidth}{!}`` (the 13-column blocks layout);
    the narrow compact layout is left at natural width so it is not scaled up."""
    if wrap_level == "rows":
        return body
    tabular = "\n".join(
        [
            r"\scriptsize",
            r"\setlength{\tabcolsep}{3pt}",
            *([r"\resizebox{\textwidth}{!}{%"] if resize else []),
            rf"\begin{{tabular}}{{{colspec}}}",
            r"\toprule",
            header.rstrip("\n"),
            body.rstrip("\n"),
            r"\bottomrule",
            r"\end{tabular}" + ("}" if resize else ""),
        ]
    )
    if wrap_level == "tabular":
        return tabular + "\n"
    return "\n".join([r"\begin{table}[!ht]", r"\centering", rf"\caption{{{caption}}}", rf"\label{{{label}}}", tabular, r"\end{table}"]) + "\n"


def render(
    values: dict,
    systems: list[str],
    table: list[tuple[str, int, str, Optional[str]]],
    layout: str,
    wrap_level: str = "rows",
    metrics: tuple[str, ...] = DEFAULT_COMPACT_METRICS,
    caption: Optional[str] = None,
) -> str:
    if layout == "blocks":
        body, header, colspec = render_blocks_body(values, systems, table), blocks_header(), blocks_colspec()
    elif layout == "compact":
        body, header, colspec = render_compact_body(values, systems, table, metrics), compact_header(systems, metrics), compact_colspec(systems, metrics)
    else:
        raise ValueError(f"unknown layout {layout!r}")
    return wrap(body, header, colspec, wrap_level, caption if caption is not None else CAPTIONS[layout], LABELS[layout], resize=layout == "blocks")


# --------------------------------------------------------------------------- csv


CSV_FIELDS = ["setting", "method", "method_key", "case", "n_buses", "n_items", *COLUMN_NAMES]


def write_csv(path: Path, values: dict, systems: list[str], table: list[tuple[str, int, str, Optional[str]]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for i, (setting, _size, label, _key) in enumerate(table):
            for system in systems:
                rec = values[(i, system)]
                w.writerow(
                    {
                        "setting": setting.split(" (")[0],
                        "method": label,
                        "method_key": rec["method_key"],
                        "case": system,
                        "n_buses": case_buses(system),
                        "n_items": rec["n_items"],
                        **{c: rec[c] for c in COLUMN_NAMES},
                    }
                )
                n += 1
    return n


# --------------------------------------------------------------------------- main


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reports", nargs="+", help="report.json files or directories searched recursively")
    ap.add_argument("--layout", choices=("blocks", "compact"), default="blocks")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output .tex file")
    ap.add_argument("--wrap", choices=("rows", "tabular", "table"), default="rows", help="rows only (default), tabular with header, or complete table")
    ap.add_argument("--standalone", action="store_true", help="alias for --wrap table (caption + label)")
    ap.add_argument("--caption", default=None, help="override the standalone caption")
    ap.add_argument("--metrics", default=",".join(DEFAULT_COMPACT_METRICS), help="compact layout: comma-separated column names (default Form.,Calls)")
    ap.add_argument("--csv", default=None, help="also write one CSV row per (table row, system)")
    ap.add_argument("--model", default=None, help="provider:model to keep when reports mix models")
    ap.add_argument("--cases", default=None, help="comma-separated systems to include, in this order (default: all found, by bus count)")
    ap.add_argument("--gated-baselines", action="store_true", help="ReAct/Plan-and-Act rows from react/plan_act instead of *_nogate")
    ap.add_argument(
        "--prefer-rescored",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="use report.rescored.json when it sits next to a report.json (default: on)",
    )
    args = ap.parse_args(argv)
    wrap_level = "table" if args.standalone else args.wrap
    metrics = tuple(m.strip() for m in args.metrics.split(",") if m.strip())
    unknown = [m for m in metrics if m not in COLUMN_NAMES]
    if unknown:
        raise SystemExit(f"unknown metrics {unknown}; choose from {COLUMN_NAMES}")

    paths = find_reports(args.reports, prefer_rescored=args.prefer_rescored)
    if not paths:
        raise SystemExit("no report.json found")
    rows = load_case_rows(paths)
    model, rows = select_model(rows, args.model)
    found = sorted({str(r["case_name"]) for r in rows}, key=case_buses)
    if args.cases:
        systems = [c.strip() for c in args.cases.split(",") if c.strip()]
        rows = [r for r in rows if str(r["case_name"]) in systems]
    else:
        systems = found
    if not systems:
        raise SystemExit("no systems to tabulate")

    table = table_rows(aggregate_all(rows), args.gated_baselines)
    values = per_system_values(rows, systems, table)
    tex = render(values, systems, table, args.layout, wrap_level, metrics, args.caption)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(tex, encoding="utf-8")
    written = [out]
    n_csv = 0
    if args.csv:
        n_csv = write_csv(Path(args.csv), values, systems, table)
        written.append(Path(args.csv))

    n_rescored = sum(1 for p in paths if p.name == "report.rescored.json")
    best = next((k for _s, _n, label, k in table if label == "Single-call, best prompt"), None)
    filled = sum(1 for rec in values.values() if rec["method_key"] != MISSING)
    print(f"model: {model}   reports: {len(paths)} ({n_rescored} rescored)   systems: {', '.join(systems)}   layout: {args.layout} / {wrap_level}")
    print(f"cells filled: {filled}/{len(values)} (row x system)   best single-call prompt: {best or MISSING}")
    for (i, system), rec in values.items():
        if rec["method_key"] == MISSING:
            print(f"  missing: {table[i][0].split(' (')[0]} / {table[i][2]} / {system}")
    if n_csv:
        print(f"csv rows: {n_csv}")
    print("written: " + ", ".join(str(p) for p in written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

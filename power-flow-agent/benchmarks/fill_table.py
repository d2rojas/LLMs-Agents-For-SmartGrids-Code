#!/usr/bin/env python3
r"""Fill the rows of the paper's Table \ref{tab:pf_protocol} from benchmark reports.

Reads one or more ``report.json`` files written by ``benchmarks/evaluate_llms.py``
(files or directories, searched recursively), aggregates every method over the
systems it was run on (weighted mean of the per-case means, weight = item count,
or the per-metric denominator when the report carries one), maps method names to
the table rows and writes a ``.tex`` fragment with only the body rows of the
tabular, in the exact order and format of the skeleton in ``main.tex``.

Usage:
  .venv/bin/python benchmarks/fill_table.py benchmarks/results_matrix_openai_gpt-4o-mini \
      [--out benchmarks/tab_pf_protocol_rows.tex] [--model openai:gpt-4o-mini] \
      [--per-system] [--scaling-csv benchmarks/pf_scaling.csv] [--gated-baselines] [--no-prefer-rescored]

A ``report.rescored.json`` written by ``benchmarks/rescore.py`` next to a ``report.json`` is
preferred by default (``--no-prefer-rescored`` reads the originals). The Solved column reads
``solved_rate`` (answered correctly end to end) and falls back to ``success_rate`` for reports
that predate it.

Row mapping (method -> table row):
  llm_only:{structured,few_shot,cot,rag}     -> LLM-only block
  single_call:{structured,few_shot,cot,rag}  -> Single-call block
  rule_based                                 -> Rule-based parser, no LLM
  single_call:<best formulation rate>        -> Single-call, best prompt
  react_nogate  (react with --gated-baselines)       -> ReAct
  plan_act_nogate (plan_act with --gated-baselines)  -> Plan-and-Act
  pfagent                                    -> PFAgent: ReAct + gate
Missing methods or metrics are printed as ``--``.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_ROOT / "benchmarks" / "tab_pf_protocol_rows.tex"
MISSING = "--"

STRATEGIES: tuple[tuple[str, str], ...] = (
    ("structured", "Structured"),
    ("few_shot", "Few-shot"),
    ("cot", "Chain-of-thought"),
    ("rag", "RAG"),
)
BEST_SINGLE_CALL = "__best_single_call__"
FORMULATION_KEY = "formulation_exact_rate"


@dataclass(frozen=True)
class Column:
    """One numeric column of the table.

    ``keys`` are tried in order on the aggregate rows (first present wins), so a
    dedicated metric added later (e.g. ``feasibility_rate``) takes precedence
    over the current proxy. ``weight`` names the per-case denominator used for
    the weighted mean; ``"ok"`` means the number of solved items. ``scale``
    multiplies the weighted mean before formatting (e.g. seconds -> hours per 100
    cases); applied after aggregation rather than to each row's raw value, which is
    safe because the aggregate is a linear weighted mean and scaling commutes with
    that.
    """

    name: str
    keys: tuple[str, ...]
    fmt: str
    weight: str = "n_items"
    scale: float = 1.0


COLUMNS: tuple[Column, ...] = (
    # Task utility (Sec.~\ref{sec:evaluation}): formulation, solver-grounded numeric
    # error, end-to-end verdict. Solved = answered correctly end to end
    # (benchmarks/scoring.py); success_rate (run completed and parsed) is only the
    # fallback for reports written before R1.
    Column("Form.", (FORMULATION_KEY,), "pct", "formulation_exact_total"),
    # Restricted to requests whose formulation was exact (n/a counts as included for
    # LLM-only methods, which have no formulation step): unconditioned, this column
    # mixes solving the wrong problem with computing badly, and any tool-using row is
    # exactly zero once formulation is exact (the reference runs the same calls on the
    # same solver) -- see benchmarks.scoring's module docstring. Falls back to the
    # unconditioned mean for reports written before this field existed; the
    # unconditioned value stays available under that name for the supplement.
    Column("V_MAE", ("voltage_mae_formulation_exact_mean", "voltage_mae_mean"), "sci", "ok"),
    Column("F_MAE", ("flow_mae_mean",), "f2", "ok"),
    Column("Solved", ("solved_rate", "success_rate"), "pct"),
    # Solver-grounded correctness: reported convergence matches the reference, and the
    # KCL residual (B_mean) of the reported flows against the trusted solver.
    Column("Solver status", ("convergence_match_rate",), "pct"),
    Column("B_mean", ("kcl_mean_mismatch_mw_mean",), "sci", "ok"),
    # Faithfulness and safe failure. Per-answer (V4 faithfulness AND V5 currency
    # together): share of answers where every number traces to a tool output and comes
    # from the solve after the last network change -- not the mean of each answer's own
    # traceable-number share (faithful_numbers_mean), which lets a handful of partially-
    # contaminated answers barely move the aggregate (falls back to that older per-
    # number rate for reports written before this field existed).
    Column("Faith.", ("faithful_answers_rate", "faithful_numbers_mean"), "pct", "faithful_answers_total"),
    Column("SFR", ("safe_failure_rate",), "pct", "safe_failure_total"),
    # Cost.
    Column("Calls", ("n_tool_calls_mean",), "f1z"),
    Column("Tok.", ("total_tokens_mean",), "int"),
)


def table_blocks(gated_baselines: bool = False) -> list[tuple[str, list[tuple[str, str]]]]:
    """[(setting cell, [(row label, method key), ...]), ...] in skeleton order."""
    react = "react" if gated_baselines else "react_nogate"
    plan = "plan_act" if gated_baselines else "plan_act_nogate"
    return [
        (
            r"LLM-only (Sec.~\ref{sec:prompting})",
            [(label, f"llm_only:{s}") for s, label in STRATEGIES]
            # Third rung of the six-row ladder in main.tex's Table~\ref{tab:pf_architectures}
            # prose ("LLM only, forced, ... removes the option to abstain"): same structured
            # prompt as the "Structured" row above, minus the abstention clause.
            + [("LLM only, forced", "llm_only_forced:structured")],
        ),
        (r"Single-call (Sec.~\ref{sec:prompting})", [(label, f"single_call:{s}") for s, label in STRATEGIES]),
        (
            r"Architectures (Sec.~\ref{sec:agents})",
            [
                ("Rule-based parser, no LLM", "rule_based"),
                ("Single-call, best prompt", BEST_SINGLE_CALL),
                ("ReAct", react),
                ("Plan-and-Act", plan),
                ("PFAgent: ReAct + gate", "pfagent"),
            ],
        ),
    ]


# --------------------------------------------------------------------------- formatting


def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _is_llm_only_family(key: Optional[str]) -> bool:
    """``llm_only:<strategy>`` and ``llm_only_forced:<strategy>`` (no tools)."""
    k = str(key)
    return k.startswith("llm_only:") or k.startswith("llm_only_forced:")


def fmt_pct(x: Optional[float]) -> str:
    return f"{100.0 * x:.1f}" if _is_num(x) else MISSING


def fmt_sci(x: Optional[float]) -> str:
    r"""Three significant digits in the paper's style: ``$1.65{\times}10^{-5}$``."""
    if not _is_num(x):
        return MISSING
    if x == 0:
        return "0"
    exp = int(math.floor(math.log10(abs(x))))
    mant = x / 10**exp
    if abs(round(mant, 2)) >= 10.0:  # 9.996 -> 10.00 rolls over
        exp += 1
        mant /= 10.0
    return f"${mant:.2f}{{\\times}}10^{{{exp}}}$"


def fmt_fixed(x: Optional[float], decimals: int, zero: Optional[str] = None) -> str:
    if not _is_num(x):
        return MISSING
    if zero is not None and x == 0:
        return zero
    return f"{x:.{decimals}f}"


def fmt_int(x: Optional[float]) -> str:
    return f"{int(round(x))}" if _is_num(x) else MISSING


def format_cell(value: Optional[float], fmt: str) -> str:
    if fmt == "pct":
        return fmt_pct(value)
    if fmt == "sci":
        return fmt_sci(value)
    if fmt == "f2":
        return fmt_fixed(value, 2)
    if fmt == "f1":
        return fmt_fixed(value, 1)
    if fmt == "f1z":  # skeleton prints a bare 0 for methods that never call tools
        return fmt_fixed(value, 1, zero="0")
    if fmt == "int":
        return fmt_int(value)
    raise ValueError(f"unknown format {fmt!r}")


# --------------------------------------------------------------------------- loading


RESCORED_NAME = "report.rescored.json"


def find_reports(paths: Iterable[str], prefer_rescored: bool = True) -> list[Path]:
    """``report.json`` files under ``paths``; with ``prefer_rescored`` a sibling
    ``report.rescored.json`` (written by ``benchmarks/rescore.py``) replaces the original."""
    found: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            found.extend(sorted(p.rglob("report.json")))
        elif p.is_file():
            found.append(p)
        else:
            raise FileNotFoundError(f"{raw}: not a report.json or a directory")
    if prefer_rescored:
        found = [p.with_name(RESCORED_NAME) if p.name == "report.json" and p.with_name(RESCORED_NAME).is_file() else p for p in found]
    return found


def _case_rows(report: dict[str, Any], source: Path) -> list[dict[str, Any]]:
    """Per-(model, method, case) aggregate rows of one report."""
    rows = list(report.get("scoreboard_per_case") or [])
    if not rows:
        cases = list((report.get("config") or {}).get("cases") or [])
        if len(cases) == 1:
            rows = [{**r, "case_name": cases[0]} for r in report.get("scoreboard") or []]
        else:
            print(f"warning: {source}: no scoreboard_per_case and {len(cases)} cases; skipped", file=sys.stderr)
    default_condition = (report.get("config") or {}).get("condition") or "normal"
    out = []
    for r in rows:
        method = r.get("method") or r.get("task")
        if not method or not r.get("case_name"):
            continue
        condition = r.get("condition") or default_condition
        out.append({**r, "method": method, "condition": condition, "_source": str(source)})
    return out


class DuplicateReportRowError(ValueError):
    """Two reports carry the same (model, method, case, condition): a merge hazard, not
    a normal-vs-stress split, since that combination is caught via the condition tag."""


def load_case_rows(report_paths: Iterable[Path]) -> list[dict[str, Any]]:
    """Merge reports, keyed by (model, method, case, condition).

    Running the same method on the same case under a *different* condition (e.g.
    "normal" vs "stress") is expected and produces two distinct rows. Two reports
    carrying the exact same (model, method, case, condition) is a merge hazard --
    silently keeping "the latter" previously risked a stress-condition run quietly
    overwriting a normal-condition one in the paper table (see the R1 postmortem);
    this now raises instead.
    """
    merged: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    sources: dict[tuple[str, str, str, str], str] = {}
    for path in report_paths:
        report = json.loads(Path(path).read_text(encoding="utf-8"))
        for r in _case_rows(report, Path(path)):
            key = (str(r.get("model")), r["method"], str(r["case_name"]), str(r["condition"]))
            if key in merged:
                raise DuplicateReportRowError(
                    f"{key[:3]} condition={key[3]!r} found in both {sources[key]} and {path}; "
                    "if these are genuinely different conditions, pass --condition when generating "
                    "the report that is missing it, otherwise remove the stale duplicate."
                )
            merged[key] = r
            sources[key] = str(path)
    return list(merged.values())


def select_model(rows: list[dict[str, Any]], model: Optional[str]) -> tuple[str, list[dict[str, Any]]]:
    """Keep one LLM model (plus the LLM-free rule_based rows)."""
    llm_models = sorted({str(r.get("model")) for r in rows if not str(r.get("model", "")).startswith("none:")})
    if model is None:
        if len(llm_models) > 1:
            raise SystemExit(f"reports contain several models {llm_models}; choose one with --model")
        model = llm_models[0] if llm_models else "none:rule_based"
    kept = [r for r in rows if str(r.get("model")) == model or str(r.get("model", "")).startswith("none:")]
    return model, kept


# --------------------------------------------------------------------------- aggregation


def _first_key(row: dict[str, Any], keys: tuple[str, ...]) -> Optional[str]:
    """First key present with a numeric value (a key stored as ``null`` falls through)."""
    for k in keys:
        if k in row and _is_num(row.get(k)):
            return k
    return None


def _weight(row: dict[str, Any], col: Column) -> float:
    n_items = row.get("n_items")
    n_items = float(n_items) if _is_num(n_items) else 0.0
    if col.weight == "ok":
        sr = row.get("success_rate")
        w = round(float(sr) * n_items) if _is_num(sr) else 0.0
    else:
        w = row.get(col.weight)
        w = float(w) if _is_num(w) else n_items
    return w if w > 0 else 0.0


def aggregate_method(case_rows: list[dict[str, Any]], columns: tuple[Column, ...] = COLUMNS) -> dict[str, Any]:
    """Weighted mean of per-case means for every column, plus the total item count.

    ``columns`` defaults to the paper table's ``COLUMNS``; pass a longer tuple (e.g.
    ``COLUMNS + (Column("V pass", ...),)``) to aggregate extra columns for a supplement
    table without changing the shared default (see fill_supertable.py).
    """
    agg: dict[str, Any] = {"n_items": sum(int(r.get("n_items") or 0) for r in case_rows), "n_cases": len(case_rows)}
    for col in columns:
        num = den = 0.0
        for r in case_rows:
            key = _first_key(r, col.keys)
            if key is None or not _is_num(r.get(key)):
                continue
            w = _weight(r, col)
            if w <= 0:
                continue
            num += w * float(r[key])
            den += w
        agg[col.name] = (num / den) * col.scale if den > 0 else None
    return agg


def aggregate_all(
    rows: list[dict[str, Any]], cases: Optional[Iterable[str]] = None, columns: tuple[Column, ...] = COLUMNS
) -> dict[str, dict[str, Any]]:
    wanted = set(cases) if cases is not None else None
    by_method: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        if wanted is not None and str(r["case_name"]) not in wanted:
            continue
        by_method.setdefault(r["method"], []).append(r)
    return {m: aggregate_method(v, columns) for m, v in by_method.items()}


def best_single_call(agg: dict[str, dict[str, Any]]) -> Optional[str]:
    """single_call strategy with the highest formulation rate (ties: skeleton order)."""
    best: Optional[str] = None
    best_val = -1.0
    for s, _ in STRATEGIES:
        m = f"single_call:{s}"
        val = (agg.get(m) or {}).get("Form.")
        if _is_num(val) and val > best_val:
            best, best_val = m, val
    return best


# --------------------------------------------------------------------------- rendering


def render_rows(agg: dict[str, dict[str, Any]], gated_baselines: bool = False) -> tuple[str, list[tuple[str, str, str]]]:
    """Return (tex body, [(setting, row label, method key or MISSING), ...]) in row order."""
    best = best_single_call(agg)
    lines: list[str] = []
    mapping: list[tuple[str, str, str]] = []
    for b, (setting, rows) in enumerate(table_blocks(gated_baselines)):
        if b:
            lines.append(r"\midrule")
        for i, (label, method) in enumerate(rows):
            key = best if method == BEST_SINGLE_CALL else method
            stats = agg.get(key) if key else None
            mapping.append((setting.split(" (")[0], label, key if stats else MISSING))
            cells = [format_cell(stats.get(c.name) if stats else None, c.fmt) for c in COLUMNS]
            # capabilities the method does not have are n/a, not 0 (LLM-only has no tools; rule-based has no LLM)
            names = [c.name for c in COLUMNS]
            if _is_llm_only_family(key):
                cells[names.index("Calls")] = "n/a"
            if key == "rule_based":
                cells[names.index("Tok.")] = "n/a"
            lead = rf"\multirow{{{len(rows)}}}{{*}}{{{setting}}}" if i == 0 else ""
            lines.append(f"{lead} & {label} & " + " & ".join(cells) + r" \\")
    return "\n".join(lines) + "\n", mapping


def case_buses(case_name: str) -> int:
    m = re.search(r"(\d+)", str(case_name))
    return int(m.group(1)) if m else 0


def write_scaling_csv(path: Path, rows: list[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    out_rows = []
    for r in sorted(rows, key=lambda r: (r["method"], case_buses(r["case_name"]))):
        form_key = _first_key(r, (FORMULATION_KEY,))
        calls_key = _first_key(r, ("n_tool_calls_mean",))
        out_rows.append(
            {
                "method": r["method"],
                "case": r["case_name"],
                "n_buses": case_buses(r["case_name"]),
                "n_items": r.get("n_items"),
                "formulation_exact_rate": r.get(form_key) if form_key else None,
                "n_tool_calls_mean": r.get(calls_key) if calls_key else None,
            }
        )
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out_rows[0].keys()) if out_rows else ["method"])
        w.writeheader()
        w.writerows(out_rows)
    return len(out_rows)


# --------------------------------------------------------------------------- main


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reports", nargs="+", help="report.json files or directories searched recursively")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="output .tex fragment (body rows only)")
    ap.add_argument("--model", default=None, help="provider:model to keep when reports mix models")
    ap.add_argument("--cases", default=None, help="comma-separated cases to aggregate (default: all found)")
    ap.add_argument(
        "--condition",
        default="normal",
        help="only aggregate rows tagged with this condition ('normal', 'stress', ... see "
        "evaluate_llms.py --condition); 'all' aggregates every condition together, which mixes "
        "conditions with different pass/fail semantics into one mean -- almost never what you want "
        "for the main protocol table (default: normal)",
    )
    ap.add_argument("--per-system", action="store_true", help="also write <out stem>_<case>.tex per system")
    ap.add_argument("--scaling-csv", default=None, help="write formulation rate and tool calls per (method, case)")
    ap.add_argument("--gated-baselines", action="store_true", help="ReAct/Plan-and-Act rows from react/plan_act instead of *_nogate")
    ap.add_argument(
        "--prefer-rescored",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="use report.rescored.json (benchmarks/rescore.py) when it sits next to a report.json (default: on)",
    )
    args = ap.parse_args(argv)

    paths = find_reports(args.reports, prefer_rescored=args.prefer_rescored)
    if not paths:
        raise SystemExit("no report.json found")
    rows = load_case_rows(paths)
    if args.condition != "all":
        rows = [r for r in rows if str(r.get("condition") or "normal") == args.condition]
    model, rows = select_model(rows, args.model)
    cases = [c.strip() for c in args.cases.split(",") if c.strip()] if args.cases else None
    if cases:
        rows = [r for r in rows if str(r["case_name"]) in cases]
    found_cases = sorted({str(r["case_name"]) for r in rows}, key=case_buses)

    agg = aggregate_all(rows)
    body, mapping = render_rows(agg, args.gated_baselines)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    written = [out]

    if args.per_system:
        for c in found_cases:
            body_c, _ = render_rows(aggregate_all(rows, [c]), args.gated_baselines)
            p = out.with_name(f"{out.stem}_{c}{out.suffix}")
            p.write_text(body_c, encoding="utf-8")
            written.append(p)
    n_scaling = 0
    if args.scaling_csv:
        n_scaling = write_scaling_csv(Path(args.scaling_csv), rows)
        written.append(Path(args.scaling_csv))

    table_methods = {m for _, _, m in mapping if m != MISSING}
    extra = sorted(set(agg) - table_methods)
    filled = sum(1 for _, _, m in mapping if m != MISSING)
    print(f"model: {model}   reports: {len(paths)}   cases: {', '.join(found_cases) or '-'}")
    print(f"methods found ({len(agg)}): " + ", ".join(f"{m} [{agg[m]['n_cases']} cases, {agg[m]['n_items']} items]" for m in sorted(agg)))
    print(f"rows filled: {filled}/{len(mapping)}   best single-call prompt: {best_single_call(agg) or MISSING}")
    for setting, label, m in mapping:
        if m == MISSING:
            print(f"  missing: {setting} / {label}")
    if extra:
        print("not in the table (ablation): " + ", ".join(extra))
    if n_scaling:
        print(f"scaling rows: {n_scaling}")
    print("written: " + ", ".join(str(p) for p in written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

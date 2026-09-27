"""Standard experiment report (``REPORT.md``) for one EV benchmark results directory.

The EV counterpart of ``power-flow-agent/benchmarks/experiment_report.py``, and the
second half of the repository rule that every run ends with a ``REPORT.md`` next
to its results. It reads a directory written by ``scripts/run_ev_matrix.py``
(``run_manifest.json``, ``scoreboard.json``, ``rows.jsonl``) and writes a report
that states the model, the days, the seeds, the budget, and every number of the
table with the denominator it was computed over.

Sections, in this order:
  1. What was run          model, days, seeds, repeats, data source, cost
  2. Protocol              what makes the arms comparable, and where they are not
  3. Results               the scoreboard, every rate with its denominator
  4. Per-arm detail        outcome split, failures, repairs, answers
  5. Budget                tokens, calls and USD per arm
  6. Caveats               what these numbers do not support
  7. Files                 what is in the directory

No model is called, no key is read, and no network is touched: every number comes
from the rows the run already wrote. A directory whose run was a smoke test on
synthetic fixture days is reported as one, in the title, in the first line, and
again next to the results table, because a clean-looking table on generated
sessions is the most misleading artefact this case study can produce.

Usage (from ev-scheduling/):
  python -m scripts.ev_report <results_dir>
  python -m scripts.ev_report <results_dir> --out REPORT.md --pdf
"""

import argparse
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_ev_matrix import (  # noqa: E402
    ARMS,
    SMOKE_BANNER,
    SMOKE_SENTINEL_NAME,
    _fmt_num,
    _fmt_rate,
)

MISSING = "--"

SECTION_TITLES: Tuple[str, ...] = (
    "## 1. What was run",
    "## 2. Protocol",
    "## 3. Results",
    "## 4. Per-arm detail",
    "## 5. Budget",
    "## 6. Caveats",
    "## 7. Files",
)


# --------------------------------------------------------------------------- loading


def load_results(results_dir: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Read the three artefacts a run writes.

    Args:
        results_dir: Directory written by ``scripts/run_ev_matrix.py``.

    Returns:
        ``(meta, arm_summaries, rows)``.

    Raises:
        FileNotFoundError: If the directory is not a results directory. The
            message names what is missing rather than reporting an empty run.
    """
    results_dir = Path(results_dir)
    manifest_path = results_dir / "run_manifest.json"
    scoreboard_path = results_dir / "scoreboard.json"
    rows_path = results_dir / "rows.jsonl"
    missing = [p.name for p in (manifest_path, scoreboard_path, rows_path) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"{results_dir} is not a run_ev_matrix results directory; missing: {', '.join(missing)}"
        )
    meta = json.loads(manifest_path.read_text(encoding="utf-8"))
    scoreboard = json.loads(scoreboard_path.read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in rows_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return meta, list(scoreboard.get("arms") or []), rows


# --------------------------------------------------------------------------- helpers


def _rows_for(rows: Sequence[Dict[str, Any]], arm: str) -> List[Dict[str, Any]]:
    """Rows of one arm, in the order they were produced."""
    return [r for r in rows if r.get("arm") == arm]


def _pct(entry: Optional[Dict[str, Any]]) -> str:
    """A rate with its denominator, or ``n/a (0/0)``."""
    return _fmt_rate(entry)


def _bullet(text: str) -> str:
    return f"- {text}"


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """A Markdown table; an empty body becomes a one-line note instead."""
    if not rows:
        return "_no rows_"
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)


# --------------------------------------------------------------------------- sections


def section_what_was_run(meta: Dict[str, Any], rows: Sequence[Dict[str, Any]]) -> str:
    """Section 1: the configuration, stated so the run can be repeated."""
    lines = [SECTION_TITLES[0], ""]
    resolved = meta.get("models_resolved") or []
    lines += [
        _bullet(f"**run_id**: `{meta.get('run_id')}`, created {meta.get('created_at')}"),
        _bullet(f"**model requested**: `{meta.get('model_requested')}`"),
        _bullet(f"**model spec**: `{meta.get('model_spec')}`"),
        _bullet(
            "**model resolved by the provider**: "
            + (", ".join(f"`{m}`" for m in resolved) if resolved else "none reported")
            + ". This is the identifier the rows carry; a moving alias is what was asked for, "
            "this is what answered."
        ),
        _bullet(
            f"**days**: {meta.get('n_days')} "
            f"({', '.join(meta.get('dates') or []) or 'none'}), site `{meta.get('site_id')}`"
        ),
        _bullet(f"**seeds**: {meta.get('seeds')}   **repeats**: {meta.get('repeats')}"),
        _bullet(f"**items per arm**: {meta.get('items_per_arm')}"),
        _bullet(f"**data source**: `{meta.get('data_source')}`, synthetic: **{meta.get('synthetic')}**"),
        _bullet(
            f"**budget**: ceiling ${meta.get('budget_usd')}, spent "
            f"${_fmt_num(meta.get('spent_usd'), 4)} at "
            f"${meta.get('price_in_per_mtok')}/M prompt and "
            f"${meta.get('price_out_per_mtok')}/M completion ({meta.get('price_source')})"
        ),
        _bullet(
            f"**completion cap**: {meta.get('max_completion_tokens')} tokens for every LLM arm; "
            f"**tool rounds**: {meta.get('max_tool_rounds')} for the grounded arm"
        ),
        _bullet(f"**rows**: {len(rows)}, of which {meta.get('n_failed', 0)} did not complete"),
        _bullet(f"**Python**: {meta.get('python')}"),
    ]
    return "\n".join(lines)


def section_protocol(meta: Dict[str, Any], arms: Sequence[Dict[str, Any]]) -> str:
    """Section 2: what makes the arms comparable, and where they are not."""
    lines = [SECTION_TITLES[1], ""]
    lines += [
        "Every arm was given the same day list, the same generated requests, the same seeds, "
        "the same repeats and the same completion budget. The request list is generated once "
        "before any arm runs and handed to all of them; its digest is on every row:",
        "",
        f"    requests_digest = {meta.get('requests_digest')}",
        "",
        "Two rows carrying that digest were scored on the same inputs. Every arm is scored by "
        "the same function (`evaluation/outcome.py::classify_outcome`), with the same cost-gap "
        f"tolerance ({meta.get('gap_tol_pct')} %) and the same answer tolerances.",
        "",
        "### Arms",
        "",
    ]
    arm_rows = []
    for entry in arms:
        name = str(entry.get("arm"))
        arm = ARMS.get(name)
        arm_rows.append(
            [
                f"`{name}`",
                "yes" if arm and arm.uses_llm else "no",
                "yes" if arm and arm.has_gate else "no",
                "yes" if arm and arm.scores_formulation else "no",
                "yes" if arm and arm.grounded else "no",
                (arm.description if arm else ""),
            ]
        )
    lines.append(
        _table(
            ["arm", "calls a model", "has a gate", "scores formulation", "solver-grounded", "what it is"],
            arm_rows,
        )
    )
    pending = meta.get("pending_arms") or {}
    if pending:
        lines += ["", "### Registered but not run", ""]
        for name, reason in sorted(pending.items()):
            lines.append(_bullet(f"`{name}`: {reason}"))
    lines += [
        "",
        "### Where the arms are not symmetric",
        "",
        _bullet(
            "**Formulation** needs an extraction step to score. Only the solver-grounded arm "
            "exposes one, so the column is `n/a` for every other arm. That is not a pass."
        ),
        _bullet(
            "**Traceability** compares the numbers in an answer with the tool output they "
            "should be quoting. Policy in force: "
            f"`{meta.get('traceability_policy')}`. Under `grounded_only` it is measured only "
            "for arms whose answer was written by a model from a real tool output; a no-tools "
            "arm has nothing for its numbers to trace to, and marking it untraceable would "
            "report a definition rather than a measurement. The rows keep the answer text and "
            "the tool outputs, so the `all` policy can be applied later without re-running."
        ),
        _bullet(
            "**Escalation** requires a gate. An arm without one can never escalate, however "
            "confident or hedged its prose sounds."
        ),
        _bullet(
            "**The two reference rows answer with a formula written in the harness** "
            "(`run_ev_matrix.py::mechanical_answer_text`), computed from their own schedule and "
            "never from the ground truth. Their Answer column therefore measures that formula, "
            "not a system reading a request. They are reference rows, not competitors."
        ),
    ]
    strategies = meta.get("strategies") or {}
    if strategies:
        lines += ["", "### Prompting strategies", ""]
        for name, info in sorted(strategies.items()):
            sections = ", ".join(info.get("sections") or [])
            lines.append(_bullet(f"`{name}` uses `{info.get('strategy')}` with sections: {sections}"))
    return "\n".join(lines)


def section_results(meta: Dict[str, Any], arms: Sequence[Dict[str, Any]]) -> str:
    """Section 3: the table, every number next to its denominator."""
    lines = [SECTION_TITLES[2], ""]
    if meta.get("synthetic"):
        lines += [
            f"> **{SMOKE_BANNER}**",
            "",
        ]
    lines += [
        "Every cell is `rate (count/total)`. The total is the denominator that cell was "
        "computed over, which differs between columns by design: a term that an arm does not "
        "expose is not measured, and `n/a (0/0)` is not a pass.",
        "",
    ]
    headers = [
        "arm", "items", "failed", "Solved", "Escalated", "Wrong unflagged",
        "Form.", "FR", "Traceable", "Answer",
    ]
    body = []
    for entry in arms:
        body.append(
            [
                f"`{entry['arm']}`",
                str(entry["n_items"]),
                str(entry["n_failed"]),
                _pct(entry["solved"]),
                _pct(entry["escalated"]),
                _pct(entry["wrong_unflagged"]),
                _pct(entry["formulation_exact"]),
                _pct(entry["feasible"]),
                _pct(entry["traceable"]),
                _pct(entry["answer_correct"]),
            ]
        )
    lines += [_table(headers, body), ""]

    lines += ["### Physical quantities", ""]
    q_headers = ["arm", "mean cost $", "mean gap %", "mean unmet kWh", "mean % fully served"]
    q_body = [
        [
            f"`{e['arm']}`",
            _fmt_num(e["cost_usd_mean"], 4),
            _fmt_num(e["gap_pct_mean"], 3),
            _fmt_num(e["unmet_kwh_mean"], 3),
            _fmt_num(e["pct_fully_served_mean"], 2),
        ]
        for e in arms
    ]
    lines += [
        _table(q_headers, q_body),
        "",
        "The cost gap is against the CVXPY optimum of the same day at the same cap and prices. "
        "A gap is reported together with unmet energy: a schedule that is cheaper because it "
        "delivered less did not beat the optimum, and `gap_comparable` on the row says so.",
    ]
    if meta.get("synthetic"):
        lines += [
            "",
            f"> **{SMOKE_BANNER}**",
        ]
    return "\n".join(lines)


def section_per_arm(arms: Sequence[Dict[str, Any]], rows: Sequence[Dict[str, Any]]) -> str:
    """Section 4: the outcome split, failures, and what the parser had to repair."""
    lines = [SECTION_TITLES[3], ""]
    for entry in arms:
        name = str(entry["arm"])
        arm_rows = _rows_for(rows, name)
        ok_rows = [r for r in arm_rows if r.get("status") == "ok"]
        failed = [r for r in arm_rows if r.get("status") != "ok"]
        lines += [f"### `{name}` - {entry.get('arm_label')}", ""]
        lines += [
            _bullet(
                f"items {entry['n_items']}, completed {entry['n_ok']}, failed {entry['n_failed']}"
            ),
            _bullet(
                "outcome split: "
                f"solved {_pct(entry['solved'])}, escalated {_pct(entry['escalated'])}, "
                f"wrong unflagged {_pct(entry['wrong_unflagged'])}"
            ),
        ]
        if entry["n_failed"]:
            lines.append(_bullet(f"failure statuses: {', '.join(entry['failure_reasons'])}"))
            for row in failed[:5]:
                lines.append(
                    f"    - `{row.get('date')}` seed {row.get('seed')} repeat {row.get('repeat')}: "
                    f"{str(row.get('error'))[:200]}"
                )
            if len(failed) > 5:
                lines.append(f"    - ... and {len(failed) - 5} more, all in `rows.jsonl`")

        repaired = entry.get("repairs_changed") or {}
        if repaired.get("total"):
            lines.append(
                _bullet(
                    f"**reply needed repair before it could be scored**: {_pct(repaired)}; "
                    f"{entry.get('repair_rows_total', 0)} row repair(s) in total, and "
                    f"{entry.get('negative_cells_total', 0)} negative power value(s) kept "
                    "verbatim so the constraint checker scores them"
                )
            )
            kinds = Counter()
            for row in ok_rows:
                for key, value in row.items():
                    if key.startswith("repair_") and isinstance(value, int) and value:
                        kinds[key[len("repair_"):]] += value
            named = ", ".join(f"{k} {v}" for k, v in sorted(kinds.items()) if k not in
                              ("negative_cells", "cells_changed", "rows_changed"))
            if named:
                lines.append(_bullet(f"repairs by kind: {named}"))

        reasons = Counter(
            str(r.get("outcome_reason") or "") for r in ok_rows if not r.get("solved")
        )
        if reasons:
            lines.append(_bullet("why the unsolved days were unsolved:"))
            for reason, count in reasons.most_common(6):
                lines.append(f"    - {count}x {reason}")
        lines.append("")
    return "\n".join(lines)


def section_budget(meta: Dict[str, Any], arms: Sequence[Dict[str, Any]]) -> str:
    """Section 5: what the run cost, per arm and in total."""
    lines = [SECTION_TITLES[4], ""]
    headers = ["arm", "model calls", "tool calls", "prompt tok", "completion tok", "USD", "wall s"]
    body = [
        [
            f"`{e['arm']}`",
            str(e["n_llm_calls"]),
            str(e["n_tool_calls"]),
            f"{e['prompt_tokens']:,}",
            f"{e['completion_tokens']:,}",
            _fmt_num(e["est_cost_usd"], 4),
            _fmt_num(e["wall_s"], 1),
        ]
        for e in arms
    ]
    body.append(
        [
            "**total**",
            str(sum(e["n_llm_calls"] for e in arms)),
            str(sum(e["n_tool_calls"] for e in arms)),
            f"{sum(e['prompt_tokens'] for e in arms):,}",
            f"{sum(e['completion_tokens'] for e in arms):,}",
            _fmt_num(sum(e["est_cost_usd"] for e in arms), 4),
            _fmt_num(sum(e["wall_s"] for e in arms), 1),
        ]
    )
    lines += [
        _table(headers, body),
        "",
        f"Ceiling was ${meta.get('budget_usd')}. USD is priced from the tokens the provider "
        "reported, at the prices in the manifest. A row whose provider reported no usage is "
        "counted in `n_missing_usage` on the row and contributes zero here, so a run with "
        "unreported usage reads as cheap and the column next to it says why.",
    ]
    return "\n".join(lines)


def section_caveats(meta: Dict[str, Any], arms: Sequence[Dict[str, Any]], rows: Sequence[Dict[str, Any]]) -> str:
    """Section 6: what these numbers do not support."""
    lines = [SECTION_TITLES[5], ""]
    if meta.get("synthetic"):
        lines += [
            _bullet(
                f"**{SMOKE_BANNER}** Nothing in this report is a result. It shows that the "
                "harness runs end to end and that the arms produce the columns the table needs."
            ),
        ]
    n_items = max((e["n_items"] for e in arms), default=0)
    if n_items < 20:
        lines.append(
            _bullet(
                f"Only {n_items} item(s) per arm. Every rate here moves by "
                f"{100.0 / n_items:.1f} percentage points per day, so no difference between "
                "arms in this run is a finding."
            )
        )
    failed = sum(e["n_failed"] for e in arms)
    if failed:
        lines.append(
            _bullet(
                f"{failed} row(s) did not complete and are excluded from every rate. Read each "
                "rate next to the `failed` column."
            )
        )
    hashes = {
        str(r.get("system_prompt_hash")) for r in rows if r.get("system_prompt_hash")
    }
    if len(hashes) > 1:
        lines.append(
            _bullet(
                f"**{len(hashes)} distinct system-prompt hashes in one run.** The prompt changed "
                "while the run was in flight, so the rows are not one comparable block "
                "(repo CLAUDE.md, incident 2026-09-17). The hashes are on the rows."
            )
        )
    models = meta.get("models_resolved") or []
    if len(models) > 1:
        lines.append(
            _bullet(
                f"**{len(models)} distinct resolved model ids**: {', '.join(models)}. The alias "
                "moved during the run, so the rows are not one model's."
            )
        )
    missing_usage = sum(int(r.get("n_missing_usage") or 0) for r in rows)
    if missing_usage:
        lines.append(
            _bullet(
                f"{missing_usage} model call(s) came back with no usage reported, so the USD "
                "figures are a lower bound."
            )
        )
    lines += [
        _bullet(
            "`n/a (0/0)` in a column means the term was not measured for that arm. It is never "
            "a pass, and an arm is not better than another for having fewer measured terms."
        ),
        _bullet(
            "The two reference rows' Answer column measures a formula in the harness, not a "
            "system's reading of the request (see the Protocol section)."
        ),
    ]
    return "\n".join(lines)


def section_files(results_dir: Path, meta: Dict[str, Any]) -> str:
    """Section 7: what is in the directory."""
    lines = [SECTION_TITLES[6], ""]
    known = [
        ("run_manifest.json", "the whole protocol of this run, in one file"),
        ("rows.csv", "per-day rows, answer text truncated, for a spreadsheet"),
        ("rows.jsonl", "per-day rows, complete and untruncated; the record of last resort"),
        ("requests.jsonl", "the exact requests every arm was given"),
        ("scoreboard.md", "the table, with a banner when the run was a smoke test"),
        ("scoreboard.csv", "the same numbers, one row per arm, rates and denominators split"),
        ("scoreboard.json", "the same numbers plus the run metadata"),
        ("traces/", "one JSON trace per arm per day, as each component wrote it"),
        (SMOKE_SENTINEL_NAME, "present only when the run was a smoke test on fixtures"),
    ]
    body = []
    for name, what in known:
        path = results_dir / name
        if path.exists():
            size = (
                f"{sum(f.stat().st_size for f in path.rglob('*') if f.is_file()) / 1024:.0f} KB"
                if path.is_dir()
                else f"{path.stat().st_size / 1024:.0f} KB"
            )
            body.append([f"`{name}`", size, what])
    lines.append(_table(["file", "size", "what it is"], body))
    lines += [
        "",
        "A row carries: the arm, the day, the seed, the repeat index, the resolved model id, "
        "the hash of the prompt actually sent, every column of the table with its per-term "
        "status, the gate's per-condition row, **both** the ground-truth answer and the answer "
        "the system gave (on every row, including a day whose request only prescribes an "
        "operation), the parser's repair counts, the tokens, the calls, and the wall clock. "
        "That is what lets a later question about a scoring definition be answered from these "
        "files instead of by re-running the matrix.",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- assembly


def build_report(results_dir: Path) -> str:
    """Assemble the whole ``REPORT.md`` for one results directory."""
    meta, arms, rows = load_results(results_dir)
    synthetic = bool(meta.get("synthetic"))
    title = "EV Scheduling Benchmark Matrix - Experiment Report"
    if synthetic:
        title = "[SMOKE TEST - SYNTHETIC DATA] " + title
    head = [f"# {title}", ""]
    if synthetic:
        head += [
            "> # DO NOT CITE ANY NUMBER IN THIS REPORT",
            ">",
            f"> {SMOKE_BANNER}",
            "",
        ]
    head += [
        f"`{meta.get('run_id')}` - generated by `scripts/ev_report.py` from "
        f"`{Path(results_dir).name}`. No model was called to write this report.",
        "",
    ]
    parts = [
        "\n".join(head),
        section_what_was_run(meta, rows),
        section_protocol(meta, arms),
        section_results(meta, arms),
        section_per_arm(arms, rows),
        section_budget(meta, arms),
        section_caveats(meta, arms, rows),
        section_files(Path(results_dir), meta),
    ]
    return "\n\n".join(parts).rstrip() + "\n"


def write_pdf(md_path: Path) -> Optional[Path]:
    """Render the report to PDF with pandoc, when pandoc is installed.

    Returns:
        The PDF path, or None when pandoc is absent or the render failed. A
        failure is reported and never raises: the Markdown report is the
        deliverable and the PDF is a convenience.
    """
    if shutil.which("pandoc") is None:
        print("pandoc not found; skipping the PDF", file=sys.stderr)
        return None
    pdf_path = md_path.with_suffix(".pdf")
    command = ["pandoc", str(md_path), "-o", str(pdf_path)]
    if shutil.which("tectonic"):
        command += ["--pdf-engine=tectonic"]
    try:
        subprocess.run(command, check=True, capture_output=True)
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"pandoc failed, keeping the Markdown only: {exc}", file=sys.stderr)
        return None
    return pdf_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point. Returns 0 when the report was written."""
    parser = argparse.ArgumentParser(
        prog="python -m scripts.ev_report",
        description="Write REPORT.md for one scripts/run_ev_matrix.py results directory.",
    )
    parser.add_argument("results_dir", help="Directory written by scripts/run_ev_matrix.py.")
    parser.add_argument("--out", default="REPORT.md", help="Report file name inside that directory.")
    parser.add_argument("--pdf", action="store_true", help="Also render a PDF with pandoc.")
    args = parser.parse_args(argv)

    results_dir = Path(args.results_dir).expanduser().resolve()
    try:
        text = build_report(results_dir)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    out_path = results_dir / args.out
    out_path.write_text(text, encoding="utf-8")
    print(f"wrote {out_path}")
    if args.pdf:
        pdf = write_pdf(out_path)
        if pdf is not None:
            print(f"wrote {pdf}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

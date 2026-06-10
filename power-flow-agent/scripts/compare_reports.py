#!/usr/bin/env python3
"""Compare multiple benchmark report.json files across models/tasks.

Usage:
  python3 scripts/compare_reports.py --report /path/to/report.json --report /other/report.json
  python3 scripts/compare_reports.py --dir /path/to/results --dir /other/results

Outputs:
  - comparison.csv
  - comparison.md
  - optional --out-json comparison.json
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_FIELDS = [
    "success_rate",
    "voltage_mae_mean",
    "flow_mae_mean",
    "loading_rmse_mean",
    "voltage_f1_mean",
    "thermal_f1_mean",
    "convergence_match_rate",
    "prompt_tokens_mean",
    "completion_tokens_mean",
    "total_tokens_mean",
    "cost_usd_mean",
    "cost_usd_total",
]


def _load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _collect_report_paths(report_paths: list[str], dirs: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in report_paths:
        p = Path(raw)
        if p.is_dir():
            p = p / "report.json"
        if p.exists():
            found.append(p)

    for raw in dirs:
        d = Path(raw)
        if not d.is_dir():
            continue
        p = d / "report.json"
        if p.exists():
            found.append(p)

    # Deduplicate while preserving order
    uniq: list[Path] = []
    seen = set()
    for p in found:
        rp = str(p.resolve())
        if rp in seen:
            continue
        seen.add(rp)
        uniq.append(p)
    return uniq


def _flatten_scoreboard(report: dict[str, Any], report_label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    scoreboard = report.get("scoreboard") or []
    config = report.get("config", {})
    for row in scoreboard:
        out = {
            "report": report_label,
            "model": row.get("model"),
            "task": row.get("task"),
        }
        for k in DEFAULT_FIELDS:
            out[k] = row.get(k)
        out["cases"] = ",".join(config.get("cases", [])) if isinstance(config.get("cases"), list) else config.get("cases")
        out["runs"] = config.get("runs")
        out["temperature"] = config.get("temperature")
        out["timeout_s"] = config.get("timeout_s")
        rows.append(out)
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("# Comparison\n\n(no rows)\n", encoding="utf-8")
        return
    cols = list(rows[0].keys())
    lines = ["# Comparison\n\n"]
    lines.append("| " + " | ".join(cols) + " |\n")
    lines.append("|" + "|".join(["---"] * len(cols)) + "|\n")
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |\n")
    path.write_text("".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare benchmark report.json files.")
    parser.add_argument("--report", action="append", default=[], help="Path to report.json (repeatable)")
    parser.add_argument("--dir", action="append", default=[], help="Directory containing report.json (repeatable)")
    parser.add_argument("--out-dir", default="benchmarks/compare", help="Output directory")
    parser.add_argument("--out-json", default=None, help="Optional JSON output path")

    args = parser.parse_args(argv)

    report_files = _collect_report_paths(args.report, args.dir)
    if not report_files:
        raise SystemExit("No report.json files found. Use --report or --dir.")

    all_rows: list[dict[str, Any]] = []
    for p in report_files:
        report = _load_report(p)
        label = p.parent.name
        all_rows.extend(_flatten_scoreboard(report, label))

    out_dir = Path(args.out_dir)
    _write_csv(out_dir / "comparison.csv", all_rows)
    _write_md(out_dir / "comparison.md", all_rows)
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

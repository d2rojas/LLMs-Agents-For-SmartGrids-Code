"""Recompute average benchmark metrics from an existing CSV.

This script is intentionally lightweight so you can fix summary tables/plots
without re-running expensive benchmark pipelines (API calls, solver runs).

It can compute:
  - Unaligned averages: each pipeline averaged over the dates it has results for.
  - Aligned averages: each pipeline averaged over the intersection of dates
    shared by all pipelines present in the CSV (fair comparison).
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Set

import numpy as np


@dataclass(frozen=True)
class Row:
    pipeline: str
    date: str
    total_cost_usd: float
    peak_load_kw: float
    total_unmet_kwh: float
    pct_fully_served: float
    violation_count: float


def _read_rows(csv_path: Path) -> List[Row]:
    rows: List[Row] = []
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if not r.get("pipeline") or not r.get("date"):
                continue
            rows.append(
                Row(
                    pipeline=str(r["pipeline"]),
                    date=str(r["date"]),
                    total_cost_usd=float(r.get("total_cost_usd") or 0.0),
                    peak_load_kw=float(r.get("peak_load_kw") or 0.0),
                    total_unmet_kwh=float(r.get("total_unmet_kwh") or 0.0),
                    pct_fully_served=float(r.get("pct_fully_served") or 0.0),
                    violation_count=float(r.get("violation_count") or 0.0),
                )
            )
    return rows


def _pipelines_present(rows: Iterable[Row]) -> List[str]:
    seen = {r.pipeline for r in rows}
    ordered = [p for p in ["optimizer", "baseline", "agent"] if p in seen]
    # Keep any extra pipelines (if added later) deterministically.
    ordered += sorted(seen - set(ordered))
    return ordered


def _dates_by_pipeline(rows: Iterable[Row]) -> Dict[str, Set[str]]:
    out: Dict[str, Set[str]] = {}
    for r in rows:
        out.setdefault(r.pipeline, set()).add(r.date)
    return out


def _aligned_dates(rows: List[Row], pipelines: List[str]) -> Set[str]:
    dates = _dates_by_pipeline(rows)
    if not pipelines:
        return set()
    common = set(dates.get(pipelines[0], set()))
    for p in pipelines[1:]:
        common &= dates.get(p, set())
    return common


def _avg_for_pipeline(rows: List[Row], pipeline: str, keep_dates: Set[str] | None) -> Dict[str, object]:
    pr = [r for r in rows if r.pipeline == pipeline and (keep_dates is None or r.date in keep_dates)]
    if not pr:
        return {}
    return {
        "pipeline": pipeline,
        "n_days": len({r.date for r in pr}),
        "avg_cost_usd": float(np.mean([r.total_cost_usd for r in pr])),
        "avg_peak_kw": float(np.mean([r.peak_load_kw for r in pr])),
        "avg_unmet_kwh": float(np.mean([r.total_unmet_kwh for r in pr])),
        "avg_served_pct": float(np.mean([r.pct_fully_served for r in pr])),
        "avg_violations": float(np.mean([r.violation_count for r in pr])),
    }


def _write_average_table_md(avg_rows: List[Dict[str, object]], path: Path, *, title: str) -> None:
    lines = [
        title,
        "",
        "| Pipeline | Days | Avg Cost ($) | Avg Peak (kW) | Avg Unmet (kWh) | Avg Served (%) | Avg Violations |",
        "|----------|------|--------------|---------------|-----------------|----------------|----------------|",
    ]
    for r in avg_rows:
        lines.append(
            f"| {r['pipeline']:9} | {int(r['n_days']):4d} | {r['avg_cost_usd']:12.2f} | {r['avg_peak_kw']:14.2f} | "
            f"{r['avg_unmet_kwh']:17.2f} | {r['avg_served_pct']:16.2f} | {r['avg_violations']:16.2f} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _plot_average_bar(avg_rows: List[Dict[str, object]], path: Path, *, title: str) -> None:
    import matplotlib.pyplot as plt

    pipelines = [r["pipeline"] for r in avg_rows]
    x = np.arange(4)  # Cost, Peak, Unmet, Served
    width = 0.25
    n = len(pipelines)

    fig, ax = plt.subplots(figsize=(10, 5))
    for i, p in enumerate(pipelines):
        rec = next(x for x in avg_rows if x["pipeline"] == p)
        vals = [
            rec["avg_cost_usd"],
            rec["avg_peak_kw"],
            rec["avg_unmet_kwh"],
            rec["avg_served_pct"],
        ]
        offset = (i - n / 2 + 0.5) * width
        ax.bar(x + offset, vals, width, label=p.capitalize())

    ax.set_xticks(x)
    ax.set_xticklabels(["Cost ($)", "Peak (kW)", "Unmet (kWh)", "Served (%)"])
    ax.set_ylabel("Value")
    ax.set_title(title)
    ax.legend()
    ax.figure.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute benchmark averages from CSV.")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("benchmark_results") / "agent_vs_baseline_metrics.csv",
        help="Input CSV (default: benchmark_results/agent_vs_baseline_metrics.csv)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmark_results"),
        help="Output directory (default: benchmark_results/)",
    )
    parser.add_argument(
        "--mode",
        choices=["aligned", "unaligned", "both"],
        default="both",
        help="Which averages to write (default: both).",
    )
    args = parser.parse_args()

    csv_path = args.csv.resolve()
    out_dir = args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = _read_rows(csv_path)
    pipelines = _pipelines_present(rows)

    common_dates = _aligned_dates(rows, pipelines)

    if args.mode in ("unaligned", "both"):
        avg_rows = [_avg_for_pipeline(rows, p, keep_dates=None) for p in pipelines]
        avg_rows = [r for r in avg_rows if r]
        _write_average_table_md(
            avg_rows,
            out_dir / "average_results_table_unaligned.md",
            title="# Average Results (unaligned: each pipeline over its available days)",
        )
        _plot_average_bar(
            avg_rows,
            out_dir / "average_results_bar_unaligned.png",
            title="Average Results by Pipeline (unaligned)",
        )

    if args.mode in ("aligned", "both"):
        avg_rows = [_avg_for_pipeline(rows, p, keep_dates=common_dates) for p in pipelines]
        avg_rows = [r for r in avg_rows if r]
        _write_average_table_md(
            avg_rows,
            out_dir / "average_results_table.md",
            title=f"# Average Results (aligned: common days across pipelines = {len(common_dates)})",
        )
        _plot_average_bar(
            avg_rows,
            out_dir / "average_results_bar.png",
            title=f"Average Results by Pipeline (aligned, n={len(common_dates)} days)",
        )


if __name__ == "__main__":
    main()


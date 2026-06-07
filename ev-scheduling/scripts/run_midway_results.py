"""Compile all midway deliverable results into Midway_results/.

Runs Phase A (optimizer), agent pipeline, and baseline (LLM) across multiple
dates, collects metrics and plots, and writes a summary CSV + markdown report.

Requires:
  - ACN_DATA_API_TOKEN in .env
  - OPENAI_API_KEY in .env (for baseline only; Phase A and agent skip it if missing)

Usage (from project root with venv active):
  python -m scripts.run_midway_results
  python scripts/run_midway_results.py
"""

import csv
import json
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

_project_root = Path(__file__).resolve().parent.parent
if _project_root not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except ImportError:
    pass

import numpy as np

from agent.run import run_agent
from config.site import SiteConfig, TOUConfig, default_tou_rates
from constraints.checker import check
from data.loader.loader import load_sessions
from evaluation.metrics import (
    Metrics,
    charge_asap_schedule,
    compute_metrics,
    total_cost,
)
from optimization.solver import solve
from visualization.plots import plot_load_profile, plot_schedule

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OUTPUT_DIR = _project_root / "Midway_results"

# Dates with known Caltech charging activity (2018-2019 academic year).
# The ACN-Data API has dense coverage for these periods.
TEST_DATES: List[date] = [
    date(2019, 5, 1),
    date(2019, 5, 15),
    date(2019, 6, 3),
    date(2019, 6, 15),
    date(2018, 11, 5),
]

SITE_ID = "caltech"
P_MAX_KW = 50.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_config(n_steps: int, dt_hours: float):
    """Build SiteConfig and TOUConfig for the given horizon."""
    site = SiteConfig(P_max_kw=P_MAX_KW, n_steps=n_steps, dt_hours=dt_hours)
    tou = TOUConfig(rates_per_kwh=default_tou_rates(n_steps))
    return site, tou


def _metrics_row(
    label: str,
    day_date: date,
    n_sessions: int,
    metrics: Metrics,
    feasible: bool,
) -> Dict[str, object]:
    """Build one row for the summary CSV."""
    return {
        "pipeline": label,
        "date": str(day_date),
        "n_sessions": n_sessions,
        "total_cost_usd": round(metrics.total_cost_usd, 4),
        "peak_load_kw": round(metrics.peak_load_kw, 4),
        "total_unmet_kwh": round(metrics.total_unmet_kwh, 4),
        "pct_fully_served": round(metrics.pct_fully_served, 2),
        "cost_reduction_pct": (
            round(metrics.cost_reduction_vs_uncontrolled_pct, 2)
            if metrics.cost_reduction_vs_uncontrolled_pct is not None
            else None
        ),
        "violation_count": metrics.violation_count,
        "feasible": feasible,
    }


def _run_unit_tests() -> str:
    """Run project unit tests and return a summary string."""
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            cwd=str(_project_root),
            timeout=120,
        )
        return result.stdout + result.stderr
    except Exception as exc:
        return f"Failed to run tests: {exc}"


# ---------------------------------------------------------------------------
# Pipeline runners
# ---------------------------------------------------------------------------

def run_phase_a_for_date(
    day_date: date,
    out_dir: Path,
) -> Optional[Dict[str, object]]:
    """Run Phase A (optimizer only) for a single date. Return metrics row or None."""
    print(f"  [Phase A] Loading sessions for {SITE_ID} on {day_date} ...")
    day = load_sessions(site_id=SITE_ID, day_date=day_date)
    if len(day.sessions) == 0:
        print(f"  [Phase A] No sessions for {day_date}; skipping.")
        return None

    n_sess = len(day.sessions)
    print(f"  [Phase A] {n_sess} sessions loaded. Solving ...")
    site, tou = _build_config(day.n_steps, day.dt_hours)

    result = solve(day, site, tou)
    if not result.success:
        print(f"  [Phase A] Solver failed: {result.message}")
        return None

    check_result = check(result.schedule, day, site)

    site_p_max = float(site.get_P_max_at_step(0))
    uncontrolled = charge_asap_schedule(day, site_p_max)
    uc_cost = total_cost(uncontrolled, tou, day.dt_hours)
    metrics = compute_metrics(
        result.schedule, day, tou, day.dt_hours,
        violation_count=len(check_result.violations),
        uncontrolled_cost_usd=uc_cost,
    )

    tag = f"phase_a_{day_date}"
    plot_schedule(result.schedule, day, save_path=out_dir / f"{tag}_schedule.png")
    plot_load_profile(result.schedule, day, save_path=out_dir / f"{tag}_load.png")

    print(f"  [Phase A] cost=${metrics.total_cost_usd:.2f}  peak={metrics.peak_load_kw:.1f}kW  "
          f"unmet={metrics.total_unmet_kwh:.2f}kWh  served={metrics.pct_fully_served:.1f}%")
    return _metrics_row("phase_a", day_date, n_sess, metrics, check_result.feasible)


def run_agent_for_date(
    day_date: date,
    out_dir: Path,
) -> Optional[Dict[str, object]]:
    """Run agent pipeline for a single date. Return metrics row or None."""
    print(f"  [Agent]   Loading sessions for {SITE_ID} on {day_date} ...")
    day = load_sessions(site_id=SITE_ID, day_date=day_date)
    if len(day.sessions) == 0:
        print(f"  [Agent]   No sessions for {day_date}; skipping.")
        return None

    n_sess = len(day.sessions)
    print(f"  [Agent]   {n_sess} sessions loaded. Running agent pipeline ...")
    site, tou = _build_config(day.n_steps, day.dt_hours)

    agent_result = run_agent(day, site, tou, request="Minimize energy cost for this day.")
    check_result = check(agent_result.schedule, day, site)

    site_p_max = float(site.get_P_max_at_step(0))
    uncontrolled = charge_asap_schedule(day, site_p_max)
    uc_cost = total_cost(uncontrolled, tou, day.dt_hours)
    metrics = compute_metrics(
        agent_result.schedule, day, tou, day.dt_hours,
        violation_count=len(check_result.violations),
        uncontrolled_cost_usd=uc_cost,
    )

    tag = f"agent_{day_date}"
    plot_schedule(agent_result.schedule, day, save_path=out_dir / f"{tag}_schedule.png")
    plot_load_profile(agent_result.schedule, day, save_path=out_dir / f"{tag}_load.png")

    # Save explanation text
    explanation_path = out_dir / f"{tag}_explanation.txt"
    explanation_path.write_text(agent_result.explanation, encoding="utf-8")

    print(f"  [Agent]   cost=${metrics.total_cost_usd:.2f}  peak={metrics.peak_load_kw:.1f}kW  "
          f"unmet={metrics.total_unmet_kwh:.2f}kWh  served={metrics.pct_fully_served:.1f}%")
    return _metrics_row("agent", day_date, n_sess, metrics, check_result.feasible)


def run_baseline_for_date(
    day_date: date,
    out_dir: Path,
) -> Optional[Dict[str, object]]:
    """Run LLM baseline for a single date. Return metrics row or None."""
    import os
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        print("  [Baseline] OPENAI_API_KEY not set; skipping baseline.")
        return None

    from baseline.run import run_baseline

    print(f"  [Baseline] Loading sessions for {SITE_ID} on {day_date} ...")
    day = load_sessions(site_id=SITE_ID, day_date=day_date)
    if len(day.sessions) == 0:
        print(f"  [Baseline] No sessions for {day_date}; skipping.")
        return None

    n_sess = len(day.sessions)
    print(f"  [Baseline] {n_sess} sessions loaded. Calling LLM baseline ...")
    site, tou = _build_config(day.n_steps, day.dt_hours)

    baseline_result = run_baseline(day=day, site=site, tou=tou, model="gpt-4o", max_completion_tokens=2048)
    if not baseline_result.parse_success:
        print(f"  [Baseline] Parse failed: {baseline_result.parse_error}")

    check_result = check(baseline_result.schedule, day, site)

    site_p_max = float(site.get_P_max_at_step(0))
    uncontrolled = charge_asap_schedule(day, site_p_max)
    uc_cost = total_cost(uncontrolled, tou, day.dt_hours)
    metrics = compute_metrics(
        baseline_result.schedule, day, tou, day.dt_hours,
        violation_count=len(check_result.violations),
        uncontrolled_cost_usd=uc_cost,
    )

    tag = f"baseline_{day_date}"
    plot_schedule(baseline_result.schedule, day, save_path=out_dir / f"{tag}_schedule.png")
    plot_load_profile(baseline_result.schedule, day, save_path=out_dir / f"{tag}_load.png")

    print(f"  [Baseline] cost=${metrics.total_cost_usd:.2f}  peak={metrics.peak_load_kw:.1f}kW  "
          f"unmet={metrics.total_unmet_kwh:.2f}kWh  served={metrics.pct_fully_served:.1f}%")
    return _metrics_row("baseline", day_date, n_sess, metrics, check_result.feasible)


# ---------------------------------------------------------------------------
# Summary writers
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    "pipeline", "date", "n_sessions", "total_cost_usd", "peak_load_kw",
    "total_unmet_kwh", "pct_fully_served", "cost_reduction_pct",
    "violation_count", "feasible",
]


def write_csv(rows: List[Dict[str, object]], path: Path) -> None:
    """Write metrics rows to a CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_markdown_report(rows: List[Dict[str, object]], test_output: str, path: Path) -> None:
    """Generate a human-readable markdown summary of all results."""
    lines: List[str] = []
    lines.append("# Midway Results — ECE 285 EV Charging Schedule Assistant")
    lines.append("")
    lines.append("**Group #10**: Ryan Luo, Peter Quawas")
    lines.append("")
    lines.append("## Summary Table")
    lines.append("")

    # Markdown table header
    headers = [
        "Pipeline", "Date", "Sessions", "Cost ($)", "Peak (kW)",
        "Unmet (kWh)", "Served (%)", "Cost Red. (%)", "Violations", "Feasible",
    ]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for row in rows:
        cost_red = row["cost_reduction_pct"]
        cost_red_str = f"{cost_red}" if cost_red is not None else "N/A"
        cells = [
            str(row["pipeline"]),
            str(row["date"]),
            str(row["n_sessions"]),
            str(row["total_cost_usd"]),
            str(row["peak_load_kw"]),
            str(row["total_unmet_kwh"]),
            str(row["pct_fully_served"]),
            cost_red_str,
            str(row["violation_count"]),
            str(row["feasible"]),
        ]
        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    lines.append("## Plots")
    lines.append("")
    lines.append("Schedule heatmaps and load profiles are saved as PNG files in this directory.")
    lines.append("Each file is named `<pipeline>_<date>_schedule.png` or `<pipeline>_<date>_load.png`.")
    lines.append("")

    # List generated plot files
    plot_files = sorted(OUTPUT_DIR.glob("*.png"))
    if plot_files:
        for pf in plot_files:
            lines.append(f"- `{pf.name}`")
        lines.append("")

    lines.append("## Agent Explanations")
    lines.append("")
    explanation_files = sorted(OUTPUT_DIR.glob("*_explanation.txt"))
    if explanation_files:
        for ef in explanation_files:
            lines.append(f"### {ef.stem}")
            lines.append("")
            lines.append(f"> {ef.read_text(encoding='utf-8').strip()}")
            lines.append("")
    else:
        lines.append("No agent explanations generated.")
        lines.append("")

    lines.append("## Unit Test Results")
    lines.append("")
    lines.append("```")
    lines.append(test_output.strip())
    lines.append("```")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    # --- 1. Run unit tests ---
    print("=" * 60)
    print("Running unit tests ...")
    print("=" * 60)
    test_output = _run_unit_tests()
    print(test_output)

    # --- 2. Run pipelines across dates ---
    all_rows: List[Dict[str, object]] = []

    for day_date in TEST_DATES:
        print()
        print("=" * 60)
        print(f"Date: {day_date}")
        print("=" * 60)

        # Phase A (optimizer)
        try:
            row = run_phase_a_for_date(day_date, OUTPUT_DIR)
            if row is not None:
                all_rows.append(row)
        except Exception:
            print(f"  [Phase A] ERROR on {day_date}:")
            traceback.print_exc()

        # Agent pipeline
        try:
            row = run_agent_for_date(day_date, OUTPUT_DIR)
            if row is not None:
                all_rows.append(row)
        except Exception:
            print(f"  [Agent]   ERROR on {day_date}:")
            traceback.print_exc()

        # Baseline (LLM)
        try:
            row = run_baseline_for_date(day_date, OUTPUT_DIR)
            if row is not None:
                all_rows.append(row)
        except Exception:
            print(f"  [Baseline] ERROR on {day_date}:")
            traceback.print_exc()

    # --- 3. Write outputs ---
    print()
    print("=" * 60)
    print("Writing results ...")
    print("=" * 60)

    csv_path = OUTPUT_DIR / "metrics_summary.csv"
    write_csv(all_rows, csv_path)
    print(f"  CSV: {csv_path}")

    json_path = OUTPUT_DIR / "metrics_summary.json"
    json_path.write_text(json.dumps(all_rows, indent=2, default=str), encoding="utf-8")
    print(f"  JSON: {json_path}")

    report_path = OUTPUT_DIR / "REPORT.md"
    write_markdown_report(all_rows, test_output, report_path)
    print(f"  Report: {report_path}")

    print()
    print(f"Done. {len(all_rows)} result rows written to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()

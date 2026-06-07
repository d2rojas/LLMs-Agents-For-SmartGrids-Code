"""Compare Optimizer vs LLM Baseline vs Agent across 10–20 benchmark days.

Both the LLM baseline and Agent receive the same natural-language input per day
(e.g., "I have 44 EVs: EV1 arrives 08:00 leaves 17:00 needs 12.5 kWh, ...").
Produces per-day schedule/load plots, day-by-day comparison table, and averaged
results with bar chart.

Usage (from project root):
  python -m scripts.run_agent_vs_baseline
  python -m scripts.run_agent_vs_baseline --ndays 10
  python -m scripts.run_agent_vs_baseline --skip-baseline

Requires:
  - ACN_DATA_API_TOKEN in .env
  - OPENAI_API_KEY in .env (for agent and baseline)

Output:
  - benchmark_results/per_day/*.png (schedule + load plots per pipeline per date)
  - benchmark_results/agent_vs_baseline_metrics.csv
  - benchmark_results/day_by_day_comparison.md
  - benchmark_results/average_results_table.md
  - benchmark_results/average_results_bar.png
"""

import argparse
import csv
import os
import sys
import traceback
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except ImportError:
    pass

from agent.run import run_agent
from baseline.run import run_baseline
from config.site import SiteConfig, TOUConfig, default_tou_rates
from constraints.checker import check
from data.loader.loader import load_sessions
from data.format.schema import DaySessions
from evaluation.metrics import (
    Metrics,
    charge_asap_schedule,
    compute_metrics,
    total_cost,
)
from optimization.solver import solve
from visualization.plots import plot_load_profile, plot_schedule

# 20 benchmark dates (ACN-Data dense periods)
BENCHMARK_DATES: List[date] = [
    date(2019, 5, 1),
    date(2019, 5, 8),
    date(2019, 5, 15),
    date(2019, 5, 22),
    date(2019, 6, 3),
    date(2019, 6, 10),
    date(2019, 6, 15),
    date(2019, 6, 20),
    date(2019, 4, 15),
    date(2019, 4, 22),
    date(2018, 11, 5),
    date(2018, 11, 12),
    date(2018, 10, 15),
    date(2019, 3, 10),
    date(2019, 2, 20),
    date(2019, 1, 15),
    date(2019, 1, 22),
    date(2018, 12, 3),
    date(2018, 12, 10),
    date(2018, 9, 17),
]

SITE_ID = "caltech"
P_MAX_KW = 50.0
OUTPUT_DIR = _project_root / "benchmark_results"

BASELINE_MODEL = "gpt-4o"
BASELINE_MAX_TOKENS = 16384


def _step_to_time(step: int, dt_hours: float) -> str:
    """Convert step index to HH:MM string (step 0 = midnight)."""
    h = int(step * dt_hours) % 24
    m = int(((step * dt_hours) % 1) * 60)
    return f"{h:02d}:{m:02d}"


def _build_nl_request(day: DaySessions, site_id: str = "caltech", cap_kw: float = 50.0) -> str:
    """Build natural-language description of sessions (same style as agent input).

    Example: "I have 44 EVs at the Caltech site. EV1 arrives at 08:00, leaves at 17:00,
    needs 12.5 kWh. EV2 arrives at 09:15, ... Site power cap is 50 kW. Please minimize
    energy cost."
    """
    parts = [f"I have {len(day.sessions)} EVs at the {site_id} site."]
    for i, sess in enumerate(day.sessions, 1):
        arr = _step_to_time(sess.arrival_idx, day.dt_hours)
        dep = _step_to_time(sess.departure_idx, day.dt_hours)
        parts.append(f" EV{i} arrives at {arr}, leaves at {dep}, needs {sess.energy_kwh:.2f} kWh.")
    parts.append(f" Site power cap is {cap_kw:.0f} kW. Please minimize energy cost.")
    return "".join(parts)


def _build_nl_request_for_baseline(day: DaySessions, site_id: str = "caltech", cap_kw: float = 50.0) -> str:
    """Compact NL instruction for baseline to avoid token overflow and format confusion.

    For many sessions, the full EV-by-EV list can push output past token limits and
    distract the model from producing the schedule. Use a short goal statement that
    emphasizes serving sessions and minimizing cost.
    """
    n = len(day.sessions)
    if n <= 10:
        return _build_nl_request(day, site_id, cap_kw)
    # Compact form for large session counts: same goal, no long EV list
    return (
        f"I have {n} EVs at the {site_id} site with varying arrival, departure, and energy needs. "
        f"Site power cap is {cap_kw:.0f} kW. "
        "Minimize energy cost while fully serving as many sessions as possible. "
        "Session details are in the table above. Output only the schedule in the specified format."
    )


def _build_config(n_steps: int, dt_hours: float) -> Tuple[SiteConfig, TOUConfig]:
    site = SiteConfig(P_max_kw=P_MAX_KW, n_steps=n_steps, dt_hours=dt_hours)
    tou = TOUConfig(rates_per_kwh=default_tou_rates(n_steps))
    return site, tou


def _metrics_row(
    pipeline: str,
    day_date: date,
    n_sessions: int,
    metrics: Metrics,
    feasible: bool,
) -> Dict[str, object]:
    return {
        "pipeline": pipeline,
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


def run_phase_optimizer(
    day_date: date,
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
    per_day_dir: Path,
) -> Optional[Tuple[Dict[str, object], np.ndarray]]:
    """Run optimizer only. Returns (metrics_row, schedule) or None."""
    result = solve(day, site, tou)
    if not result.success:
        return None
    check_result = check(result.schedule, day, site)
    uc = charge_asap_schedule(day, float(site.get_P_max_at_step(0)))
    uc_cost = total_cost(uc, tou, day.dt_hours)
    metrics = compute_metrics(
        result.schedule, day, tou, day.dt_hours,
        violation_count=len(check_result.violations),
        uncontrolled_cost_usd=uc_cost,
    )
    row = _metrics_row("optimizer", day_date, len(day.sessions), metrics, check_result.feasible)

    plot_schedule(result.schedule, day, save_path=per_day_dir / f"{day_date}_optimizer_schedule.png")
    plot_load_profile(
        result.schedule, day,
        save_path=per_day_dir / f"{day_date}_optimizer_load.png",
        title=f"Optimizer - {day_date}",
    )
    return row, result.schedule


def run_phase_agent(
    day_date: date,
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
    nl_request: str,
    per_day_dir: Path,
) -> Optional[Tuple[Dict[str, object], np.ndarray]]:
    """Run agent pipeline. Returns (metrics_row, schedule) or None."""
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        return None
    agent_result = run_agent(day, site, tou, request=nl_request)
    check_result = check(agent_result.schedule, day, site)
    uc = charge_asap_schedule(day, float(site.get_P_max_at_step(0)))
    uc_cost = total_cost(uc, tou, day.dt_hours)
    metrics = compute_metrics(
        agent_result.schedule, day, tou, day.dt_hours,
        violation_count=len(check_result.violations),
        uncontrolled_cost_usd=uc_cost,
    )
    row = _metrics_row("agent", day_date, len(day.sessions), metrics, check_result.feasible)

    plot_schedule(agent_result.schedule, day, save_path=per_day_dir / f"{day_date}_agent_schedule.png")
    plot_load_profile(
        agent_result.schedule, day,
        save_path=per_day_dir / f"{day_date}_agent_load.png",
        title=f"Agent - {day_date}",
    )
    return row, agent_result.schedule


def run_phase_baseline(
    day_date: date,
    day: DaySessions,
    site: SiteConfig,
    tou: TOUConfig,
    nl_request: str,
    per_day_dir: Path,
) -> Optional[Tuple[Dict[str, object], np.ndarray]]:
    """Run LLM baseline with same NL input as agent. Returns (metrics_row, schedule) or None."""
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        return None
    baseline_result = run_baseline(
        day=day, site=site, tou=tou,
        model=BASELINE_MODEL,
        max_completion_tokens=BASELINE_MAX_TOKENS,
        instruction=nl_request,
    )
    if not baseline_result.parse_success:
        print(f"    [Baseline] WARNING: parse failed — {baseline_result.parse_error}")
    check_result = check(baseline_result.schedule, day, site)
    uc = charge_asap_schedule(day, float(site.get_P_max_at_step(0)))
    uc_cost = total_cost(uc, tou, day.dt_hours)
    metrics = compute_metrics(
        baseline_result.schedule, day, tou, day.dt_hours,
        violation_count=len(check_result.violations),
        uncontrolled_cost_usd=uc_cost,
    )
    row = _metrics_row("baseline", day_date, len(day.sessions), metrics, check_result.feasible)

    plot_schedule(baseline_result.schedule, day, save_path=per_day_dir / f"{day_date}_baseline_schedule.png")
    plot_load_profile(
        baseline_result.schedule, day,
        save_path=per_day_dir / f"{day_date}_baseline_load.png",
        title=f"Baseline - {day_date}",
    )
    return row, baseline_result.schedule


def _write_day_by_day_md(rows: List[Dict[str, object]], path: Path) -> None:
    """Write day-by-day comparison table."""
    dates = sorted({r["date"] for r in rows})
    pipelines = [p for p in ["optimizer", "baseline", "agent"] if any(r["pipeline"] == p for r in rows)]

    lines = [
        "# Day-by-Day Comparison",
        "",
        "| Date | Pipeline | Cost ($) | Peak (kW) | Unmet (kWh) | Served (%) | Violations |",
        "|------|----------|----------|-----------|-------------|------------|------------|",
    ]
    for d in dates:
        for p in pipelines:
            r = next((x for x in rows if x["date"] == d and x["pipeline"] == p), None)
            if r:
                lines.append(
                    f"| {d} | {p:9} | {r['total_cost_usd']:8.2f} | {r['peak_load_kw']:9.2f} | "
                    f"{r['total_unmet_kwh']:11.2f} | {r['pct_fully_served']:10.2f} | {r['violation_count']:10} |"
                )
        lines.append("")  # blank line between date groups
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_average_table_md(avg_rows: List[Dict[str, object]], path: Path) -> None:
    """Write average results table."""
    lines = [
        "# Average Results (aligned over common benchmark days)",
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


def _plot_average_bar(avg_rows: List[Dict[str, object]], path: Path) -> None:
    """Plot grouped bar chart for average metrics."""
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
        bars = ax.bar(x + offset, vals, width, label=p.capitalize())
    ax.set_xticks(x)
    ax.set_xticklabels(["Cost ($)", "Peak (kW)", "Unmet (kWh)", "Served (%)"])
    ax.set_ylabel("Value")
    ax.set_title("Average Results by Pipeline")
    ax.legend()
    ax.figure.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare Optimizer vs LLM Baseline vs Agent on 10–20 benchmark days.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})",
    )
    parser.add_argument(
        "--ndays",
        type=int,
        default=None,
        help="Use first N dates (default: all 20)",
    )
    parser.add_argument(
        "--skip-optimizer",
        action="store_true",
        help="Skip optimizer phase",
    )
    parser.add_argument(
        "--skip-baseline",
        action="store_true",
        help="Skip baseline (LLM-only) to save API cost",
    )
    parser.add_argument(
        "--skip-agent",
        action="store_true",
        help="Skip agent to save API cost",
    )
    parser.add_argument(
        "--dates",
        nargs="+",
        default=None,
        help="Override dates as YYYY-MM-DD",
    )
    args = parser.parse_args()

    dates = [date.fromisoformat(d) for d in args.dates] if args.dates else list(BENCHMARK_DATES)
    if args.ndays is not None:
        dates = dates[: args.ndays]

    out_dir = args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    per_day_dir = out_dir / "per_day"
    per_day_dir.mkdir(parents=True, exist_ok=True)

    if not os.environ.get("OPENAI_API_KEY", "").strip():
        print("WARNING: OPENAI_API_KEY not set. Agent and baseline will be skipped.", file=sys.stderr)
    if not os.environ.get("ACN_DATA_API_TOKEN", "").strip():
        print("WARNING: ACN_DATA_API_TOKEN not set. Session loading may fail.", file=sys.stderr)

    print(f"Output: {out_dir}")
    print(f"Dates: {len(dates)} ({dates[0]} to {dates[-1]})")
    print()

    all_rows: List[Dict[str, object]] = []
    for i, day_date in enumerate(dates, 1):
        print(f"[{i}/{len(dates)}] {day_date}")

        try:
            day = load_sessions(site_id=SITE_ID, day_date=day_date)
        except Exception as exc:
            print(f"    Load error: {exc}")
            continue
        if len(day.sessions) == 0:
            print("    No sessions; skipping.")
            continue

        site, tou = _build_config(day.n_steps, day.dt_hours)
        nl_request = _build_nl_request(day, site_id=SITE_ID, cap_kw=P_MAX_KW)

        if not args.skip_optimizer:
            try:
                out = run_phase_optimizer(day_date, day, site, tou, per_day_dir)
                if out:
                    row, _ = out
                    all_rows.append(row)
                    print(f"    Optimizer: cost=${row['total_cost_usd']:.2f}  served={row['pct_fully_served']:.1f}%")
                else:
                    print("    Optimizer: solver failed")
            except Exception:
                print("    Optimizer: ERROR")
                traceback.print_exc()

        if not args.skip_agent:
            try:
                out = run_phase_agent(day_date, day, site, tou, nl_request, per_day_dir)
                if out:
                    row, _ = out
                    all_rows.append(row)
                    print(f"    Agent:     cost=${row['total_cost_usd']:.2f}  served={row['pct_fully_served']:.1f}%")
                else:
                    print("    Agent:     skipped (no API key)")
            except Exception:
                print("    Agent:     ERROR")
                traceback.print_exc()

        if not args.skip_baseline:
            try:
                out = run_phase_baseline(day_date, day, site, tou, nl_request, per_day_dir)
                if out:
                    row, _ = out
                    all_rows.append(row)
                    print(f"    Baseline:  cost=${row['total_cost_usd']:.2f}  served={row['pct_fully_served']:.1f}%")
                else:
                    print("    Baseline:  skipped (no API key)")
            except Exception:
                print("    Baseline:  ERROR")
                traceback.print_exc()
        print()

    if not all_rows:
        print("No results. Check API keys and ACN_DATA_API_TOKEN.", file=sys.stderr)
        sys.exit(1)

    # CSV
    csv_path = out_dir / "agent_vs_baseline_metrics.csv"
    cols = [
        "pipeline", "date", "n_sessions", "total_cost_usd", "peak_load_kw",
        "total_unmet_kwh", "pct_fully_served", "cost_reduction_pct",
        "violation_count", "feasible",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for row in all_rows:
            writer.writerow({k: row.get(k) for k in cols})
    print(f"Wrote {csv_path} ({len(all_rows)} rows)")

    # Day-by-day table
    md_day_path = out_dir / "day_by_day_comparison.md"
    _write_day_by_day_md(all_rows, md_day_path)
    print(f"Wrote {md_day_path}")

    # Average results
    pipelines = ["optimizer", "baseline", "agent"]
    present = {r["pipeline"] for r in all_rows}
    pipelines = [p for p in pipelines if p in present]

    # Align averages over dates common to all pipelines present (fair comparison).
    dates_by_pipeline: Dict[str, set] = {}
    for r in all_rows:
        dates_by_pipeline.setdefault(r["pipeline"], set()).add(r["date"])
    common_dates = set(dates_by_pipeline.get(pipelines[0], set())) if pipelines else set()
    for p in pipelines[1:]:
        common_dates &= dates_by_pipeline.get(p, set())

    avg_rows: List[Dict[str, object]] = []
    for p in pipelines:
        pr = [r for r in all_rows if r["pipeline"] == p and r["date"] in common_dates]
        if pr:
            avg_rows.append({
                "pipeline": p,
                "n_days": len({r["date"] for r in pr}),
                "avg_cost_usd": sum(r["total_cost_usd"] for r in pr) / len(pr),
                "avg_peak_kw": sum(r["peak_load_kw"] for r in pr) / len(pr),
                "avg_unmet_kwh": sum(r["total_unmet_kwh"] for r in pr) / len(pr),
                "avg_served_pct": sum(r["pct_fully_served"] for r in pr) / len(pr),
                "avg_violations": sum(r["violation_count"] for r in pr) / len(pr),
            })

    avg_md_path = out_dir / "average_results_table.md"
    _write_average_table_md(avg_rows, avg_md_path)
    print(f"Wrote {avg_md_path}")

    avg_bar_path = out_dir / "average_results_bar.png"
    _plot_average_bar(avg_rows, avg_bar_path)
    print(f"Wrote {avg_bar_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()

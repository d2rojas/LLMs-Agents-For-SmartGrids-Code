"""Run Phase A, Phase B (baseline), and Phase C (agent) over multiple sites and dates; compile results.

Usage (from project root):
  python -m scripts.run_benchmark_abc
  python -m scripts.run_benchmark_abc --sites caltech jpl --ndays 15
  python -m scripts.run_benchmark_abc --sites caltech --dates 2019-06-15 2019-06-16 2019-06-17

Requires:
  - ACN_DATA_API_TOKEN in .env
  - OPENAI_API_KEY in .env (for Phase B and Phase C)

Output:
  - benchmark_results/metrics_abc.csv
  - benchmark_results/metrics_abc.json
"""

import argparse
import csv
import json
import sys
import traceback
from datetime import date
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

from agent.run import run_agent
from baseline.run import run_baseline
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

# Default dates with known ACN-Data activity (Caltech 2018–2019). Expand for more days.
DEFAULT_DATES: List[date] = [
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
]

DEFAULT_SITES: List[str] = ["caltech", "jpl"]
P_MAX_KW = 50.0
OUTPUT_DIR = _project_root / "benchmark_results"


def _build_config(n_steps: int, dt_hours: float) -> tuple:
    site = SiteConfig(P_max_kw=P_MAX_KW, n_steps=n_steps, dt_hours=dt_hours)
    tou = TOUConfig(rates_per_kwh=default_tou_rates(n_steps))
    return site, tou


def _metrics_row(
    pipeline: str,
    site_id: str,
    day_date: date,
    n_sessions: int,
    metrics: Metrics,
    feasible: bool,
) -> Dict[str, object]:
    return {
        "pipeline": pipeline,
        "site": site_id,
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


def run_phase_a(site_id: str, day_date: date) -> Optional[Dict[str, object]]:
    """Run Phase A (optimizer) for one (site, date). Return metrics row or None."""
    try:
        day = load_sessions(site_id=site_id, day_date=day_date)
    except Exception as exc:
        print(f"    [Phase A] Load error: {exc}")
        return None
    if len(day.sessions) == 0:
        return None
    n_sess = len(day.sessions)
    site, tou = _build_config(day.n_steps, day.dt_hours)
    result = solve(day, site, tou)
    if not result.success:
        print(f"    [Phase A] Solver failed: {result.message}")
        return None
    check_result = check(result.schedule, day, site)
    uc = charge_asap_schedule(day, float(site.get_P_max_at_step(0)))
    uc_cost = total_cost(uc, tou, day.dt_hours)
    metrics = compute_metrics(
        result.schedule, day, tou, day.dt_hours,
        violation_count=len(check_result.violations),
        uncontrolled_cost_usd=uc_cost,
    )
    return _metrics_row("phase_a", site_id, day_date, n_sess, metrics, check_result.feasible)


def run_phase_b(site_id: str, day_date: date) -> Optional[Dict[str, object]]:
    """Run Phase B (LLM baseline) for one (site, date). Return metrics row or None."""
    import os
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        return None
    try:
        day = load_sessions(site_id=site_id, day_date=day_date)
    except Exception as exc:
        print(f"    [Phase B] Load error: {exc}")
        return None
    if len(day.sessions) == 0:
        return None
    n_sess = len(day.sessions)
    site, tou = _build_config(day.n_steps, day.dt_hours)
    baseline_result = run_baseline(day=day, site=site, tou=tou, model="gpt-4o", max_completion_tokens=8192)
    check_result = check(baseline_result.schedule, day, site)
    uc = charge_asap_schedule(day, float(site.get_P_max_at_step(0)))
    uc_cost = total_cost(uc, tou, day.dt_hours)
    metrics = compute_metrics(
        baseline_result.schedule, day, tou, day.dt_hours,
        violation_count=len(check_result.violations),
        uncontrolled_cost_usd=uc_cost,
    )
    return _metrics_row("phase_b", site_id, day_date, n_sess, metrics, check_result.feasible)


def run_phase_c(site_id: str, day_date: date) -> Optional[Dict[str, object]]:
    """Run Phase C (agent) for one (site, date). Return metrics row or None."""
    import os
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        return None
    try:
        day = load_sessions(site_id=site_id, day_date=day_date)
    except Exception as exc:
        print(f"    [Phase C] Load error: {exc}")
        return None
    if len(day.sessions) == 0:
        return None
    n_sess = len(day.sessions)
    site, tou = _build_config(day.n_steps, day.dt_hours)
    agent_result = run_agent(day, site, tou, request="Minimize energy cost for this day.")
    check_result = check(agent_result.schedule, day, site)
    uc = charge_asap_schedule(day, float(site.get_P_max_at_step(0)))
    uc_cost = total_cost(uc, tou, day.dt_hours)
    metrics = compute_metrics(
        agent_result.schedule, day, tou, day.dt_hours,
        violation_count=len(check_result.violations),
        uncontrolled_cost_usd=uc_cost,
    )
    return _metrics_row("phase_c", site_id, day_date, n_sess, metrics, check_result.feasible)


CSV_COLUMNS = [
    "pipeline", "site", "date", "n_sessions", "total_cost_usd", "peak_load_kw",
    "total_unmet_kwh", "pct_fully_served", "cost_reduction_pct",
    "violation_count", "feasible",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Phase A, B, C over multiple sites and dates; write metrics CSV and JSON.",
    )
    parser.add_argument(
        "--sites",
        nargs="+",
        default=DEFAULT_SITES,
        help=f"Site IDs (default: {' '.join(DEFAULT_SITES)})",
    )
    parser.add_argument(
        "--ndays",
        type=int,
        default=None,
        help="Use first N dates from the default date list (default: use all)",
    )
    parser.add_argument(
        "--dates",
        nargs="+",
        default=None,
        help="Override dates as YYYY-MM-DD (e.g. 2019-06-15 2019-06-16)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})",
    )
    parser.add_argument(
        "--skip-b",
        action="store_true",
        help="Skip Phase B (baseline) to save time / API cost",
    )
    parser.add_argument(
        "--skip-c",
        action="store_true",
        help="Skip Phase C (agent) to save time / API cost",
    )
    args = parser.parse_args()

    if args.dates is not None:
        dates = [date.fromisoformat(d) for d in args.dates]
    else:
        dates = list(DEFAULT_DATES)
        if args.ndays is not None:
            dates = dates[: args.ndays]

    sites = args.sites
    if not dates:
        print("No dates to run. Use --dates or default list.", file=sys.stderr)
        sys.exit(1)
    out_dir = args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output: {out_dir}")
    print(f"Sites: {sites}")
    print(f"Dates: {len(dates)} ({dates[0]} to {dates[-1]})")
    print()

    all_rows: List[Dict[str, object]] = []
    n_combos = 0
    for site_id in sites:
        for day_date in dates:
            n_combos += 1
            print(f"[{n_combos}] {site_id} / {day_date}")

            # Phase A
            try:
                row = run_phase_a(site_id, day_date)
                if row is not None:
                    all_rows.append(row)
                    print(f"      Phase A: cost=${row['total_cost_usd']:.2f}  served={row['pct_fully_served']:.1f}%")
                else:
                    print("      Phase A: no sessions or solver failed")
            except Exception:
                print("      Phase A: ERROR")
                traceback.print_exc()

            # Phase B
            if not args.skip_b:
                try:
                    row = run_phase_b(site_id, day_date)
                    if row is not None:
                        all_rows.append(row)
                        print(f"      Phase B: cost=${row['total_cost_usd']:.2f}  served={row['pct_fully_served']:.1f}%")
                    else:
                        print("      Phase B: skipped (no sessions or no API key)")
                except Exception:
                    print("      Phase B: ERROR")
                    traceback.print_exc()

            # Phase C
            if not args.skip_c:
                try:
                    row = run_phase_c(site_id, day_date)
                    if row is not None:
                        all_rows.append(row)
                        print(f"      Phase C: cost=${row['total_cost_usd']:.2f}  served={row['pct_fully_served']:.1f}%")
                    else:
                        print("      Phase C: skipped (no sessions or no API key)")
                except Exception:
                    print("      Phase C: ERROR")
                    traceback.print_exc()
            print()

    # Write CSV and JSON
    csv_path = out_dir / "metrics_abc.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)
    print(f"Wrote {csv_path} ({len(all_rows)} rows)")

    json_path = out_dir / "metrics_abc.json"
    json_path.write_text(json.dumps(all_rows, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {json_path}")

    print("Done.")


if __name__ == "__main__":
    main()

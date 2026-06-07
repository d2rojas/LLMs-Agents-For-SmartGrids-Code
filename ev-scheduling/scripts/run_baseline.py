"""Script: load config and sessions, run baseline, optionally run checker and print metrics."""

# Usage:
#   python -m scripts.run_baseline
# or
#   python scripts/run_baseline.py
#
# Loads .env from project root so ACN_DATA_API_TOKEN is used.
# Build site + TOU config, run baseline, run constraint checker, print metrics.
# Optionally save schedule or pass --output experiments/baseline_out.json.

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

# Load .env from project root so ACN_DATA_API_TOKEN (and LLM keys) are available
_project_root = Path(__file__).resolve().parent.parent
if _project_root not in sys.path:
    sys.path.insert(0, str(_project_root))
try:
    from dotenv import load_dotenv

    load_dotenv(_project_root / ".env")
except ImportError:
    pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the prompting baseline: load sessions, call LLM, check, and compute metrics."
    )
    parser.add_argument("--site", default="caltech", help="ACN site (caltech, jpl, office001)")
    parser.add_argument(
        "--date",
        default=None,
        help="Date YYYY-MM-DD (default: yesterday)",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o",
        help="OpenAI chat model name to use for the baseline.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=8192,
        help="Maximum number of completion tokens to request from the model.",
    )
    args = parser.parse_args()

    from config.site import SiteConfig, TOUConfig, default_tou_rates
    from constraints.checker import check
    from data.loader.loader import load_sessions
    from evaluation.metrics import (
        Metrics,
        charge_asap_schedule,
        compute_metrics,
        total_cost,
    )
    from baseline.run import run_baseline

    day_date = date.today() - timedelta(days=1) if args.date is None else date.fromisoformat(args.date)

    # 1. Load sessions from ACN-Data API.
    try:
        day = load_sessions(site_id=args.site, day_date=day_date)
    except Exception as exc:
        print(f"Error while loading sessions for site={args.site} on date={day_date}: {exc}", file=sys.stderr)
        sys.exit(1)

    if len(day.sessions) == 0:
        print(
            f"No sessions returned for site={args.site} on date={day_date}.",
            file=sys.stderr,
        )
        print(
            "Try another --date (e.g., a date when the site had charging activity).",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Loaded {len(day.sessions)} sessions for {args.site} on {day_date}")

    # 2. Build site and TOU configuration (match Phase A defaults).
    site = SiteConfig(P_max_kw=50.0, n_steps=day.n_steps, dt_hours=day.dt_hours)
    tou = TOUConfig(rates_per_kwh=default_tou_rates(day.n_steps))

    # 3. Run baseline (LLM call + parse).
    baseline_result = run_baseline(
        day=day,
        site=site,
        tou=tou,
        model=args.model,
        max_completion_tokens=args.max_tokens,
    )

    if not baseline_result.parse_success:
        print("Baseline parse was not successful.", file=sys.stderr)
        if baseline_result.parse_error:
            print(f"Parse error: {baseline_result.parse_error}", file=sys.stderr)
        # We still continue to run the checker and metrics on whatever schedule we have.

    schedule = baseline_result.schedule

    # 4. Check constraints on the baseline schedule.
    check_result = check(schedule, day, site)

    # 5. Compute uncontrolled (charge-asap) baseline and metrics.
    uncontrolled_schedule = charge_asap_schedule(day, site_p_max=float(site.P_max_kw))
    uncontrolled_cost = total_cost(uncontrolled_schedule, tou, dt_hours=day.dt_hours)

    metrics: Metrics = compute_metrics(
        schedule,
        day,
        tou,
        dt_hours=day.dt_hours,
        violation_count=len(check_result.violations),
        uncontrolled_cost_usd=uncontrolled_cost,
    )

    # 6. Report results.
    print()
    print("=== Baseline results ===")
    print(f"Feasible (no constraint violations): {check_result.feasible}")
    print(f"Number of violations: {len(check_result.violations)}")
    print(f"Total cost (USD): {metrics.total_cost_usd:.2f}")
    print(f"Total unmet energy (kWh): {metrics.total_unmet_kwh:.3f}")
    print(f"Peak load (kW): {metrics.peak_load_kw:.2f}")
    print(f"Percent of sessions fully served (%): {metrics.pct_fully_served:.1f}")
    if metrics.cost_reduction_vs_uncontrolled_pct is not None:
        print(
            "Cost reduction vs uncontrolled charge-asap baseline (%): "
            f"{metrics.cost_reduction_vs_uncontrolled_pct:.1f}"
        )

    if not check_result.feasible and check_result.violations:
        print()
        print("Constraint violations (first 10 shown):")
        for v in check_result.violations[:10]:
            print(
                f"- kind={v.kind}, session_id={v.session_id}, "
                f"time_step={v.time_step}, message={v.message}"
            )


if __name__ == "__main__":
    main()

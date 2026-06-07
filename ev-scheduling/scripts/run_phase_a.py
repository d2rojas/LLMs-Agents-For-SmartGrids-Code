"""Phase A integration: load sessions from ACN-Data API, solve, check, compute metrics, plot.

Requires ACN_DATA_API_TOKEN in .env. No synthetic data.

Usage (from project root):
  python -m scripts.run_phase_a [--site SITE] [--date YYYY-MM-DD]
  python scripts.run_phase_a.py

Writes schedule and load profile to experiments/ if the directory exists.
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if _project_root not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except ImportError:
    pass


def main() -> None:
    # --- 1. Parse CLI: site and date (default yesterday) ---
    parser = argparse.ArgumentParser(description="Phase A: load from API, solve, check, metrics, plot")
    parser.add_argument("--site", default="caltech", help="ACN site (caltech, jpl, office001)")
    parser.add_argument("--date", default=None, help="Date YYYY-MM-DD (default: yesterday)")
    args = parser.parse_args()

    from config.site import SiteConfig, TOUConfig, default_tou_rates
    from constraints.checker import DEFAULT_TOL, check
    from data.loader.loader import load_sessions
    from evaluation.metrics import charge_asap_schedule, compute_metrics, total_cost
    from optimization.solver import solve
    from visualization.plots import plot_load_profile, plot_schedule

    day_date = date.today() - timedelta(days=1) if args.date is None else date.fromisoformat(args.date)

    # --- 2. Load sessions from ACN-Data API (requires ACN_DATA_API_TOKEN in .env) ---
    try:
        day = load_sessions(site_id=args.site, day_date=day_date)
    except ValueError as e:
        print("Error:", e, file=sys.stderr)
        print("Set ACN_DATA_API_TOKEN in .env or pass it in the environment.", file=sys.stderr)
        sys.exit(1)
    except ImportError as e:
        print("Error:", e, file=sys.stderr)
        print("Install acnportal: pip install -e ./acnportal", file=sys.stderr)
        sys.exit(1)

    # --- 3. Require at least one session; exit with clear message if API returned none ---
    if len(day.sessions) == 0:
        print(
            f"No sessions returned for site={args.site} on date={day_date}.",
            file=sys.stderr,
        )
        print(
            "Try another --date (e.g. a date when the site had charging activity).",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Loaded {len(day.sessions)} sessions for {args.site} on {day_date}")

    # --- 4. Build site config (power cap 50 kW) and TOU rates (peak/off-peak) ---
    site = SiteConfig(P_max_kw=50.0, n_steps=day.n_steps, dt_hours=day.dt_hours)
    tou = TOUConfig(rates_per_kwh=default_tou_rates(day.n_steps))

    # --- 5. Run optimizer: minimize TOU cost + penalty for unmet energy ---
    result = solve(day, site, tou)
    if not result.success:
        print("Solver failed:", result.message, file=sys.stderr)
        sys.exit(1)

    # --- 6. Check schedule against constraints (availability, per-charger, site cap, energy) ---
    check_result = check(result.schedule, day, site)

    # --- 7. Uncontrolled baseline (charge-asap) and its cost, for % cost reduction ---
    site_p_max = site.get_P_max_at_step(0) if day.n_steps > 0 else 50.0
    uncontrolled = charge_asap_schedule(day, float(site_p_max))
    uncontrolled_cost = total_cost(uncontrolled, tou, day.dt_hours)
    metrics = compute_metrics(
        result.schedule,
        day,
        tou,
        day.dt_hours,
        violation_count=len(check_result.violations),
        uncontrolled_cost_usd=uncontrolled_cost,
    )

    # --- 8. Print results: feasibility, violations (if any), cost, peak, unmet, % served, % reduction ---
    print("Phase A results")
    print("  Feasible:", check_result.feasible)
    if not check_result.feasible and check_result.violations:
        print(f"  Violations ({len(check_result.violations)}):")
        for v in check_result.violations:
            sid = v.session_id or "(site)"
            ts = v.time_step if v.time_step is not None else "-"
            print(f"    [{v.kind}] session={sid} t={ts}  {v.message}")
        print(f"  (Checker tol={DEFAULT_TOL}; solver uses CVXPY defaults.)")
    print("  Total cost ($):", round(metrics.total_cost_usd, 2))
    print("  Peak load (kW):", round(metrics.peak_load_kw, 2))
    print("  Total unmet (kWh):", round(metrics.total_unmet_kwh, 2))
    print("  % fully served:", round(metrics.pct_fully_served, 1))
    print("  % cost reduction vs uncontrolled:", metrics.cost_reduction_vs_uncontrolled_pct)

    # --- 9. Save schedule heatmap and load profile to experiments/ if directory exists ---
    out_dir = _project_root / "experiments"
    if out_dir.exists():
        plot_schedule(result.schedule, day, save_path=out_dir / "phase_a_schedule.png")
        plot_load_profile(result.schedule, day, save_path=out_dir / "phase_a_load.png")
        print("  Plots saved to experiments/")


if __name__ == "__main__":
    main()

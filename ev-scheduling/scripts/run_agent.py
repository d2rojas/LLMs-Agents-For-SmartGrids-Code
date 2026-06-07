"""Agent integration: load sessions, run agent pipeline, check, compute metrics, plot.

Two modes of operation:

  Natural-language mode (--text):
    Describe the problem in plain English. The agent extracts session details
    and runs the optimizer. No API token required.

    python -m scripts.run_agent --text "I have 2 EVs: EV1 arrives 6pm leaves 10pm needs 20 kWh, EV2 arrives 7pm leaves 11pm needs 15 kWh"

  API mode (--site / --date):
    Load real sessions from the ACN-Data API. Requires ACN_DATA_API_TOKEN in .env.

    python -m scripts.run_agent --site caltech --date 2019-01-15

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


def _print_agent_result(
    result: "AgentResult",
    day: "DaySessions",
    site: "SiteConfig",
    tou: "TOUConfig",
    out_dir: Path,
) -> None:
    """Validate, compute metrics, and print results for an AgentResult."""
    from constraints.checker import DEFAULT_TOL, check
    from evaluation.metrics import charge_asap_schedule, compute_metrics, total_cost
    from visualization.plots import plot_load_profile, plot_schedule

    check_result = check(result.schedule, day, site)

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

    print()
    print("=== Agent results ===")
    print()
    print("Explanation:", result.explanation)
    print()
    print("Feasible:", result.feasible)
    if not check_result.feasible and check_result.violations:
        print(f"Violations ({len(check_result.violations)}):")
        for v in check_result.violations[:10]:
            sid = v.session_id or "(site)"
            ts = v.time_step if v.time_step is not None else "-"
            print(f"  [{v.kind}] session={sid} t={ts}  {v.message}")
        if len(check_result.violations) > 10:
            print(f"  ... and {len(check_result.violations) - 10} more violations")
        print(f"  (Checker tol={DEFAULT_TOL}; solver uses CVXPY defaults.)")
    print("Total cost ($):", round(metrics.total_cost_usd, 2))
    print("Peak load (kW):", round(metrics.peak_load_kw, 2))
    print("Total unmet (kWh):", round(metrics.total_unmet_kwh, 2))
    print("% fully served:", round(metrics.pct_fully_served, 1))
    if metrics.cost_reduction_vs_uncontrolled_pct is not None:
        print("% cost reduction vs uncontrolled:", round(metrics.cost_reduction_vs_uncontrolled_pct, 1))

    if out_dir.exists():
        plot_schedule(result.schedule, day, save_path=out_dir / "agent_schedule.png")
        plot_load_profile(result.schedule, day, save_path=out_dir / "agent_load.png")
        print("Plots saved to experiments/")


def main() -> None:
    # --- 1. Parse CLI ---
    parser = argparse.ArgumentParser(
        description=(
            "Run the EV charging agent. Use --text for natural-language input "
            "or --site/--date to load sessions from the ACN-Data API."
        )
    )
    parser.add_argument(
        "--text",
        default=None,
        metavar="DESCRIPTION",
        help=(
            "Natural-language description of the charging problem. "
            "Example: \"I have 2 EVs: EV1 arrives 6pm leaves 10pm needs 20 kWh, "
            "EV2 arrives 7pm leaves 11pm needs 15 kWh\""
        ),
    )
    parser.add_argument("--site", default="caltech", help="ACN site (caltech, jpl, office001)")
    parser.add_argument("--date", default=None, help="Date YYYY-MM-DD (default: yesterday)")
    parser.add_argument(
        "--request",
        default="Minimize energy cost for this day.",
        help="Natural-language request appended to the agent prompt (API mode only).",
    )
    args = parser.parse_args()

    out_dir = _project_root / "experiments"

    # =========================================================================
    # Branch A: natural-language text input
    # =========================================================================
    if args.text:
        from agent.run import run_agent_from_text, ClarificationResult
        from agent.parse.parse import parse_nl_problem, parsed_problem_to_day_site_tou

        print(f"Parsing problem from text: {args.text!r}")
        print()

        # Run the full pipeline via run_agent_from_text
        result = run_agent_from_text(args.text)

        if isinstance(result, ClarificationResult):
            print("The agent needs more information to optimize:")
            print()
            print(result.message)
            sys.exit(0)

        # Re-parse to get day/site/tou for printing (needed for _print_agent_result)
        parse_result = parse_nl_problem(args.text)
        if parse_result.problem is None:
            print("Error: Could not parse problem.")
            sys.exit(1)
        day, site, tou = parsed_problem_to_day_site_tou(parse_result.problem)

        # Show inference information if applicable
        if parse_result.used_inference:
            print("Note: Context-aware inference was used for missing values:")
            for note in parse_result.inference_notes:
                print(f"  - {note}")
            print()

        print(f"Processing {len(day.sessions)} session(s).")

        _print_agent_result(result, day, site, tou, out_dir)
        return

    # =========================================================================
    # Branch B: ACN-Data API mode
    # =========================================================================
    from agent.run import run_agent
    from config.site import SiteConfig, TOUConfig, default_tou_rates
    from data.loader.loader import load_sessions

    day_date = date.today() - timedelta(days=1) if args.date is None else date.fromisoformat(args.date)

    # --- 2. Load sessions from ACN-Data API ---
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

    site = SiteConfig(P_max_kw=50.0, n_steps=day.n_steps, dt_hours=day.dt_hours)
    tou = TOUConfig(rates_per_kwh=default_tou_rates(day.n_steps))

    result = run_agent(day, site, tou, request=args.request)
    _print_agent_result(result, day, site, tou, out_dir)


if __name__ == "__main__":
    main()

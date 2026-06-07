"""Generate comparison figures from Midway_results/metrics_summary.csv.

Creates bar charts comparing Phase A, Agent, and Baseline across the 5 benchmark
dates for cost, peak load, % served, unmet energy, and violations.

Usage (from project root with venv active):
  python -m scripts.plot_midway_comparison
  python -m scripts.plot_midway_comparison --out-dir Midway_results

Outputs:
  - comparison_cost.png
  - comparison_peak_load.png
  - comparison_pct_served.png
  - comparison_unmet_kwh.png
  - comparison_violations.png
  - comparison_summary.png (2x2 or multi-panel overview)
"""

import argparse
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if _project_root not in sys.path:
    sys.path.insert(0, str(_project_root))

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


# Default output directory and CSV path
DEFAULT_CSV = _project_root / "Midway_results" / "metrics_summary.csv"
DEFAULT_OUT = _project_root / "Midway_results"

# Pipeline display order and colors (Phase A and Agent same color to show they match)
PIPELINES = ["phase_a", "agent", "baseline"]
PIPELINE_LABELS = {"phase_a": "Phase A", "agent": "Agent", "baseline": "Baseline"}
COLORS = {"phase_a": "#2ecc71", "agent": "#2ecc71", "baseline": "#e74c3c"}  # green, green, red


def load_metrics(csv_path: Path) -> pd.DataFrame:
    """Load metrics CSV and ensure date order."""
    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def _bar_plot(
    df: pd.DataFrame,
    metric: str,
    ylabel: str,
    title: str,
    save_path: Path,
    log_scale: bool = False,
) -> None:
    """Grouped bar chart: one group per date, three bars per group (Phase A, Agent, Baseline)."""
    dates = df["date"].drop_duplicates().sort_values()
    dates_str = dates.dt.strftime("%Y-%m-%d").tolist()
    x = np.arange(len(dates_str))
    width = 0.25

    fig, ax = plt.subplots(figsize=(10, 5))
    for i, pipe in enumerate(PIPELINES):
        subset = df[df["pipeline"] == pipe]
        vals = [subset[subset["date"] == d][metric].values[0] if len(subset[subset["date"] == d]) else 0 for d in dates]
        offset = (i - 1) * width
        bars = ax.bar(x + offset, vals, width, label=PIPELINE_LABELS[pipe], color=COLORS[pipe])
        # Optional: show value on bar if not too crowded
        if metric != "violation_count" or max(vals) < 200:
            for b in bars:
                h = b.get_height()
                if h != 0 and (not log_scale or h > 0):
                    ax.annotate(
                        f"{h:.1f}" if isinstance(h, float) and (h >= 10 or h < 1) else f"{int(h)}",
                        xy=(b.get_x() + b.get_width() / 2, h),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha="center",
                        va="bottom",
                        fontsize=7,
                        rotation=0,
                    )

    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_xticks(x)
    ax.set_xticklabels(dates_str, rotation=15)
    ax.legend()
    if log_scale:
        ax.set_yscale("symlog", linthresh=1)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_comparison_figures(csv_path: Path, out_dir: Path) -> None:
    """Generate all comparison figures and save to out_dir."""
    df = load_metrics(csv_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    _bar_plot(
        df,
        "total_cost_usd",
        "Cost (USD)",
        "Total cost by pipeline and date",
        out_dir / "comparison_cost.png",
    )
    _bar_plot(
        df,
        "peak_load_kw",
        "Peak load (kW)",
        "Peak load by pipeline and date",
        out_dir / "comparison_peak_load.png",
    )
    _bar_plot(
        df,
        "pct_fully_served",
        "% fully served",
        "% sessions fully served by pipeline and date",
        out_dir / "comparison_pct_served.png",
    )
    _bar_plot(
        df,
        "total_unmet_kwh",
        "Unmet energy (kWh)",
        "Total unmet energy by pipeline and date",
        out_dir / "comparison_unmet_kwh.png",
        log_scale=True,
    )
    _bar_plot(
        df,
        "violation_count",
        "Violation count",
        "Constraint violations by pipeline and date",
        out_dir / "comparison_violations.png",
    )

    # Summary figure: 2x2 subplots (cost, % served, unmet, violations)
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    dates = df["date"].drop_duplicates().sort_values()
    dates_str = dates.dt.strftime("%Y-%m-%d").tolist()
    x = np.arange(len(dates_str))
    width = 0.25

    metrics_config = [
        ("total_cost_usd", "Cost (USD)", "Cost"),
        ("pct_fully_served", "% fully served", "% Served"),
        ("total_unmet_kwh", "Unmet (kWh)", "Unmet energy"),
        ("violation_count", "Violations", "Violations"),
    ]
    for ax, (metric, ylabel, title) in zip(axes.flat, metrics_config):
        for i, pipe in enumerate(PIPELINES):
            subset = df[df["pipeline"] == pipe]
            vals = [
                subset[subset["date"] == d][metric].values[0]
                if len(subset[subset["date"] == d])
                else 0
                for d in dates
            ]
            offset = (i - 1) * width
            ax.bar(x + offset, vals, width, label=PIPELINE_LABELS[pipe], color=COLORS[pipe])
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels(dates_str, rotation=15)
        ax.legend(fontsize=8)
        ax.grid(axis="y", alpha=0.3)
        if metric == "total_unmet_kwh":
            ax.set_yscale("symlog", linthresh=1)

    fig.suptitle("Midway benchmark: Phase A vs Agent vs Baseline (5 dates)", fontsize=12)
    fig.tight_layout()
    fig.savefig(out_dir / "comparison_summary.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"Saved comparison figures to {out_dir}/")
    for name in [
        "comparison_cost.png",
        "comparison_peak_load.png",
        "comparison_pct_served.png",
        "comparison_unmet_kwh.png",
        "comparison_violations.png",
        "comparison_summary.png",
    ]:
        print(f"  - {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot Phase A / Agent / Baseline comparison from midway CSV")
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help=f"Path to metrics CSV (default: {DEFAULT_CSV})",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output directory for figures (default: {DEFAULT_OUT})",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"Error: CSV not found: {args.csv}", file=sys.stderr)
        print("Run: python -m scripts.run_midway_results", file=sys.stderr)
        sys.exit(1)

    plot_comparison_figures(args.csv, args.out_dir)


if __name__ == "__main__":
    main()

"""Output visualizer: structured result data and optional base64 images for API responses.

This module provides utilities to package agent results into JSON-serializable
formats suitable for web APIs and visualization frontends. It supports:
  - Structured metrics summaries
  - Schedule data as nested lists (for frontend heatmaps)
  - Load profile data (for frontend line charts)
  - Base64-encoded PNG images (optional, for direct embedding)
"""

import base64
import io
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from data.format.schema import DaySessions


@dataclass
class SessionSummary:
    """Summary of one charging session for display.

    Attributes:
        session_id: Session identifier.
        arrival_idx: First time step available for charging.
        departure_idx: First time step not available.
        energy_kwh: Requested energy.
        delivered_kwh: Energy actually delivered by the schedule.
        max_power_kw: Per-session power limit.
        fully_served: True if delivered >= requested (within tolerance).
    """

    session_id: str
    arrival_idx: int
    departure_idx: int
    energy_kwh: float
    delivered_kwh: float
    max_power_kw: float
    fully_served: bool


@dataclass
class VisualizationData:
    """Structured data for frontend visualization of agent results.

    Attributes:
        metrics: Dict of key metrics (cost, peak, unmet, pct_served, etc.).
        sessions: List of SessionSummary dicts.
        schedule: 2D list (n_sessions x n_steps) of power values in kW.
        load_profile: 1D list (n_steps) of total load per time step.
        time_labels: Human-readable time labels for x-axis (e.g., "00:00", "00:15").
        explanation: Natural-language explanation from the agent.
        schedule_image_b64: Optional base64-encoded PNG of schedule heatmap.
        load_image_b64: Optional base64-encoded PNG of load profile.
    """

    metrics: Dict[str, Any]
    sessions: List[Dict[str, Any]]
    schedule: List[List[float]]
    load_profile: List[float]
    time_labels: List[str]
    explanation: str
    schedule_image_b64: Optional[str] = None
    load_image_b64: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dict."""
        return asdict(self)


def _time_label(step: int, dt_hours: float) -> str:
    """Convert a step index to a time label like '14:30'."""
    total_minutes = int(step * dt_hours * 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"


def _figure_to_base64(fig: Any) -> str:
    """Convert a matplotlib Figure to a base64-encoded PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def build_visualization_data(
    schedule: np.ndarray,
    day: DaySessions,
    total_cost_usd: float,
    peak_load_kw: float,
    unmet_energy_kwh: float,
    pct_fully_served: float,
    explanation: str,
    *,
    cost_reduction_pct: Optional[float] = None,
    feasible: bool = True,
    violation_count: int = 0,
    include_images: bool = False,
) -> VisualizationData:
    """Build a VisualizationData object from agent results.

    Args:
        schedule: Power schedule array of shape (n_sessions, n_steps) in kW.
        day: DaySessions with session metadata.
        total_cost_usd: Total energy cost.
        peak_load_kw: Maximum total power draw.
        unmet_energy_kwh: Total unmet energy.
        pct_fully_served: Percentage of sessions fully served.
        explanation: LLM-generated explanation.
        cost_reduction_pct: Optional cost reduction vs. uncontrolled baseline.
        feasible: Whether the schedule is constraint-feasible.
        violation_count: Number of constraint violations.
        include_images: If True, generate base64 PNG images.

    Returns:
        VisualizationData ready for JSON serialization.
    """
    n_sessions = len(day.sessions)
    n_steps = day.n_steps
    dt_hours = day.dt_hours

    if schedule.size == 0:
        schedule_2d = np.zeros((n_sessions, n_steps))
    else:
        schedule_2d = schedule

    metrics: Dict[str, Any] = {
        "total_cost_usd": round(total_cost_usd, 2),
        "peak_load_kw": round(peak_load_kw, 2),
        "unmet_energy_kwh": round(unmet_energy_kwh, 2),
        "pct_fully_served": round(pct_fully_served, 1),
        "feasible": feasible,
        "violation_count": violation_count,
        "n_sessions": n_sessions,
        "n_steps": n_steps,
    }
    if cost_reduction_pct is not None:
        metrics["cost_reduction_pct"] = round(cost_reduction_pct, 1)

    sessions_summary: List[Dict[str, Any]] = []
    for i, sess in enumerate(day.sessions):
        if i < schedule_2d.shape[0]:
            delivered = float(np.sum(schedule_2d[i, :]) * dt_hours)
        else:
            delivered = 0.0
        fully_served = delivered >= sess.energy_kwh - 0.01

        sessions_summary.append(asdict(SessionSummary(
            session_id=sess.session_id,
            arrival_idx=sess.arrival_idx,
            departure_idx=sess.departure_idx,
            energy_kwh=sess.energy_kwh,
            delivered_kwh=round(delivered, 2),
            max_power_kw=sess.max_power_kw,
            fully_served=fully_served,
        )))

    schedule_list = schedule_2d.tolist()
    load_profile = np.sum(schedule_2d, axis=0).tolist()
    time_labels = [_time_label(t, dt_hours) for t in range(n_steps)]

    schedule_image_b64: Optional[str] = None
    load_image_b64: Optional[str] = None

    if include_images:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            # Session labels for y-axis
            session_labels = [s.session_id for s in day.sessions]

            # Time labels for x-axis (every 2 hours = 8 steps at 15-min resolution)
            steps_per_hour = int(1 / dt_hours)
            hour_ticks = list(range(0, n_steps, steps_per_hour * 2))
            hour_labels = [f"{int(t * dt_hours)}:00" for t in hour_ticks]

            # Schedule heatmap
            fig_schedule, ax_schedule = plt.subplots(figsize=(12, max(3, n_sessions * 0.5 + 1)))
            if schedule_2d.size > 0 and n_sessions > 0:
                im = ax_schedule.imshow(
                    schedule_2d,
                    aspect="auto",
                    interpolation="nearest",
                    cmap="YlOrRd",
                )
                cbar = fig_schedule.colorbar(im, ax=ax_schedule)
                cbar.set_label("Power (kW)")

                # Set proper y-axis labels (session IDs)
                ax_schedule.set_yticks(range(n_sessions))
                ax_schedule.set_yticklabels(session_labels)

                # Set x-axis to show time of day
                ax_schedule.set_xticks(hour_ticks)
                ax_schedule.set_xticklabels(hour_labels)

            ax_schedule.set_xlabel("Time of Day")
            ax_schedule.set_ylabel("Session")
            ax_schedule.set_title("Charging Schedule (Power Allocation)")
            fig_schedule.tight_layout()
            schedule_image_b64 = _figure_to_base64(fig_schedule)
            plt.close(fig_schedule)

            # Load profile chart
            fig_load, ax_load = plt.subplots(figsize=(12, 4))
            time_hours = [t * dt_hours for t in range(n_steps)]
            ax_load.fill_between(time_hours, load_profile, alpha=0.4, color='steelblue')
            ax_load.plot(time_hours, load_profile, linewidth=2, color='steelblue')
            ax_load.set_xlabel("Time of Day (hours)")
            ax_load.set_ylabel("Total Load (kW)")
            ax_load.set_title("Aggregate Facility Load Profile")
            ax_load.set_xlim(0, 24)
            ax_load.set_ylim(bottom=0)
            ax_load.set_xticks(range(0, 25, 2))
            ax_load.set_xticklabels([f"{h}:00" for h in range(0, 25, 2)])
            ax_load.grid(True, alpha=0.3)
            fig_load.tight_layout()
            load_image_b64 = _figure_to_base64(fig_load)
            plt.close(fig_load)

        except ImportError:
            pass

    return VisualizationData(
        metrics=metrics,
        sessions=sessions_summary,
        schedule=schedule_list,
        load_profile=load_profile,
        time_labels=time_labels,
        explanation=explanation,
        schedule_image_b64=schedule_image_b64,
        load_image_b64=load_image_b64,
    )

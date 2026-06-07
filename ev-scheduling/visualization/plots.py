"""Schedule and load profile visualization for reports."""

from pathlib import Path
from typing import Optional

import numpy as np

from data.format.schema import DaySessions


def plot_schedule(
    schedule: np.ndarray,
    day: DaySessions,
    save_path: Optional[Path] = None,
) -> None:
    """Plot schedule matrix: sessions (rows) vs time (columns), color = power (kW).

    If save_path is set, save figure to file (e.g. PNG).
    """
    import matplotlib.pyplot as plt

    # Empty schedule: still create a minimal figure so caller can save if desired
    if schedule.size == 0:
        fig, ax = plt.subplots()
        ax.set_xlabel("Time step")
        ax.set_ylabel("Session")
        if save_path is not None:
            fig.savefig(save_path)
        plt.close(fig)
        return

    # 2D heatmap: rows = session index, columns = time step, color = power (kW)
    fig, ax = plt.subplots()
    im = ax.imshow(
        schedule,
        aspect="auto",
        interpolation="nearest",
        cmap="viridis",
    )
    ax.set_xlabel("Time step")
    ax.set_ylabel("Session")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Power (kW)")
    if save_path is not None:
        fig.savefig(save_path)
    plt.close(fig)


def plot_load_profile(
    schedule: np.ndarray,
    day: DaySessions,
    save_path: Optional[Path] = None,
    title: Optional[str] = None,
) -> None:
    """Plot facility load sum_i p_i(t) vs time; optionally annotate with cost/unmet in title."""
    import matplotlib.pyplot as plt

    # Total power at each time step (sum over all sessions)
    if schedule.size == 0:
        load_per_t = np.zeros(day.n_steps)
    else:
        load_per_t = np.sum(schedule, axis=0)

    fig, ax = plt.subplots()
    ax.plot(np.arange(len(load_per_t)), load_per_t)
    ax.set_xlabel("Time step")
    ax.set_ylabel("Total load (kW)")
    if title is not None:
        ax.set_title(title)
    if save_path is not None:
        fig.savefig(save_path)
    plt.close(fig)

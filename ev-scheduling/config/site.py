"""Site and experiment configuration: power cap, time step, TOU rates.

This module defines site-level constraints (power cap, horizon) and time-of-use (TOU)
energy rates used by the optimizer, constraint checker, baseline, and evaluation.
All time is in discrete steps; step 0 corresponds to midnight (00:00) by convention.
"""

from dataclasses import dataclass
from typing import Union

import numpy as np


@dataclass
class SiteConfig:
    """Site-level constraints for one day.

    Encapsulates the facility power cap (possibly time-varying), the number of time
    steps in the horizon, and the step duration. Used by the constraint checker and
    optimizer to enforce sum_i p_i(t) <= P_max(t) at each step t.

    Attributes:
        P_max_kw: Site power cap (kW). Either a scalar (constant for all steps) or
            an array of length n_steps for a time-varying cap.
        n_steps: Number of time steps in the horizon (indices 0 .. n_steps-1).
        dt_hours: Duration of each time step in hours (e.g. 0.25 for 15 minutes).

    Assumptions:
        If P_max_kw is an array, its length must equal n_steps.
    """

    P_max_kw: Union[float, np.ndarray]
    n_steps: int
    dt_hours: float = 0.25

    def get_P_max_at_step(self, t: int) -> float:
        """Return the site power cap at time step t (kW).

        Supports both a constant cap (scalar P_max_kw) and a per-step cap (array).
        Callers should ensure 0 <= t < n_steps when P_max_kw is an array.

        Args:
            t: Time step index in [0, n_steps).

        Returns:
            Power cap in kW at step t.

        Verifications:
            If P_max_kw is an array, indexing with t is not bounds-checked here;
            out-of-range t may raise IndexError.
        """
        if np.isscalar(self.P_max_kw):
            return float(self.P_max_kw)
        return float(self.P_max_kw[t])


@dataclass
class TOUConfig:
    """Time-of-use (TOU) energy rates ($/kWh) per time step.

    Holds the cost vector c(t) used in the objective: minimize sum_t c(t) * power_t * dt.
    The solver and evaluation metrics use this to compute total energy cost.

    Attributes:
        rates_per_kwh: 1D array of length n_steps; element t is the energy cost
            in $/kWh for time step t.

    Assumptions:
        rates_per_kwh length matches the horizon n_steps used by sessions and site.
    """

    rates_per_kwh: np.ndarray

    @property
    def n_steps(self) -> int:
        """Number of time steps in the rate vector.

        Returns:
            len(rates_per_kwh). Must match SiteConfig.n_steps and day horizon.
        """
        return len(self.rates_per_kwh)


def default_tou_rates(
    n_steps: int,
    peak_price: float = 0.45,
    off_peak_price: float = 0.12,
) -> np.ndarray:
    """Build a TOU rate vector with a single peak window (e.g. 4pm–9pm).

    Returns an array of length n_steps where steps in the peak window get peak_price
    and all other steps get off_peak_price. Used to construct TOUConfig for experiments
    when no custom rate file is provided.

    Args:
        n_steps: Number of time steps in the horizon (e.g. 96 for 24h at 15-min resolution).
        peak_price: Energy rate in $/kWh during peak hours. Default 0.45.
        off_peak_price: Energy rate in $/kWh outside peak. Default 0.12.

    Returns:
        1D numpy array of shape (n_steps,) with dtype float; each element is $/kWh
        for that step.

    Assumptions:
        Step 0 corresponds to midnight (00:00). Day is 24 hours; steps_per_hour
        is n_steps // 24. Peak window is 4pm–9pm (steps 16*steps_per_hour through
        21*steps_per_hour, exclusive end). If n_steps is not divisible by 24,
        steps_per_hour is truncated; peak indices are clamped to [0, n_steps).
    """
    steps_per_hour = n_steps // 24
    peak_start_step = int(16 * steps_per_hour)  # 4pm
    peak_end_step = int(21 * steps_per_hour)    # 9pm (exclusive)

    rates = np.full(n_steps, off_peak_price, dtype=float)
    for t in range(peak_start_step, min(peak_end_step, n_steps)):
        rates[t] = peak_price
    return rates

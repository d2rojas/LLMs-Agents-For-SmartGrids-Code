"""Evaluation metrics: cost, unmet energy, peak load, violations, % fully served."""

from dataclasses import dataclass
from typing import Optional

import numpy as np

from config.site import TOUConfig
from data.format.schema import DaySessions


@dataclass
class Metrics:
    """Aggregate metrics for one schedule."""

    total_cost_usd: float
    total_unmet_kwh: float
    peak_load_kw: float
    violation_count: int
    pct_fully_served: float  # 0–100
    cost_reduction_vs_uncontrolled_pct: Optional[float] = None


def total_cost(
    schedule: np.ndarray,
    tou: TOUConfig,
    dt_hours: float,
) -> float:
    """Total energy cost ($): sum_t c(t) * sum_i p_i(t) * dt."""
    if schedule.size == 0:
        return 0.0
    # c[t] = $/kWh at step t; total power at t = sum over sessions; cost at t = c[t] * power_t * dt
    c = np.asarray(tou.rates_per_kwh).flatten()
    n_steps = min(schedule.shape[1], len(c))
    return float(np.sum(c[:n_steps] * np.sum(schedule[:, :n_steps], axis=0) * dt_hours))


def total_unmet_kwh(schedule: np.ndarray, day: DaySessions, dt_hours: float) -> float:
    """Sum over sessions of (E_i - delivered_i). Only positive unmet counts."""
    if len(day.sessions) == 0:
        return 0.0
    total = 0.0
    for i, sess in enumerate(day.sessions):
        if i >= schedule.shape[0]:
            total += sess.energy_kwh  # no row for this session => full unmet
            continue
        delivered = np.sum(schedule[i, :]) * dt_hours  # kWh = sum_t p[i,t] * dt
        total += max(0.0, sess.energy_kwh - delivered)
    return total


def peak_load_kw(schedule: np.ndarray) -> float:
    """Peak facility load (kW): max over time of (sum of power over all sessions)."""
    if schedule.size == 0:
        return 0.0
    # Sum over axis=0 gives total power at each time step; max over those
    return float(np.max(np.sum(schedule, axis=0)))


def pct_fully_served(schedule: np.ndarray, day: DaySessions, dt_hours: float) -> float:
    """Percentage of sessions that received at least their requested energy (0–100)."""
    if len(day.sessions) == 0:
        return 0.0
    tol = 1e-6  # small tolerance for numerical comparison
    count = 0
    for i, sess in enumerate(day.sessions):
        if i >= schedule.shape[0]:
            continue
        delivered = np.sum(schedule[i, :]) * dt_hours
        if delivered >= sess.energy_kwh - tol:
            count += 1
    return 100.0 * count / len(day.sessions)


def charge_asap_schedule(day: DaySessions, site_p_max: float) -> np.ndarray:
    """Uncontrolled baseline: each session charges at max rate from arrival until E_i met.
    Used to compute cost and peak for 'charge-asap' so we can report % cost reduction.
    """
    n_sessions = len(day.sessions)
    n_steps = day.n_steps
    dt = day.dt_hours
    schedule = np.zeros((n_sessions, n_steps))
    for i, sess in enumerate(day.sessions):
        remaining = sess.energy_kwh
        # Charge at max rate in each step until requested energy is reached
        for t in range(sess.arrival_idx, min(sess.departure_idx, n_steps)):
            if remaining <= 0:
                break
            power = min(sess.max_power_kw, remaining / dt)  # cap by remaining energy in this step
            schedule[i, t] = power
            remaining -= power * dt
    return schedule


def compute_metrics(
    schedule: np.ndarray,
    day: DaySessions,
    tou: TOUConfig,
    dt_hours: float,
    violation_count: int = 0,
    uncontrolled_cost_usd: Optional[float] = None,
) -> Metrics:
    """Compute all metrics; set cost_reduction_vs_uncontrolled_pct if uncontrolled_cost_usd given."""
    total_cost_usd = total_cost(schedule, tou, dt_hours)
    total_unmet = total_unmet_kwh(schedule, day, dt_hours)
    peak = peak_load_kw(schedule)
    pct = pct_fully_served(schedule, day, dt_hours)

    # Optional: % reduction vs uncontrolled (charge-asap) baseline
    cost_reduction_pct = None
    if uncontrolled_cost_usd is not None and uncontrolled_cost_usd > 0:
        cost_reduction_pct = 100.0 * (uncontrolled_cost_usd - total_cost_usd) / uncontrolled_cost_usd

    return Metrics(
        total_cost_usd=total_cost_usd,
        total_unmet_kwh=total_unmet,
        peak_load_kw=peak,
        violation_count=violation_count,
        pct_fully_served=pct,
        cost_reduction_vs_uncontrolled_pct=cost_reduction_pct,
    )

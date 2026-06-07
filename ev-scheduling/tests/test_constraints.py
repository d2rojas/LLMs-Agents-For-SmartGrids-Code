"""Unit tests for constraint checker: feasible schedule, and one violation per constraint type."""

import numpy as np
import pytest

from config.site import SiteConfig
from constraints.checker import check, CheckResult, Violation
from data.format.schema import DaySessions, Session


def test_check_feasible_schedule() -> None:
    """One schedule that satisfies all constraints; assert result.feasible and no violations."""
    # Two sessions, n_steps=8, dt=0.25. Session 0: [0,4), 4 kWh, max 4 kW → 4 kW for 4 steps = 4 kWh.
    # Session 1: [2,6), 4 kWh, max 4 kW → 4 kW for 4 steps = 4 kWh. Peak sum at t in [2,4) = 8 kW.
    sessions = [
        Session("s1", arrival_idx=0, departure_idx=4, energy_kwh=4.0, charger_id="c1", max_power_kw=4.0),
        Session("s2", arrival_idx=2, departure_idx=6, energy_kwh=4.0, charger_id="c2", max_power_kw=4.0),
    ]
    day = DaySessions(sessions=sessions, n_steps=8, dt_hours=0.25)
    schedule = np.zeros((2, 8))
    schedule[0, 0:4] = 4.0
    schedule[1, 2:6] = 4.0
    site = SiteConfig(P_max_kw=10.0, n_steps=8, dt_hours=0.25)

    result = check(schedule, day, site)

    assert result.feasible is True
    assert len(result.violations) == 0
    assert np.all(result.unmet_energy_kwh >= 0)


def test_check_availability_violation() -> None:
    """Schedule with non-zero power outside [arrival, departure); assert violation kind 'availability'."""
    sessions = [
        Session("s1", arrival_idx=2, departure_idx=6, energy_kwh=5.0, charger_id="c1", max_power_kw=7.0),
    ]
    day = DaySessions(sessions=sessions, n_steps=8, dt_hours=0.25)
    schedule = np.zeros((1, 8))
    schedule[0, 2:6] = 5.0
    schedule[0, 0] = 1.0  # power outside window
    site = SiteConfig(P_max_kw=20.0, n_steps=8, dt_hours=0.25)

    result = check(schedule, day, site)

    assert result.feasible is False
    assert any(v.kind == "availability" for v in result.violations)


def test_check_per_charger_violation() -> None:
    """Schedule with p_i(t) > max_power_kw or negative; assert violation kind 'per_charger'."""
    sessions = [
        Session("s1", arrival_idx=0, departure_idx=4, energy_kwh=10.0, charger_id="c1", max_power_kw=7.0),
    ]
    day = DaySessions(sessions=sessions, n_steps=8, dt_hours=0.25)
    schedule = np.zeros((1, 8))
    schedule[0, 1] = 8.0  # exceeds max_power_kw=7
    site = SiteConfig(P_max_kw=20.0, n_steps=8, dt_hours=0.25)

    result = check(schedule, day, site)

    assert result.feasible is False
    assert any(v.kind == "per_charger" for v in result.violations)


def test_check_site_cap_violation() -> None:
    """Schedule where sum_i p_i(t) > P_max at some t; assert violation kind 'site_cap'."""
    sessions = [
        Session("s1", arrival_idx=0, departure_idx=4, energy_kwh=5.0, charger_id="c1", max_power_kw=5.0),
        Session("s2", arrival_idx=0, departure_idx=4, energy_kwh=5.0, charger_id="c2", max_power_kw=5.0),
    ]
    day = DaySessions(sessions=sessions, n_steps=8, dt_hours=0.25)
    schedule = np.zeros((2, 8))
    schedule[0, 0:4] = 5.0
    schedule[1, 0:4] = 5.0  # sum = 10 at t in [0,4); P_max = 8
    site = SiteConfig(P_max_kw=8.0, n_steps=8, dt_hours=0.25)

    result = check(schedule, day, site)

    assert result.feasible is False
    assert any(v.kind == "site_cap" for v in result.violations)


def test_check_energy_violation() -> None:
    """Schedule that over-delivers or under-delivers (unmet); assert violation or unmet set correctly."""
    sessions = [
        Session("s1", arrival_idx=0, departure_idx=4, energy_kwh=10.0, charger_id="c1", max_power_kw=7.0),
    ]
    day = DaySessions(sessions=sessions, n_steps=8, dt_hours=0.25)
    schedule = np.zeros((1, 8))  # delivers 0 kWh → under-delivered
    site = SiteConfig(P_max_kw=20.0, n_steps=8, dt_hours=0.25)

    result = check(schedule, day, site)

    assert result.feasible is False
    assert result.unmet_energy_kwh[0] > 0
    assert any(v.kind == "energy" for v in result.violations)

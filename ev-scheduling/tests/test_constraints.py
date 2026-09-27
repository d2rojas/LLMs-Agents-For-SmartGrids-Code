"""Unit tests for the constraint checker and FR.

Covers the original per-kind violations, the hard/soft split, the numeric
magnitude on each violation, and ``evaluation.metrics.feasible_rate`` (FR), which
is derived from the same CheckResult objects.
"""

import numpy as np
import pytest

from config.site import SiteConfig
from solver.checker import (
    HARD_VIOLATION_KINDS,
    SOFT_VIOLATION_KINDS,
    CheckResult,
    Violation,
    check,
    hard_violations,
    is_hard_violation,
    max_violation_kw,
)
from data.format.schema import DaySessions, Session
from evaluation.metrics import feasible_rate


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
    assert result.no_hard_violation is True
    assert result.max_violation_kw == 0.0


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
    availability = [v for v in result.violations if v.kind == "availability"]
    assert availability
    # The whole 1 kW is charged where 0 kW is allowed.
    assert availability[0].magnitude == pytest.approx(1.0)
    assert result.no_hard_violation is False


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
    per_charger = [v for v in result.violations if v.kind == "per_charger"]
    assert per_charger
    assert per_charger[0].magnitude == pytest.approx(1.0)  # 8 kW against a 7 kW charger


def test_check_negative_power_magnitude() -> None:
    """Negative power is a per_charger violation whose magnitude is how far below zero it is."""
    sessions = [
        Session("s1", arrival_idx=0, departure_idx=4, energy_kwh=4.0, charger_id="c1", max_power_kw=7.0),
    ]
    day = DaySessions(sessions=sessions, n_steps=8, dt_hours=0.25)
    schedule = np.zeros((1, 8))
    schedule[0, 0] = -2.5
    site = SiteConfig(P_max_kw=20.0, n_steps=8, dt_hours=0.25)

    result = check(schedule, day, site)

    negative = [v for v in result.violations if v.kind == "per_charger"]
    assert negative
    assert negative[0].magnitude == pytest.approx(2.5)
    assert result.max_violation_kw == pytest.approx(2.5)


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
    site_cap = [v for v in result.violations if v.kind == "site_cap"]
    assert site_cap
    assert site_cap[0].magnitude == pytest.approx(2.0)  # 10 kW against an 8 kW cap
    assert result.max_violation_kw == pytest.approx(2.0)


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
    energy = [v for v in result.violations if v.kind == "energy"]
    assert energy
    assert energy[0].magnitude == pytest.approx(10.0)  # kWh still owed


def test_energy_is_soft_and_does_not_break_feasibility_in_the_hard_sense() -> None:
    """A schedule that under-delivers but breaks no hard constraint: feasible False, no hard violation."""
    sessions = [
        Session("s1", arrival_idx=0, departure_idx=4, energy_kwh=10.0, charger_id="c1", max_power_kw=7.0),
    ]
    day = DaySessions(sessions=sessions, n_steps=8, dt_hours=0.25)
    schedule = np.zeros((1, 8))
    schedule[0, 0:4] = 4.0  # 4 kW * 4 * 0.25 h = 4 kWh delivered of 10 kWh requested
    site = SiteConfig(P_max_kw=20.0, n_steps=8, dt_hours=0.25)

    result = check(schedule, day, site)

    # The original meaning of `feasible` is preserved: any violation makes it False.
    assert result.feasible is False
    assert result.no_hard_violation is True  # the FR term counts this day as feasible
    assert result.n_hard_violations == 0
    assert result.max_violation_kw == 0.0
    assert result.total_unmet_kwh == pytest.approx(6.0)


def test_max_violation_kw_ignores_energy_magnitudes() -> None:
    """kWh magnitudes must never leak into the kW figure, even when much larger."""
    sessions = [
        Session("s1", arrival_idx=0, departure_idx=4, energy_kwh=500.0, charger_id="c1", max_power_kw=5.0),
        Session("s2", arrival_idx=0, departure_idx=4, energy_kwh=500.0, charger_id="c2", max_power_kw=5.0),
    ]
    day = DaySessions(sessions=sessions, n_steps=8, dt_hours=0.25)
    schedule = np.zeros((2, 8))
    schedule[0, 0:4] = 5.0
    schedule[1, 0:4] = 5.0  # site cap exceeded by 2 kW; ~495 kWh unmet per session
    site = SiteConfig(P_max_kw=8.0, n_steps=8, dt_hours=0.25)

    result = check(schedule, day, site)

    assert result.total_unmet_kwh > 900.0
    assert result.max_violation_kw == pytest.approx(2.0)


def test_hard_violation_helpers() -> None:
    """is_hard_violation / hard_violations / max_violation_kw agree on the kind split."""
    hard = [
        Violation(kind="availability", session_id="s1", time_step=0, message="", magnitude=1.0),
        Violation(kind="per_charger", session_id="s1", time_step=1, message="", magnitude=3.0),
        Violation(kind="site_cap", session_id=None, time_step=2, message="", magnitude=2.0),
    ]
    soft = [Violation(kind="energy", session_id="s1", time_step=None, message="", magnitude=99.0)]

    assert {v.kind for v in hard} == HARD_VIOLATION_KINDS
    assert {v.kind for v in soft} == SOFT_VIOLATION_KINDS
    assert all(is_hard_violation(v) for v in hard)
    assert not any(is_hard_violation(v) for v in soft)
    assert hard_violations(hard + soft) == hard
    assert max_violation_kw(hard + soft) == pytest.approx(3.0)
    assert max_violation_kw(soft) == 0.0


def test_check_day_with_zero_sessions() -> None:
    """A day with no sessions is vacuously valid: no violations, zero peak."""
    day = DaySessions(sessions=[], n_steps=8, dt_hours=0.25)
    schedule = np.zeros((0, 8))
    site = SiteConfig(P_max_kw=10.0, n_steps=8, dt_hours=0.25)

    result = check(schedule, day, site)

    assert result.feasible is True
    assert result.violations == []
    assert result.peak_load_kw == 0.0
    assert result.no_hard_violation is True
    assert result.total_unmet_kwh == 0.0


def test_check_single_step_window() -> None:
    """A session available for exactly one step: charging inside it is valid, one step later is not."""
    sessions = [
        Session("s1", arrival_idx=3, departure_idx=4, energy_kwh=1.0, charger_id="c1", max_power_kw=7.0),
    ]
    day = DaySessions(sessions=sessions, n_steps=8, dt_hours=0.25)
    site = SiteConfig(P_max_kw=20.0, n_steps=8, dt_hours=0.25)

    inside = np.zeros((1, 8))
    inside[0, 3] = 4.0  # 4 kW * 0.25 h = 1.0 kWh, exactly the request
    ok = check(inside, day, site)
    assert ok.feasible is True
    assert ok.no_hard_violation is True

    outside = np.zeros((1, 8))
    outside[0, 4] = 4.0  # one step after departure
    bad = check(outside, day, site)
    assert bad.no_hard_violation is False
    assert [v.kind for v in bad.violations if v.kind == "availability"] == ["availability"]
    # Pinned, not endorsed: the checker's energy accumulator sums power over the whole
    # horizon, so energy delivered outside the window still counts as delivered and the
    # session reads as fully served. The day is already hard-infeasible, so the unmet
    # figure for it is moot, but a future change of that accumulator must break this test
    # rather than move the Unmet column quietly.
    assert bad.unmet_energy_kwh[0] == pytest.approx(0.0)
    assert bad.max_violation_kw == pytest.approx(4.0)


def test_feasible_rate_over_days() -> None:
    """FR is the share of days with no hard violation; under-delivery does not count against it."""
    sessions = [
        Session("s1", arrival_idx=0, departure_idx=4, energy_kwh=4.0, charger_id="c1", max_power_kw=4.0),
    ]
    day = DaySessions(sessions=sessions, n_steps=8, dt_hours=0.25)
    site = SiteConfig(P_max_kw=10.0, n_steps=8, dt_hours=0.25)

    served = np.zeros((1, 8))
    served[0, 0:4] = 4.0
    under = np.zeros((1, 8))  # delivers nothing: soft violation only
    over_cap = np.zeros((1, 8))
    over_cap[0, 0] = 12.0  # above both the charger limit and the site cap

    results = [check(served, day, site), check(under, day, site), check(over_cap, day, site)]

    fr = feasible_rate(results)
    assert fr["total"] == 3
    assert fr["count"] == 2
    assert fr["rate"] == pytest.approx(2.0 / 3.0)
    # Same answer from plain booleans, so a harness may store the flag instead of the object.
    assert feasible_rate([r.no_hard_violation for r in results])["rate"] == pytest.approx(2.0 / 3.0)
    assert feasible_rate([])["rate"] is None

"""Tests for data loader: API path (when ACN_DATA_API_TOKEN is set) and raw_session_to_standard."""

import os
from datetime import date, datetime, time, timezone

import pytest

from data.format.schema import DaySessions, Session
from data.loader.loader import load_sessions, raw_session_to_standard


@pytest.fixture
def sample_day_sessions() -> DaySessions:
    """Hand-built DaySessions for tests that need data without calling the API."""
    sessions = [
        Session(
            "s1",
            arrival_idx=0,
            departure_idx=4,
            energy_kwh=10.0,
            charger_id="c1",
            max_power_kw=7.0,
        ),
        Session(
            "s2",
            arrival_idx=2,
            departure_idx=6,
            energy_kwh=5.0,
            charger_id="c2",
            max_power_kw=7.0,
        ),
    ]
    return DaySessions(sessions=sessions, n_steps=8, dt_hours=0.25)


def test_raw_session_to_standard() -> None:
    """raw_session_to_standard maps ACN-Data keys to Session with correct step indices."""
    day_start = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    # 8:00 UTC = 8h from midnight UTC -> step 8*4 = 32 at 15-min resolution
    # 12:00 UTC = step 48
    raw = {
        "sessionID": "test-123",
        "spaceID": "PS-001",
        "connectionTime": "Mon, 15 Jan 2024 08:00:00 GMT",
        "disconnectTime": "Mon, 15 Jan 2024 12:00:00 GMT",
        "kWhDelivered": 14.5,
    }
    s = raw_session_to_standard(raw, day_start_utc=day_start, dt_hours=0.25, n_steps=96)
    assert s.session_id == "test-123"
    assert s.charger_id == "PS-001"
    assert s.energy_kwh == 14.5
    assert 30 <= s.arrival_idx <= 34
    assert 46 <= s.departure_idx <= 50
    assert s.arrival_idx < s.departure_idx
    assert s.max_power_kw > 0


def test_load_sessions_with_api_returns_day_sessions() -> None:
    """When ACN_DATA_API_TOKEN is set, load_sessions returns DaySessions from the API."""
    if not os.environ.get("ACN_DATA_API_TOKEN", "").strip():
        pytest.skip("ACN_DATA_API_TOKEN not set; load .env or set token to run API test")
    day = load_sessions(
        site_id="caltech",
        day_date=date(2019, 5, 1),
        n_steps=96,
        dt_hours=0.25,
    )
    assert isinstance(day, DaySessions)
    assert day.n_steps == 96
    assert day.dt_hours == 0.25
    for s in day.sessions:
        assert 0 <= s.arrival_idx < s.departure_idx <= day.n_steps
        assert s.energy_kwh > 0
        assert s.max_power_kw > 0

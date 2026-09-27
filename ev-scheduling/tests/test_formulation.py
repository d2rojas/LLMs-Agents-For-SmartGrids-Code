"""Unit tests for evaluation.formulation: per-session extraction correctness.

Offline: no API key, no LLM call. ParsedSession / ParsedProblem are used as data
shapes only; ``methods/agent/parse/parse.py`` imports openai lazily inside its functions.
"""

import pytest

from methods.agent.parse.parse import ParsedProblem, ParsedSession
from data.format.schema import DaySessions, Session
from evaluation.formulation import (
    FORMULATION_ERROR_TYPES,
    formulation_error_counts,
    formulation_exact,
    formulation_exact_rate,
)

DT = 0.25


def _truth() -> DaySessions:
    """Two sessions: EV-1 9:00–17:00 / 15 kWh, EV-2 10:00–18:00 / 20 kWh, both 7 kW."""
    return DaySessions(
        sessions=[
            Session("EV-1", arrival_idx=36, departure_idx=68, energy_kwh=15.0, charger_id="c1", max_power_kw=7.0),
            Session("EV-2", arrival_idx=40, departure_idx=72, energy_kwh=20.0, charger_id="c2", max_power_kw=7.0),
        ],
        n_steps=96,
        dt_hours=DT,
    )


def _parsed(*sessions: ParsedSession) -> ParsedProblem:
    return ParsedProblem(sessions=list(sessions), n_steps=96, dt_hours=DT)


def test_exact_extraction() -> None:
    """Hours that convert to the ground-truth step indices, with exact magnitudes."""
    parsed = _parsed(
        ParsedSession(9.0, 17.0, 15.0, 7.0, "EV-1", "c1"),
        ParsedSession(10.0, 18.0, 20.0, 7.0, "EV-2", "c2"),
    )

    result = formulation_exact(parsed, _truth())

    assert result.formulation_exact is True
    assert result.formulation_error_type == "ok"
    assert result.n_truth == 2 and result.n_parsed == 2
    assert result.n_sessions_exact == 2
    assert result.matched_by == "session_id"
    assert all(f.exact for s in result.sessions for f in s.fields)


def test_energy_within_one_percent_is_exact_beyond_it_is_wrong_field() -> None:
    """1 % relative tolerance on energy_kwh, and nothing looser."""
    inside = _parsed(
        ParsedSession(9.0, 17.0, 15.1, 7.0, "EV-1", "c1"),   # +0.67 %
        ParsedSession(10.0, 18.0, 20.0, 7.0, "EV-2", "c2"),
    )
    outside = _parsed(
        ParsedSession(9.0, 17.0, 15.3, 7.0, "EV-1", "c1"),   # +2.0 %
        ParsedSession(10.0, 18.0, 20.0, 7.0, "EV-2", "c2"),
    )

    assert formulation_exact(inside, _truth()).formulation_exact is True

    bad = formulation_exact(outside, _truth())
    assert bad.formulation_exact is False
    assert bad.formulation_error_type == "wrong_field"
    assert bad.n_sessions_exact == 1
    wrong = [f for s in bad.sessions for f in s.fields if not f.exact]
    assert [f.name for f in wrong] == ["energy_kwh"]


def test_max_power_tolerance() -> None:
    """The same 1 % rule applies to max_power_kw."""
    parsed = _parsed(
        ParsedSession(9.0, 17.0, 15.0, 7.05, "EV-1", "c1"),   # +0.7 %
        ParsedSession(10.0, 18.0, 20.0, 7.5, "EV-2", "c2"),   # +7.1 %
    )

    result = formulation_exact(parsed, _truth())

    assert result.formulation_exact is False
    assert result.sessions[0].exact is True
    assert result.sessions[1].error_type == "wrong_field"


def test_step_indices_are_compared_exactly() -> None:
    """A window off by one step is a different problem: no tolerance on the indices."""
    parsed = _parsed(
        ParsedSession(9.25, 17.0, 15.0, 7.0, "EV-1", "c1"),  # idx 37 instead of 36
        ParsedSession(10.0, 18.0, 20.0, 7.0, "EV-2", "c2"),
    )

    result = formulation_exact(parsed, _truth())

    assert result.formulation_exact is False
    assert result.formulation_error_type == "wrong_field"
    field = next(f for s in result.sessions for f in s.fields if f.name == "arrival_idx" and not f.exact)
    assert field.parsed_value == 37 and field.truth_value == 36


def test_missing_field_is_not_exact() -> None:
    """A field the model never extracted (None) is a wrong field, not a pass."""
    parsed = _parsed(
        ParsedSession(9.0, 17.0, None, 7.0, "EV-1", "c1"),
        ParsedSession(10.0, 18.0, 20.0, 7.0, "EV-2", "c2"),
    )

    result = formulation_exact(parsed, _truth())

    assert result.formulation_exact is False
    field = next(f for s in result.sessions for f in s.fields if f.name == "energy_kwh")
    assert field.exact is False and field.parsed_value is None


def test_omitted_session() -> None:
    """A ground-truth session with no extracted counterpart."""
    parsed = _parsed(ParsedSession(9.0, 17.0, 15.0, 7.0, "EV-1", "c1"))

    result = formulation_exact(parsed, _truth())

    assert result.formulation_exact is False
    assert result.formulation_error_type == "omitted_session"
    omitted = [s for s in result.sessions if s.error_type == "omitted_session"]
    assert [s.session_id for s in omitted] == ["EV-2"]
    assert result.n_parsed == 1 and result.n_truth == 2


def test_extra_session() -> None:
    """An extracted session the request never described."""
    parsed = _parsed(
        ParsedSession(9.0, 17.0, 15.0, 7.0, "EV-1", "c1"),
        ParsedSession(10.0, 18.0, 20.0, 7.0, "EV-2", "c2"),
        ParsedSession(11.0, 19.0, 10.0, 7.0, "EV-3", "c3"),
    )

    result = formulation_exact(parsed, _truth())

    assert result.formulation_exact is False
    assert result.formulation_error_type == "extra_session"
    assert [s.session_id for s in result.sessions if s.error_type == "extra_session"] == ["EV-3"]


def test_omitted_outranks_extra_at_day_level() -> None:
    """When a day has both, the day-level type is the first in the priority order."""
    parsed = _parsed(
        ParsedSession(9.0, 17.0, 15.0, 7.0, "EV-1", "c1"),
        ParsedSession(11.0, 19.0, 10.0, 7.0, "EV-9", "c9"),
    )

    result = formulation_exact(parsed, _truth())

    types = {s.error_type for s in result.sessions}
    assert "omitted_session" in types and "extra_session" in types
    assert result.formulation_error_type == "omitted_session"


def test_wrong_unit_energy_and_power() -> None:
    """Wh quoted as kWh (and W as kW) is diagnosed as a unit error, not a plain wrong field."""
    parsed = _parsed(
        ParsedSession(9.0, 17.0, 15000.0, 7.0, "EV-1", "c1"),
        ParsedSession(10.0, 18.0, 20.0, 7000.0, "EV-2", "c2"),
    )

    result = formulation_exact(parsed, _truth())

    assert result.formulation_exact is False
    assert result.formulation_error_type == "wrong_unit"
    assert [s.error_type for s in result.sessions] == ["wrong_unit", "wrong_unit"]


def test_wrong_unit_time_in_minutes() -> None:
    """An arrival given in minutes from midnight is a unit error, not an arbitrary index."""
    parsed = _parsed(
        ParsedSession(540.0, 17.0, 15.0, 7.0, "EV-1", "c1"),  # 540 minutes = 9:00
        ParsedSession(10.0, 18.0, 20.0, 7.0, "EV-2", "c2"),
    )

    result = formulation_exact(parsed, _truth())

    field = next(f for f in result.sessions[0].fields if f.name == "arrival_idx")
    assert field.exact is False
    assert field.error_type == "wrong_unit"
    assert result.formulation_error_type == "wrong_unit"


def test_day_with_zero_sessions_is_exact() -> None:
    """Nothing to extract on either side: exact, and no error type."""
    truth = DaySessions(sessions=[], n_steps=96, dt_hours=DT)

    result = formulation_exact(_parsed(), truth)

    assert result.formulation_exact is True
    assert result.formulation_error_type == "ok"
    assert result.n_truth == 0 and result.n_parsed == 0
    assert result.sessions == []
    assert "no sessions on either side" in result.detail


def test_sessions_invented_on_an_empty_day() -> None:
    """Extracting a car from a day that had none is an extra session, not a pass."""
    truth = DaySessions(sessions=[], n_steps=96, dt_hours=DT)

    result = formulation_exact(_parsed(ParsedSession(9.0, 17.0, 15.0, 7.0, "EV-1", "c1")), truth)

    assert result.formulation_exact is False
    assert result.formulation_error_type == "extra_session"


def test_single_step_window() -> None:
    """A session available for one step only converts to [36, 37) and compares exactly."""
    truth = DaySessions(
        sessions=[Session("EV-1", arrival_idx=36, departure_idx=37, energy_kwh=1.75, charger_id="c1", max_power_kw=7.0)],
        n_steps=96,
        dt_hours=DT,
    )

    ok = formulation_exact(_parsed(ParsedSession(9.0, 9.25, 1.75, 7.0, "EV-1", "c1")), truth)
    assert ok.formulation_exact is True

    # Half an hour instead of fifteen minutes is a different window.
    bad = formulation_exact(_parsed(ParsedSession(9.0, 9.5, 1.75, 7.0, "EV-1", "c1")), truth)
    assert bad.formulation_exact is False
    assert bad.formulation_error_type == "wrong_field"


def test_reordered_sessions_match_by_id() -> None:
    """Extraction order does not matter when the ids line up."""
    parsed = _parsed(
        ParsedSession(10.0, 18.0, 20.0, 7.0, "EV-2", "c2"),
        ParsedSession(9.0, 17.0, 15.0, 7.0, "EV-1", "c1"),
    )

    result = formulation_exact(parsed, _truth())

    assert result.matched_by == "session_id"
    assert result.formulation_exact is True


def test_unrelated_ids_fall_back_to_position() -> None:
    """With no shared ids the two sides are paired in order, as the request enumerates them."""
    truth = DaySessions(
        sessions=[
            Session("2-39-21", arrival_idx=36, departure_idx=68, energy_kwh=15.0, charger_id="CA-301", max_power_kw=7.0),
            Session("2-39-22", arrival_idx=40, departure_idx=72, energy_kwh=20.0, charger_id="CA-302", max_power_kw=7.0),
        ],
        n_steps=96,
        dt_hours=DT,
    )
    parsed = _parsed(
        ParsedSession(9.0, 17.0, 15.0, 7.0, "EV-1", "c1"),
        ParsedSession(10.0, 18.0, 20.0, 7.0, "EV-2", "c2"),
    )

    result = formulation_exact(parsed, truth)

    assert result.matched_by == "position"
    assert result.formulation_exact is True


def test_dt_hours_override() -> None:
    """The hour-to-index conversion follows dt_hours, not a hard-coded resolution."""
    truth = DaySessions(
        sessions=[Session("EV-1", arrival_idx=9, departure_idx=17, energy_kwh=15.0, charger_id="c1", max_power_kw=7.0)],
        n_steps=24,
        dt_hours=1.0,
    )
    parsed = ParsedProblem(sessions=[ParsedSession(9.0, 17.0, 15.0, 7.0, "EV-1", "c1")], n_steps=24, dt_hours=1.0)

    assert formulation_exact(parsed, truth).formulation_exact is True
    # Reading the same hours at 15-minute resolution gives indices 36 and 68 instead.
    assert formulation_exact(parsed, truth, dt_hours=0.25).formulation_exact is False


def test_rate_and_error_counts() -> None:
    """Aggregates over days: the Form. column and the supplement's error breakdown."""
    good = formulation_exact(
        _parsed(
            ParsedSession(9.0, 17.0, 15.0, 7.0, "EV-1", "c1"),
            ParsedSession(10.0, 18.0, 20.0, 7.0, "EV-2", "c2"),
        ),
        _truth(),
    )
    omitted = formulation_exact(_parsed(ParsedSession(9.0, 17.0, 15.0, 7.0, "EV-1", "c1")), _truth())

    agg = formulation_exact_rate([good, good, omitted])
    assert agg == {"rate": pytest.approx(2.0 / 3.0), "count": 2, "total": 3}

    counts = formulation_error_counts([good, good, omitted])
    assert counts["ok"] == 2 and counts["omitted_session"] == 1
    assert set(counts) >= set(FORMULATION_ERROR_TYPES)

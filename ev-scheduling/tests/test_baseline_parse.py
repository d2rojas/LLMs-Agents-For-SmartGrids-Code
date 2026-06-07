"""Tests for baseline.parse — including resampling of wrong-length LLM output."""

import numpy as np
import pytest

from data.format.schema import DaySessions, Session
from baseline.parse import ParseResult, _resample_to_n_steps, parse_llm_schedule


# ---------------------------------------------------------------------------
# _resample_to_n_steps unit tests
# ---------------------------------------------------------------------------

def test_resample_exact_divisor() -> None:
    """24 values resampled to 96 by repeating each value 4 times."""
    values = list(range(24))
    result = _resample_to_n_steps(values, 96)
    assert result is not None
    assert len(result) == 96
    # Each value repeated 4 times
    for i, v in enumerate(values):
        assert result[i * 4 : i * 4 + 4] == [v] * 4


def test_resample_exact_match_is_identity() -> None:
    """Exactly 96 values returns the same list."""
    values = [float(i) for i in range(96)]
    result = _resample_to_n_steps(values, 96)
    assert result == values


def test_resample_close_too_long_truncates() -> None:
    """97 values for n_steps=96 → truncate to 96."""
    values = list(range(97))
    result = _resample_to_n_steps(values, 96)
    assert result is not None
    assert len(result) == 96
    assert result == list(range(96))


def test_resample_close_too_short_pads() -> None:
    """94 values for n_steps=96 → pad with last value."""
    values = list(range(94))
    result = _resample_to_n_steps(values, 96)
    assert result is not None
    assert len(result) == 96
    # 94 values padded by 2: last 3 slots are all the last original value (93)
    assert result[-1] == 93
    assert result[-2] == 93
    assert result[-3] == 93
    # The value before the pad region is the second-to-last original value (92)
    assert result[-4] == 92


def test_resample_far_off_returns_none() -> None:
    """10 values for n_steps=96 — not a divisor and far off — returns None."""
    result = _resample_to_n_steps(list(range(10)), 96)
    assert result is None


def test_resample_48_to_96() -> None:
    """48 values resampled to 96 by repeating each value twice."""
    values = [float(i) for i in range(48)]
    result = _resample_to_n_steps(values, 96)
    assert result is not None
    assert len(result) == 96
    for i, v in enumerate(values):
        assert result[i * 2 : i * 2 + 2] == [v, v]


# ---------------------------------------------------------------------------
# parse_llm_schedule integration tests with resampling
# ---------------------------------------------------------------------------

def _make_day(n_sessions: int = 3, n_steps: int = 96) -> DaySessions:
    sessions = [
        Session(
            session_id=str(i),
            arrival_idx=0,
            departure_idx=n_steps,
            energy_kwh=7.0,
            charger_id=f"c{i}",
            max_power_kw=7.0,
        )
        for i in range(n_sessions)
    ]
    return DaySessions(sessions=sessions, n_steps=n_steps, dt_hours=0.25)


def test_parse_24_values_resampled_to_96() -> None:
    """LLM outputs 24 values per session; parser resamples to 96 (success)."""
    day = _make_day(n_sessions=2, n_steps=96)
    # 24 values: power 7.0 for steps 0-7 (representing hours 0-7), zero otherwise
    vals_s0 = " ".join(["7.0"] * 8 + ["0.0"] * 16)
    vals_s1 = " ".join(["3.5"] * 24)
    response = f"Session 0: {vals_s0}\nSession 1: {vals_s1}\n"

    result = parse_llm_schedule(response, day)
    assert result.success is True
    assert result.schedule.shape == (2, 96)
    # Session 0: each of the first 8 values (7.0) repeated 4x = 32 steps of 7.0
    assert np.all(result.schedule[0, :32] == pytest.approx(7.0))
    assert np.all(result.schedule[0, 32:] == pytest.approx(0.0))
    # Session 1: all 3.5
    assert np.all(result.schedule[1, :] == pytest.approx(3.5))


def test_parse_97_values_truncated_to_96() -> None:
    """LLM outputs 97 values per session; parser truncates to 96 (success)."""
    day = _make_day(n_sessions=1, n_steps=96)
    vals = " ".join(["1.0"] * 97)
    response = f"Session 0: {vals}\n"

    result = parse_llm_schedule(response, day)
    assert result.success is True
    assert result.schedule.shape == (1, 96)
    assert np.all(result.schedule[0, :] == pytest.approx(1.0))


def test_parse_94_values_padded_to_96() -> None:
    """LLM outputs 94 values; parser pads with last value to 96 (success)."""
    day = _make_day(n_sessions=1, n_steps=96)
    vals = " ".join(["2.0"] * 93 + ["5.0"])
    response = f"Session 0: {vals}\n"

    result = parse_llm_schedule(response, day)
    assert result.success is True
    assert result.schedule.shape == (1, 96)
    assert result.schedule[0, 95] == pytest.approx(5.0)
    assert result.schedule[0, 94] == pytest.approx(5.0)


def test_parse_irrecoverable_length_skipped() -> None:
    """LLM outputs 10 values (not a divisor and far off) — session skipped, parse_failed."""
    day = _make_day(n_sessions=1, n_steps=96)
    vals = " ".join(["1.0"] * 10)
    response = f"Session 0: {vals}\n"

    result = parse_llm_schedule(response, day)
    # Session should be skipped, so schedule stays all zeros
    assert result.success is False
    assert np.all(result.schedule == 0.0)


def test_parse_mixed_good_and_resampled() -> None:
    """Session 0 has exact 96 values; session 1 has 24 (resampled). Both parsed."""
    day = _make_day(n_sessions=2, n_steps=96)
    vals_exact = " ".join(["4.0"] * 96)
    vals_24 = " ".join(["2.0"] * 24)
    response = f"Session 0: {vals_exact}\nSession 1: {vals_24}\n"

    result = parse_llm_schedule(response, day)
    assert result.success is True
    assert np.all(result.schedule[0, :] == pytest.approx(4.0))
    assert np.all(result.schedule[1, :] == pytest.approx(2.0))

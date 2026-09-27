"""Tests for methods.prompting.parse: row labels, resampling, and the repair log.

The repair tests are the ones that matter for the paper's fairness claim: the
baseline's output must be scored as written, and anything the parser has to
change must be counted rather than applied silently.
"""

import numpy as np
import pytest

from data.format.schema import DaySessions, Session
from methods.prompting.parse import (
    REPAIR_KINDS,
    ParseResult,
    RepairLog,
    _resample_to_n_steps,
    _split_concatenated_run,
    parse_llm_schedule,
)


# ---------------------------------------------------------------------------
# _resample_to_n_steps unit tests
# ---------------------------------------------------------------------------

def test_resample_exact_divisor() -> None:
    """24 values resampled to 96 by repeating each value 4 times."""
    values = list(range(24))
    result = _resample_to_n_steps(values, 96)
    assert result is not None
    result = result.values
    assert len(result) == 96
    # Each value repeated 4 times
    for i, v in enumerate(values):
        assert result[i * 4 : i * 4 + 4] == [v] * 4


def test_resample_exact_match_is_identity() -> None:
    """Exactly 96 values returns the same list and records no repair."""
    values = [float(i) for i in range(96)]
    result = _resample_to_n_steps(values, 96)
    assert result is not None
    assert result.values == values
    assert result.kind == ""


def test_resample_close_too_long_truncates() -> None:
    """97 values for n_steps=96 → truncate to 96."""
    values = list(range(97))
    result = _resample_to_n_steps(values, 96)
    assert result is not None
    result = result.values
    assert len(result) == 96
    assert result == list(range(96))


def test_resample_close_too_short_pads() -> None:
    """94 values for n_steps=96 → pad with last value."""
    values = list(range(94))
    result = _resample_to_n_steps(values, 96)
    assert result is not None
    result = result.values
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
    result = result.values
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


# ---------------------------------------------------------------------------
# Several cars written behind one label
# ---------------------------------------------------------------------------

def test_split_helper_returns_none_for_one_row() -> None:
    """A row of exactly n_steps, or short of two of them, is not a run."""
    assert _split_concatenated_run([1.0] * 96, 96) is None
    assert _split_concatenated_run([1.0] * 97, 96) is None
    assert _split_concatenated_run([1.0] * 191, 96) is None


def test_split_helper_cuts_at_the_horizon() -> None:
    """192 values are two rows of 96, with nothing left over."""
    run = _split_concatenated_run([float(i) for i in range(192)], 96)
    assert run is not None
    assert len(run.rows) == 2
    assert run.rows[0] == [float(i) for i in range(96)]
    assert run.rows[1] == [float(i) for i in range(96, 192)]
    assert run.leftover == []


def test_split_run_goes_to_consecutive_cars_from_the_label() -> None:
    """One 'EV 2:' label carrying two cars fills EV 2 and EV 3, not EV 2 alone."""
    day = _make_day(n_sessions=3, n_steps=4)
    response = "EV 2: 1.0 1.0 1.0 1.0 2.0 2.0 2.0 2.0\n"

    result = parse_llm_schedule(response, day)
    assert result.success is True
    assert np.all(result.schedule[0, :] == 0.0)
    assert np.all(result.schedule[1, :] == pytest.approx(1.0))
    assert np.all(result.schedule[2, :] == pytest.approx(2.0))
    counts = result.repairs.counts()
    assert counts["split_row"] == 2
    assert counts["missing_row"] == 1


def test_one_line_for_every_car_is_the_defect_that_was_scored_as_zero() -> None:
    """The 2018-09-17 shape: one 'EV 1:' label, 34 cars' rows, then a cut-off row.

    gpt-4o-mini answered an 87-car day on a single line and its output stopped
    mid-row at the token cap. The whole reply used to resample to nothing, so the
    arm was scored on an all-zero schedule: no cost, no violation, every session
    missing. The rows the model did write are now read, and the fact that it
    ignored a format the prompt stated twice stays on the record as 34
    ``split_row`` repairs.
    """
    n_steps = 96
    n_written_rows = 34
    n_cut_off = 12
    day = _make_day(n_sessions=87, n_steps=n_steps)
    values = []
    for row in range(n_written_rows):
        values += [float(row)] * n_steps
    values += [99.0] * n_cut_off  # the row the output cap interrupted
    response = "EV 1: " + " ".join(f"{v:.4f}" for v in values) + "\n"
    assert len(values) == 3276

    result = parse_llm_schedule(response, day)

    assert result.success is True
    assert result.error_message is None
    counts = result.repairs.counts()
    assert counts["split_row"] == n_written_rows
    assert counts["missing_row"] == 87 - n_written_rows
    # Every complete row landed on its own car, in the order it was written.
    for row in range(n_written_rows):
        assert np.all(result.schedule[row, :] == pytest.approx(float(row)))
    # The interrupted row is not scored, and says why it is missing.
    assert np.all(result.schedule[n_written_rows, :] == 0.0)
    cut = [
        e for e in result.repairs.events
        if e.kind == "missing_row" and e.session_index == n_written_rows
    ]
    assert len(cut) == 1
    assert f"{n_cut_off} of {n_steps}" in cut[0].detail
    # Cars the model never reached are plain missing rows.
    assert np.all(result.schedule[n_written_rows + 1 :, :] == 0.0)
    # What the fix is for: the day is no longer an empty schedule.
    assert result.schedule.sum() > 0.0


def test_trailing_partial_run_is_never_resampled_into_a_row() -> None:
    """A cut-off row is a fragment, not a coarse answer, so it charges nothing.

    12 values on their own would be a ``repeated_row`` stretched over the
    horizon. After a run of full rows we know the model was writing n_steps per
    car, so stretching the fragment would invent charging it never wrote.
    """
    day = _make_day(n_sessions=3, n_steps=96)
    values = [1.0] * 96 + [2.0] * 96 + [3.0] * 12
    response = "EV 1: " + " ".join(str(v) for v in values) + "\n"

    result = parse_llm_schedule(response, day)
    assert result.success is True
    counts = result.repairs.counts()
    assert counts["split_row"] == 2
    assert counts["repeated_row"] == 0
    assert counts["missing_row"] == 1
    assert np.all(result.schedule[2, :] == 0.0)


def test_split_run_past_the_last_car_is_reported_not_wrapped() -> None:
    """Rows beyond the last session are dropped and fail the parse, as a bad label does."""
    day = _make_day(n_sessions=2, n_steps=4)
    response = "EV 1: 1.0 1.0 1.0 1.0 2.0 2.0 2.0 2.0 3.0 3.0 3.0 3.0\n"

    result = parse_llm_schedule(response, day)
    assert result.success is False
    assert "past session 1" in (result.error_message or "")
    assert np.all(result.schedule[0, :] == pytest.approx(1.0))
    assert np.all(result.schedule[1, :] == pytest.approx(2.0))
    assert result.repairs.counts()["split_row"] == 2


def test_a_single_full_row_still_parses_exactly_as_before() -> None:
    """The ordinary case is untouched: 96 values for one car, no repair at all."""
    day = _make_day(n_sessions=1, n_steps=96)
    response = "EV 1: " + " ".join(["7.0"] * 96) + "\n"

    result = parse_llm_schedule(response, day)
    assert result.success is True
    assert np.all(result.schedule[0, :] == pytest.approx(7.0))
    assert result.repairs.changed is False
    assert result.repairs.counts()["split_row"] == 0


def test_unlabeled_numeric_blob_is_not_split() -> None:
    """Without a label there is no car to start from, so the run stays one row.

    Splitting here would guess the cut points and the placement at once. The
    fallback's existing positional reading applies, and says so.
    """
    day = _make_day(n_sessions=3, n_steps=96)
    response = " ".join(["1.0"] * 192) + "\n"

    result = parse_llm_schedule(response, day)
    counts = result.repairs.counts()
    assert counts["split_row"] == 0
    assert counts["unlabeled_row"] == 1


def test_split_rows_keep_their_own_cells_scored() -> None:
    """Negatives and NaNs inside a split run are counted against the right car."""
    day = _make_day(n_sessions=2, n_steps=4)
    response = "EV 1: 1.0 -2.0 1.0 1.0 3.0 nan 3.0 3.0\n"

    result = parse_llm_schedule(response, day)
    assert result.success is True
    assert result.schedule[0, 1] == pytest.approx(-2.0)
    assert result.repairs.negative_cells == 1
    assert result.schedule[1, 1] == pytest.approx(0.0)
    nonfinite = [e for e in result.repairs.events if e.kind == "nonfinite_cell"]
    assert len(nonfinite) == 1
    assert nonfinite[0].session_index == 1


# ---------------------------------------------------------------------------
# Row labels
# ---------------------------------------------------------------------------

def test_parse_ev_labels_are_one_based() -> None:
    """'EV 1:' is session 0 — the request text names the cars EV 1..N."""
    day = _make_day(n_sessions=2, n_steps=4)
    response = "EV 1: 1.0 1.0 1.0 1.0\nEV 2: 2.0 2.0 2.0 2.0\n"

    result = parse_llm_schedule(response, day)
    assert result.success is True
    assert np.all(result.schedule[0, :] == pytest.approx(1.0))
    assert np.all(result.schedule[1, :] == pytest.approx(2.0))
    assert result.repairs.changed is False


def test_parse_session_labels_are_still_zero_based() -> None:
    """The older 'Session i:' format keeps its zero-based meaning."""
    day = _make_day(n_sessions=2, n_steps=4)
    response = "Session 0: 1.0 1.0 1.0 1.0\nSession 1: 2.0 2.0 2.0 2.0\n"

    result = parse_llm_schedule(response, day)
    assert result.success is True
    assert np.all(result.schedule[0, :] == pytest.approx(1.0))
    assert np.all(result.schedule[1, :] == pytest.approx(2.0))


def test_parse_ignores_prose_mentioning_a_car() -> None:
    """A reasoning sentence about EV 1 is not read as a schedule row."""
    day = _make_day(n_sessions=1, n_steps=4)
    response = (
        "EV 1: needs 12.5 kWh by 6 pm.\n"
        "EV 1 total: 7.0\n"
        "EV 1: 1.0 2.0 3.0 4.0\n"
    )

    result = parse_llm_schedule(response, day)
    assert result.success is True
    assert result.schedule[0, :].tolist() == pytest.approx([1.0, 2.0, 3.0, 4.0])


# ---------------------------------------------------------------------------
# The repair log — negatives are scored, not erased
# ---------------------------------------------------------------------------

def test_negative_power_survives_to_the_checker() -> None:
    """A negative charger power is kept verbatim and counted, never clamped.

    This is the comparability rule: the no-tools arm is scored on what it
    produced, exactly as the solver-grounded arm is.
    """
    day = _make_day(n_sessions=1, n_steps=4)
    response = "EV 1: 1.0 -3.5 2.0 -0.5\n"

    result = parse_llm_schedule(response, day)
    assert result.success is True
    assert result.schedule[0, 1] == pytest.approx(-3.5)
    assert result.schedule[0, 3] == pytest.approx(-0.5)
    assert result.repairs.negative_cells == 2
    # A preserved violation is not a repair: nothing about the row changed.
    assert result.repairs.changed is False
    assert result.repairs.n_cells_changed == 0


def test_negative_power_is_a_violation_the_checker_sees() -> None:
    """The parsed schedule fails the constraint checker instead of passing it.

    Under the old silent clamp this schedule reached the checker as all-zeros in
    that cell and raised no per_charger violation at all.
    """
    from config.site import SiteConfig
    from solver.checker import check

    day = _make_day(n_sessions=1, n_steps=4)
    site = SiteConfig(P_max_kw=50.0, n_steps=4, dt_hours=0.25)
    result = parse_llm_schedule("EV 1: 1.0 -3.5 2.0 0.0\n", day)

    report = check(result.schedule, day, site)
    assert report.no_hard_violation is False
    assert any(v.kind == "per_charger" for v in report.violations)


def test_nonfinite_is_neutralised_and_counted() -> None:
    """NaN cannot be scored, so it becomes 0.0 — but it is recorded, not silent."""
    day = _make_day(n_sessions=1, n_steps=4)
    response = "EV 1: 1.0 nan 2.0 inf\n"

    result = parse_llm_schedule(response, day)
    assert np.all(np.isfinite(result.schedule))
    assert result.schedule[0, 1] == pytest.approx(0.0)
    assert result.schedule[0, 3] == pytest.approx(0.0)
    assert result.repairs.changed is True
    assert result.repairs.n_cells_changed == 2
    assert result.repairs.counts()["nonfinite_cell"] == 2


def test_shape_repairs_are_recorded_by_kind() -> None:
    """Repeated, truncated and padded rows each show up under their own kind."""
    day = _make_day(n_sessions=3, n_steps=96)
    repeated = " ".join(["1.0"] * 24)
    truncated = " ".join(["2.0"] * 97)
    padded = " ".join(["3.0"] * 94)
    response = f"EV 1: {repeated}\nEV 2: {truncated}\nEV 3: {padded}\n"

    result = parse_llm_schedule(response, day)
    assert result.success is True
    counts = result.repairs.counts()
    assert counts["repeated_row"] == 1
    assert counts["truncated_row"] == 1
    assert counts["padded_row"] == 1
    assert result.repairs.n_rows_changed == 3


def test_missing_row_is_recorded() -> None:
    """A session that got no row is zeros, and that is reported."""
    day = _make_day(n_sessions=2, n_steps=4)
    response = "EV 1: 1.0 1.0 1.0 1.0\n"

    result = parse_llm_schedule(response, day)
    assert np.all(result.schedule[1, :] == 0.0)
    assert result.repairs.counts()["missing_row"] == 1
    assert result.repairs.changed is True


def test_unlabeled_rows_are_recorded() -> None:
    """A bare numeric matrix is mapped by position, and every row says so."""
    day = _make_day(n_sessions=2, n_steps=4)
    response = "1.0 1.0 1.0 1.0\n2.0 2.0 2.0 2.0\n"

    result = parse_llm_schedule(response, day)
    assert result.success is True
    assert result.repairs.counts()["unlabeled_row"] == 2


def test_clean_reply_reports_no_repair() -> None:
    """The case the table needs as its denominator: nothing was fixed."""
    day = _make_day(n_sessions=2, n_steps=4)
    response = "EV 1: 0.0 1.0 1.0 0.0\nEV 2: 0.0 0.0 2.0 2.0\n"

    result = parse_llm_schedule(response, day)
    assert result.success is True
    assert result.repairs.changed is False
    assert result.repairs.negative_cells == 0
    assert result.repairs.to_dict()["changed"] is False


def test_repair_log_to_dict_covers_every_kind() -> None:
    """to_dict is what a report reads; every kind is present as a key."""
    day = _make_day(n_sessions=1, n_steps=4)
    result = parse_llm_schedule("EV 1: 1.0 nan 2.0 3.0\n", day)

    payload = result.repairs.to_dict()
    for kind in REPAIR_KINDS:
        assert kind in payload
    assert payload["n_cells_changed"] == 1
    assert len(payload["events"]) == 1


def test_default_parse_result_has_an_empty_log() -> None:
    """ParseResult stays constructible the way baseline/run.py builds it."""
    day = _make_day(n_sessions=1, n_steps=4)
    result = ParseResult(schedule=np.zeros((1, 4)), success=True, error_message=None)
    assert isinstance(result.repairs, RepairLog)
    assert result.repairs.changed is False
    assert parse_llm_schedule("", day).success is False

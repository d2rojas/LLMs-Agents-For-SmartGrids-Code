"""Parse LLM response text into schedule array (n_sessions x n_steps) in kW.

Why this module counts what it changes
--------------------------------------
The solver-grounded arm's schedule comes out of CVXPY and needs no repair. The
no-tools arm's schedule comes out of a text reply and used to be repaired on the
way in, silently: ``_sanitize`` replaced every non-finite value with 0 and
clamped every negative value to 0, and ``_resample_to_n_steps`` repeated or
truncated rows of the wrong length. Its docstring gave the reason as preventing
numpy warnings in the metrics, which is a housekeeping reason for something with
a scoring consequence. A baseline that answered "-3.5 kW at step 40" had that
per-charger violation erased before ``constraints/checker.py`` could see it, so
the two arms were not scored on comparable objects: one was scored on what it
produced, the other on a cleaned-up version of what it produced.

What happens now, and why each case is treated the way it is:

- **Negative power is no longer clamped.** It is a finite number, the checker can
  score it, and it is exactly the violation the comparison exists to measure.
  It is passed through verbatim and counted in ``RepairLog.negative_cells``.
- **Non-finite values (NaN, infinity) are counted and replaced with 0.0.** These
  are not numbers and no metric can be computed from a day that contains one:
  left in place a single NaN turns the whole day's cost and peak into NaN, which
  scores the arm as missing rather than as wrong. Each one is recorded as a
  ``nonfinite_cell`` event, so a day that needed this is visible rather than
  indistinguishable from a day that charged nothing at that step.
- **Shape repairs are kept and counted.** A row of the wrong length is still
  repeated, truncated, padded or interpolated, because a model that answered at
  hourly resolution did answer; but every such row is recorded as a
  ``repeated_row``, ``truncated_row``, ``padded_row`` or ``interpolated_row``
  event. A row that carried no label and was mapped by position is an
  ``unlabeled_row``, and a session for which no row arrived at all is a
  ``missing_row``.
- **Several cars written behind one label are split apart, and counted.** A
  model asked for one row per car sometimes emits a single ``EV 1:`` followed by
  many cars' worth of numbers on one line. The values are there and they are in
  car order, so they are cut into consecutive rows of ``n_steps`` and given to
  consecutive cars starting at the labelled one; each row taken this way is a
  ``split_row``. Reading the run as one unusable row scored the model's whole
  answer as an empty schedule, which overstates the failure; reading it silently
  would hide a format the prompt stated twice. The trailing values after the
  last complete row are the row the model was still writing when its output
  stopped, so they are not scored: that car keeps the existing ``missing_row``,
  with the cut-off length in its detail.

So nothing is repaired silently. ``ParseResult.repairs`` carries the whole log,
``RepairLog.changed`` says whether the parsed schedule differs from what the
model literally wrote, and a harness can report how often the baseline's output
had to be fixed before it could be scored at all. That rate is itself a finding
about no-tools generation, and it used to be invisible.

Accepted row labels
-------------------
``EV 1:`` ... ``EV n:`` (one-based, the names the request text uses) and
``Session 0:`` ... ``Session i:`` (zero-based, the older format). Both map to the
same rows: the text's ``EV k`` is ``day.sessions[k - 1]``.
"""

from dataclasses import dataclass, field
from typing import Dict, List, NamedTuple, Optional, Tuple

import numpy as np

from data.format.schema import DaySessions


# Repair kinds, i.e. events where the parsed schedule differs from the text the
# model wrote. A negative value is NOT one of these: it is passed through and
# counted separately, because it is a violation to be scored, not a defect to be
# fixed.
REPAIR_KINDS: Tuple[str, ...] = (
    "nonfinite_cell",
    "repeated_row",
    "truncated_row",
    "padded_row",
    "interpolated_row",
    "split_row",
    "unlabeled_row",
    "missing_row",
)


@dataclass(frozen=True)
class RepairEvent:
    """One recorded difference between the model's text and the parsed schedule.

    Attributes:
        kind: One of ``REPAIR_KINDS``.
        session_index: Row the event belongs to, or -1 when it belongs to none.
        count: Cells affected for a cell-level kind, 1 for a row-level kind.
        detail: Short human-readable note, for the trace and the report.
    """

    kind: str
    session_index: int
    count: int = 1
    detail: str = ""


@dataclass(frozen=True)
class RepairLog:
    """Everything the parser had to do to the model's output to make it scorable.

    Attributes:
        events: The repairs, in the order they happened.
        negative_cells: Number of negative power values found. These are kept
            verbatim so the constraint checker sees the violation; the count is
            here so a report can state how often the baseline emitted one.
    """

    events: Tuple[RepairEvent, ...] = ()
    negative_cells: int = 0

    @property
    def changed(self) -> bool:
        """Whether the parsed schedule differs from what the model wrote."""
        return bool(self.events)

    @property
    def n_cells_changed(self) -> int:
        """Cells whose value the parser changed (non-finite substitutions)."""
        return sum(e.count for e in self.events if e.kind == "nonfinite_cell")

    @property
    def n_rows_changed(self) -> int:
        """Rows whose shape or placement the parser had to fix."""
        return sum(1 for e in self.events if e.kind != "nonfinite_cell")

    def counts(self) -> Dict[str, int]:
        """Count per repair kind, every kind present as a key (zero when unused)."""
        out = {kind: 0 for kind in REPAIR_KINDS}
        for event in self.events:
            out[event.kind] = out.get(event.kind, 0) + (
                event.count if event.kind == "nonfinite_cell" else 1
            )
        return out

    def to_dict(self) -> Dict[str, object]:
        """JSON-ready summary for a run trace or a results table."""
        summary: Dict[str, object] = {
            "changed": self.changed,
            "negative_cells": self.negative_cells,
            "n_cells_changed": self.n_cells_changed,
            "n_rows_changed": self.n_rows_changed,
        }
        summary.update(self.counts())
        summary["events"] = [
            {
                "kind": e.kind,
                "session_index": e.session_index,
                "count": e.count,
                "detail": e.detail,
            }
            for e in self.events
        ]
        return summary


@dataclass
class ParseResult:
    """Result of parsing LLM output.

    Attributes:
        schedule: Power schedule of shape (n_sessions, n_steps) in kW.
        success: True when the reply parsed into a schedule. Independent of
            ``repairs``: a reply can parse successfully and still have needed
            repair, which is precisely the case the log exists to surface.
        error_message: Why parsing failed, if it did.
        repairs: Everything the parser changed, and the count of negative values
            it deliberately did not change.
    """

    schedule: np.ndarray  # (n_sessions, n_steps)
    success: bool
    error_message: Optional[str] = None
    repairs: RepairLog = field(default_factory=RepairLog)


# Fraction of n_steps a "close" parse is allowed to deviate before we try interpolation.
# e.g. 0.25 means ±24 values for n_steps=96 — so we accept 72–120 via truncate/pad.
_CLOSE_THRESHOLD = 0.25

# Shortest row we will treat as a schedule. A single number after a label is a
# sentence, not a schedule, and repeating it across the horizon would invent one.
_MIN_ROW_VALUES = 2

# Shortest labelled run, in whole horizons, that we read as several cars' rows
# written end to end. Two cars' worth is the shortest run that can be one.
# Anything below it stays a single row, so a row of exactly n_steps is untouched
# and a row that merely overshoots by a few values is still a ``truncated_row``.
_MIN_SPLIT_ROWS = 2


class Resampled(NamedTuple):
    """A row coerced to the required length, and how it was coerced.

    Attributes:
        values: Exactly n_steps floats.
        kind: The repair kind, one of ``REPAIR_KINDS``, or "" when the row was
            already the right length and nothing was done.
    """

    values: List[float]
    kind: str


def _resample_to_n_steps(values: List[float], n_steps: int) -> Optional[Resampled]:
    """Attempt to coerce `values` to exactly `n_steps` elements.

    Handles the error patterns observed in practice:

    1. **Exact divisor** (e.g. 24 values when n_steps=96): each value represents
       a whole number of steps; repeat each value (n_steps // len) times.
    2. **Close length** (within ±_CLOSE_THRESHOLD of n_steps): the model
       miscounted by a few steps. Truncate if too long; pad with the last
       value if too short.
    3. **Otherwise**, for a row long enough to carry a shape (>= 12 values and no
       more than twice the horizon), interpolate onto the horizon.
    4. **Far off or too short**: return None so the caller can reject the row.

    Values are never modified in sign or magnitude here. Non-finite values are
    left as they are and dealt with once, by the caller, where they are counted.

    Args:
        values: Parsed floats from one session row.
        n_steps: Required number of steps.

    Returns:
        A ``Resampled`` with exactly n_steps floats and the repair kind, or None
        if resampling is not possible.
    """
    n = len(values)
    if n == n_steps:
        return Resampled(values, "")
    if n < _MIN_ROW_VALUES:
        return None

    # Case 1: n divides evenly into n_steps (e.g. 24 hourly → 96 quarter-hour).
    if n_steps % n == 0:
        repeat = n_steps // n
        return Resampled([v for v in values for _ in range(repeat)], "repeated_row")

    # Case 2: close to n_steps — truncate or pad.
    close_range = max(1, int(n_steps * _CLOSE_THRESHOLD))
    if abs(n - n_steps) <= close_range:
        if n > n_steps:
            return Resampled(values[:n_steps], "truncated_row")
        # Pad with the last value to fill the gap.
        return Resampled(values + [values[-1]] * (n_steps - n), "padded_row")

    # Case 3: linear interpolation (e.g. 39 values → 96). Interpolating across a
    # non-finite value would spread it over its neighbours, so those are held out
    # here and restored as non-finite for the caller to count.
    if 12 <= n <= n_steps * 2:
        arr = np.asarray(values, dtype=float)
        finite = np.isfinite(arr)
        x_old = np.linspace(0, 1, n)
        x_new = np.linspace(0, 1, n_steps)
        if not finite.any():
            return Resampled([float("nan")] * n_steps, "interpolated_row")
        out = np.interp(x_new, x_old[finite], arr[finite])
        if not finite.all():
            bad = np.interp(x_new, x_old, (~finite).astype(float)) > 0.5
            out = np.where(bad, np.nan, out)
        return Resampled([float(v) for v in out], "interpolated_row")

    return None


class SplitRun(NamedTuple):
    """Several cars' rows recovered from one labelled run of numbers.

    Attributes:
        rows: The complete rows, each exactly n_steps long, in the order the
            model wrote them. The first belongs to the labelled car.
        leftover: The values after the last complete row, i.e. the row the model
            was still writing when its output stopped. Empty when the run was an
            exact multiple of n_steps.
    """

    rows: List[List[float]]
    leftover: List[float]


def _split_concatenated_run(values: List[float], n_steps: int) -> Optional[SplitRun]:
    """Read one long labelled run as consecutive rows of `n_steps` values.

    The prompt asks for one line per car. A model that ignores the line
    structure writes one label and then every car's values end to end, so a run
    of k * n_steps values is k cars' rows and the cut points are unambiguous.
    A run that is not an exact multiple is still split: the leading complete
    rows are unambiguous, and the remainder is the row the model was still
    writing when it hit its output cap. The remainder is returned rather than
    resampled, because the run itself is the evidence that the model was writing
    n_steps values per car, so reading a fragment of one as a whole coarse row
    would invent charging the model never wrote.

    Args:
        values: Parsed floats from one labelled row.
        n_steps: Required number of steps per car.

    Returns:
        A ``SplitRun``, or None when the run is shorter than
        ``_MIN_SPLIT_ROWS`` whole horizons and is therefore one row.
    """
    if n_steps <= 0 or len(values) < _MIN_SPLIT_ROWS * n_steps:
        return None
    n_rows = len(values) // n_steps
    rows = [values[i * n_steps : (i + 1) * n_steps] for i in range(n_rows)]
    return SplitRun(rows=rows, leftover=values[n_rows * n_steps :])


def parse_llm_schedule(
    response_text: str,
    day: DaySessions,
) -> ParseResult:
    """Convert model output string to schedule matrix.

    Expected format (as specified in ``baseline/strategies.py``):
        - One row per session, in any order.
        - Each row starts with ``EV n:`` (one-based, as the request text names
          the cars) or ``Session i:`` (zero-based, the older format).
        - After the colon, n_steps floating-point numbers separated by spaces;
          the k-th number is p[i,k] in kW at time step k.

    Robustness, all of it recorded in ``ParseResult.repairs``:
        - Non-matching lines are ignored and duplicate rows are dropped (first
          wins); neither is a repair, nothing about the schedule changes.
        - A row of the wrong length is resampled and the repair kind recorded.
        - One label followed by two or more cars' worth of numbers is cut into
          rows of n_steps and given to consecutive sessions from the labelled
          one, each recorded as a ``split_row``. Rows past the last session are
          dropped and reported as an error, and a trailing partial row is left
          unscored as a ``missing_row``.
        - A reply with no labelled rows falls back to reading bare numeric lines
          in order, each recorded as an ``unlabeled_row``. A bare run is never
          split: without a label there is no car to start from, so the cut
          points and the placement would both be guesses.
        - Non-finite values are replaced with 0.0 and counted.
        - Negative values are kept, and counted, so the constraint checker scores
          the violation the model actually produced.
        - A session that got no row is left as zeros and counted as a
          ``missing_row``.

    Args:
        response_text: The model's reply, verbatim.
        day: The day being scheduled; supplies the shape.

    Returns:
        ParseResult with the schedule, whether the parse succeeded, the first
        errors if it did not, and the repair log.
    """
    n_sessions = len(day.sessions)
    n_steps = day.n_steps
    schedule = np.zeros((n_sessions, n_steps), dtype=float)
    events: List[RepairEvent] = []
    negative_cells = 0

    def _record_cells(values: List[float], session_idx: int) -> List[float]:
        """Count non-finite and negative cells; neutralise only the non-finite ones."""
        nonlocal negative_cells
        arr = np.asarray(values, dtype=float)
        finite = np.isfinite(arr)
        n_bad = int((~finite).sum())
        negative_cells += int((arr[finite] < 0.0).sum())
        if n_bad:
            events.append(
                RepairEvent(
                    kind="nonfinite_cell",
                    session_index=session_idx,
                    count=n_bad,
                    detail="NaN or infinity replaced with 0.0 so the day can be scored",
                )
            )
            arr = np.where(finite, arr, 0.0)
        return [float(v) for v in arr]

    def _log(kind: str, session_idx: int, detail: str) -> None:
        """Record a row-level repair."""
        events.append(RepairEvent(kind=kind, session_index=session_idx, detail=detail))

    # Empty day: trivial schedule, no need to parse
    if n_sessions == 0 or n_steps == 0:
        return ParseResult(schedule=schedule, success=True, error_message=None)

    used_rows: List[bool] = [False] * n_sessions
    # Sessions whose row was cut off mid-line by the model's output cap, and how
    # many values arrived, so the missing_row they get says why it is missing.
    cut_off_rows: Dict[int, int] = {}
    lines = response_text.splitlines()

    def _parse_session_line(line: str) -> Optional[Tuple[int, List[float]]]:
        """Parse one 'EV n: v0 v1 ...' or 'Session i: v0 v1 ...' row.

        Returns:
            (zero-based session index, values) or None when the line is not a row.
        """
        stripped = line.strip().lstrip("-*• \t")
        lowered = stripped.lower()
        if lowered.startswith("session"):
            one_based = False
        elif lowered.startswith("ev"):
            one_based = True
        else:
            return None

        # Split at the first colon: "EV 1:" / "Session 0:".
        if ":" not in stripped:
            # Without a colon we do not consider this a valid row.
            return None
        left, right = stripped.split(":", 1)

        # Extract the index from the left part, tolerating spaces and separators
        # ("EV 1", "EV-1", "EV#1"). The label must carry nothing else.
        label = left.strip().replace("-", " ").replace("_", " ").replace("#", " ")
        tokens = label.split()
        if len(tokens) != 2:
            return None
        try:
            index = int(tokens[-1])
        except ValueError:
            return None
        session_idx = index - 1 if one_based else index

        # Parse the numeric values on the right side.
        value_strs = right.strip().split()
        if not value_strs:
            return None
        try:
            values = [float(v) for v in value_strs]
        except ValueError:
            # At least one token is not a float; treat this line as invalid.
            return None
        if len(values) < _MIN_ROW_VALUES and n_steps >= _MIN_ROW_VALUES:
            # A single number after a label is prose, not a schedule row.
            return None

        return session_idx, values

    errors: List[str] = []

    def _assign_split_run(start_idx: int, run: SplitRun) -> None:
        """Place a run written behind one label on consecutive sessions.

        The first row goes to the labelled session and each following row to the
        next one. Every row placed this way is a ``split_row``, the labelled one
        included: the model wrote no row boundary anywhere, so where its row for
        each car ends is the parser's reading and not the model's statement.
        Rows past the last session are dropped and reported, as an out-of-range
        label is. A session already filled by an earlier row keeps it.

        Args:
            start_idx: Zero-based session the label named.
            run: The rows and trailing values from ``_split_concatenated_run``.
        """
        n_written = len(run.rows)
        n_fit = min(n_written, n_sessions - start_idx)
        for offset, row in enumerate(run.rows[:n_fit]):
            idx = start_idx + offset
            if used_rows[idx]:
                continue
            _log(
                "split_row",
                idx,
                f"one label carried {len(run.rows) * n_steps + len(run.leftover)} "
                f"values, read as {n_written} rows of {n_steps}; this is row "
                f"{offset + 1} of them",
            )
            schedule[idx, :] = _record_cells(row, idx)
            used_rows[idx] = True

        if n_written > n_fit:
            errors.append(
                f"One label carried {n_written} rows of {n_steps} values starting "
                f"at session {start_idx}, which runs past session "
                f"{n_sessions - 1}; {n_written - n_fit} row(s) were dropped."
            )

        # The values after the last complete row are an unfinished row, not a
        # coarse one. They stay unscored, and the session they belong to says so.
        cut_idx = start_idx + n_written
        if run.leftover and cut_idx < n_sessions and not used_rows[cut_idx]:
            cut_off_rows[cut_idx] = len(run.leftover)

    for line in lines:
        parsed = _parse_session_line(line)
        if parsed is None:
            continue

        session_idx, values = parsed
        if session_idx < 0 or session_idx >= n_sessions:
            errors.append(f"Session index {session_idx} is out of range [0, {n_sessions - 1}].")
            continue

        if used_rows[session_idx]:
            # First occurrence wins; silently skip duplicates.
            continue

        if len(values) != n_steps:
            run = _split_concatenated_run(values, n_steps)
            if run is not None:
                _assign_split_run(session_idx, run)
                continue

            resampled = _resample_to_n_steps(values, n_steps)
            if resampled is None:
                errors.append(
                    f"Session {session_idx} has {len(values)} values "
                    f"(n_steps={n_steps}); could not resample — skipping."
                )
                continue
            _log(
                resampled.kind,
                session_idx,
                f"row had {len(values)} values, coerced to {n_steps}",
            )
            values = resampled.values

        schedule[session_idx, :] = _record_cells(values, session_idx)
        used_rows[session_idx] = True

    def _finish(success: bool, error_message: Optional[str]) -> ParseResult:
        """Record the sessions that never got a row, then build the result."""
        for idx, used in enumerate(used_rows):
            if not used:
                n_cut = cut_off_rows.get(idx)
                _log(
                    "missing_row",
                    idx,
                    "no row for this session, left as zeros"
                    if n_cut is None
                    else f"row stopped after {n_cut} of {n_steps} values, left as zeros",
                )
        return ParseResult(
            schedule=schedule,
            success=success,
            error_message=error_message,
            repairs=RepairLog(events=tuple(events), negative_cells=negative_cells),
        )

    def _fallback_matrix_parse(lines: List[str]) -> ParseResult:
        """Fallback parser: treat each numeric line as one session row.

        Used when the model omitted the row labels but still returned a numeric
        matrix. Accepts lines whose length can be resampled to n_steps and maps
        them to sessions in order (row 0 → session 0, etc.), which is a guess:
        every row taken this way is recorded as an ``unlabeled_row``.
        """
        row_idx = 0
        for line in lines:
            if row_idx >= n_sessions:
                break
            tokens = line.strip().split()
            if len(tokens) < _MIN_ROW_VALUES:
                continue
            try:
                values = [float(tok) for tok in tokens]
            except ValueError:
                continue

            if len(values) != n_steps:
                resampled = _resample_to_n_steps(values, n_steps)
                if resampled is None:
                    continue
                if resampled.kind:
                    _log(
                        resampled.kind,
                        row_idx,
                        f"row had {len(values)} values, coerced to {n_steps}",
                    )
                values = resampled.values

            _log("unlabeled_row", row_idx, "row carried no label, mapped by position")
            schedule[row_idx, :] = _record_cells(values, row_idx)
            used_rows[row_idx] = True
            row_idx += 1

        if row_idx == 0:
            return _finish(
                False,
                "Could not find any valid 'EV n:' / 'Session i:' rows or numeric "
                "rows with the expected length in the model output.",
            )

        # We successfully filled at least one row; treat this as a successful parse.
        return _finish(True, None)

    if not any(used_rows):
        # Try a more permissive numeric-matrix parse before giving up.
        return _fallback_matrix_parse(lines)

    if errors:
        # We still return the partially filled schedule, but mark parse as failed.
        return _finish(False, "; ".join(errors))

    return _finish(True, None)

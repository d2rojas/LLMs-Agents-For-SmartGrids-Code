"""Parse LLM response text into schedule array (n_sessions x n_steps) in kW."""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from data.format.schema import DaySessions


@dataclass
class ParseResult:
    """Result of parsing LLM output."""

    schedule: np.ndarray  # (n_sessions, n_steps)
    success: bool
    error_message: Optional[str] = None


# Fraction of n_steps a "close" parse is allowed to deviate before we try interpolation.
# e.g. 0.25 means ±24 values for n_steps=96 — so we accept 72–120 via truncate/pad.
_CLOSE_THRESHOLD = 0.25


def _resample_to_n_steps(values: List[float], n_steps: int) -> Optional[List[float]]:
    """Attempt to coerce `values` to exactly `n_steps` elements.

    Handles the three error patterns observed in practice:

    1. **Exact divisor** (e.g. 24 values when n_steps=96): each value represents
       a whole number of steps; repeat each value (n_steps // len) times.
    2. **Close length** (within ±CLOSE_THRESHOLD of n_steps): the model
       miscounted by a few steps. Truncate if too long; pad with the last
       value if too short.
    3. **Far off**: return None so the caller can reject the line.

    Args:
        values: Parsed floats from one session line.
        n_steps: Required number of steps.

    Returns:
        A list of exactly n_steps floats, or None if resampling is not possible.
    """
    n = len(values)
    if n == n_steps:
        return values

    # Case 1: n divides evenly into n_steps (e.g. 24 hourly → 96 quarter-hour).
    if n_steps % n == 0:
        repeat = n_steps // n
        return [v for v in values for _ in range(repeat)]

    # Case 2: close to n_steps — truncate or pad.
    close_range = max(1, int(n_steps * _CLOSE_THRESHOLD))
    if abs(n - n_steps) <= close_range:
        if n > n_steps:
            return values[:n_steps]
        # Pad with the last value to fill the gap.
        return values + [values[-1]] * (n_steps - n)

    # Case 3: use linear interpolation (e.g. 24 or 39 values → 96).
    if 12 <= n <= n_steps * 2:
        arr = np.asarray(values, dtype=float)
        arr = np.where(np.isfinite(arr), arr, 0.0)
        arr = np.maximum(arr, 0.0)
        x_old = np.linspace(0, 1, n)
        x_new = np.linspace(0, 1, n_steps)
        return list(np.interp(x_new, x_old, arr))

    return None


def parse_llm_schedule(
    response_text: str,
    day: DaySessions,
) -> ParseResult:
    """Convert model output string to schedule matrix.

    Expected format (as specified in baseline.prompt.build_prompt):
        - One line per session, in any order.
        - Each line starts with: 'Session i:' where i is the integer session_index.
        - After the colon, there are n_steps floating-point numbers separated by
          spaces; the k-th number is p[i,k] in kW at time step k.

    Robustness:
        - Ignores non-matching lines.
        - Tolerates extra whitespace and duplicate session lines (first wins).
        - When a session line has the wrong number of values, attempts resampling
          via _resample_to_n_steps before rejecting:
            * Exact divisor (e.g. 24 values for n_steps=96): each value is
              repeated (n_steps // len) times (LLM used hourly resolution).
            * Within ±10% of n_steps: truncate or pad with last value.
            * Otherwise: session is skipped and logged as a warning.
    """
    n_sessions = len(day.sessions)
    n_steps = day.n_steps
    schedule = np.zeros((n_sessions, n_steps), dtype=float)

    def _sanitize(s: np.ndarray) -> None:
        """Replace inf/nan with 0, clamp negative to 0. Prevents numpy warnings in metrics."""
        s[:] = np.where(np.isfinite(s), s, 0.0)
        np.maximum(s, 0.0, out=s)

    # Empty day: trivial schedule, no need to parse
    if n_sessions == 0 or n_steps == 0:
        return ParseResult(schedule=schedule, success=True, error_message=None)

    used_rows: List[bool] = [False] * n_sessions
    lines = response_text.splitlines()

    def _parse_session_line(line: str) -> Optional[Tuple[int, List[float]]]:
        """Parse one 'Session i: v0 v1 ...' line. Return (i, values) or None."""
        stripped = line.strip()
        if not stripped.lower().startswith("session"):
            return None

        # Split at the first colon: "Session i:" / "Session i - " etc.
        if ":" in stripped:
            left, right = stripped.split(":", 1)
        else:
            # If there is no colon, we do not consider this a valid session line
            return None

        # Extract the session index i from the left part.
        # Expected pattern: "Session i" (case-insensitive), but be tolerant to spaces.
        tokens = left.strip().split()
        if len(tokens) < 2:
            return None
        try:
            session_idx = int(tokens[-1])
        except ValueError:
            return None

        # Parse the numeric values on the right side.
        value_strs = right.strip().split()
        if not value_strs:
            return None
        try:
            values = [float(v) for v in value_strs]
        except ValueError:
            # At least one token is not a float; treat this line as invalid
            return None

        return session_idx, values

    errors: List[str] = []
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
            resampled = _resample_to_n_steps(values, n_steps)
            if resampled is None:
                errors.append(
                    f"Session {session_idx} has {len(values)} values "
                    f"(n_steps={n_steps}); could not resample — skipping."
                )
                continue
            values = resampled

        schedule[session_idx, :] = values
        used_rows[session_idx] = True

    def _fallback_matrix_parse(lines: List[str]) -> ParseResult:
        """Fallback parser: treat each numeric line as one session row.

        Used when the model omitted 'Session i:' prefixes but still returned a
        numeric matrix. Accepts lines whose length can be resampled to n_steps.
        Maps rows to sessions in order (row 0 → session 0, etc.).
        """

        row_idx = 0
        for line in lines:
            if row_idx >= n_sessions:
                break
            tokens = line.strip().split()
            if not tokens:
                continue
            try:
                values = [float(tok) for tok in tokens]
            except ValueError:
                continue

            if len(values) != n_steps:
                resampled = _resample_to_n_steps(values, n_steps)
                if resampled is None:
                    continue
                values = resampled

            schedule[row_idx, :] = values
            row_idx += 1

        _sanitize(schedule)
        if row_idx == 0:
            return ParseResult(
                schedule=schedule,
                success=False,
                error_message=(
                    "Could not find any valid 'Session i:' lines or numeric "
                    "rows with the expected length in the model output."
                ),
            )

        # We successfully filled at least one row; treat this as a successful parse.
        return ParseResult(schedule=schedule, success=True, error_message=None)

    if not any(used_rows):
        # Try a more permissive numeric-matrix parse before giving up.
        return _fallback_matrix_parse(lines)

    _sanitize(schedule)
    if errors:
        # We still return the partially filled schedule, but mark parse as failed.
        return ParseResult(
            schedule=schedule,
            success=False,
            error_message="; ".join(errors),
        )

    return ParseResult(schedule=schedule, success=True, error_message=None)

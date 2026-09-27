"""Formulation correctness: did the model extract the right problem from the text?

This is the EV counterpart of ``power-flow-agent/benchmarks/metrics.py``'s
``formulation_check``: there, the intended tool calls are compared against the
executed ones; here, the per-session parameters the model extracted from the
free-form request are compared against the ground-truth structured sessions the
text was generated from. Same verdict name (``formulation_exact``), same idea of
an error taxonomy (``formulation_error_type``).

Comparison rule
---------------
* ``arrival_idx`` and ``departure_idx``: exact equality of step indices. A
  parsed session carries fractional hours, so it is converted with
  ``idx = round(hour / dt_hours)`` first. Times are the availability window; an
  index off by one is a different problem, so no tolerance is given.
* ``energy_kwh`` and ``max_power_kw``: 1 % relative tolerance.

Conversion note: ``methods/agent/parse/parse.py::parsed_problem_to_day_site_tou`` applies
repairs when it builds the solver input (overnight windows get a one-hour
fallback, indices are clamped to the horizon, a non-positive energy becomes
1 kWh). This module does *not* apply them. Those repairs hide extraction errors,
and hiding them here would make the column measure the repair rather than the
model.

Error taxonomy
--------------
``omitted_session`` (a ground-truth session has no extracted counterpart),
``extra_session`` (an extracted session matches no ground-truth session),
``wrong_field`` (a field differs), ``wrong_unit`` (a field differs by a ratio
that a unit confusion explains: Wh for kWh, W for kW, minutes or steps for
hours). The day-level type is the first of
``omitted_session > extra_session > wrong_field > wrong_unit`` present, the same
"first offending class wins" rule the power-flow comparator uses.

A day is ``formulation_exact`` only when every ground-truth session is matched,
no extra session was invented, and every field of every session is exact. A day
with no sessions on either side is exact: there was nothing to extract.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from data.format.schema import DaySessions, Session

FORMULATION_ERROR_TYPES: Tuple[str, ...] = (
    "ok",
    "omitted_session",
    "extra_session",
    "wrong_field",
    "wrong_unit",
)

# First present wins, for a session's fields and for the day's sessions alike.
_ERROR_PRIORITY: Tuple[str, ...] = ("omitted_session", "extra_session", "wrong_field", "wrong_unit")

# 1 % relative tolerance on the magnitudes; step indices are compared exactly.
FIELD_REL_TOL = 0.01

# Ratios that a unit confusion explains. Energy and power: Wh quoted as kWh, W as
# kW, and the inverse. Time: minutes or seconds quoted as hours, and the inverse;
# step-index-as-hour ratios depend on dt and are added per call.
_VALUE_UNIT_RATIOS: Tuple[float, ...] = (1000.0, 0.001)
_TIME_UNIT_RATIOS: Tuple[float, ...] = (60.0, 1.0 / 60.0, 3600.0, 1.0 / 3600.0)

STEP_FIELDS: Tuple[str, ...] = ("arrival_idx", "departure_idx")
VALUE_FIELDS: Tuple[str, ...] = ("energy_kwh", "max_power_kw")


@dataclass(frozen=True)
class _Params:
    """One session reduced to the four compared parameters, in common units."""

    session_id: str
    arrival_idx: Optional[int]
    departure_idx: Optional[int]
    energy_kwh: Optional[float]
    max_power_kw: Optional[float]


@dataclass
class FieldCheck:
    """One compared parameter.

    Attributes:
        name: "arrival_idx" | "departure_idx" | "energy_kwh" | "max_power_kw".
        parsed_value: Value the model extracted (None when it never gave one).
        truth_value: Ground-truth value.
        exact: True when the field satisfies its comparison rule.
        error_type: None when exact, else "wrong_field" or "wrong_unit".
        detail: Short note, empty when exact.
    """

    name: str
    parsed_value: Optional[float]
    truth_value: Optional[float]
    exact: bool
    error_type: Optional[str] = None
    detail: str = ""


@dataclass
class SessionCheck:
    """Per-session verdict.

    Attributes:
        session_id: Ground-truth id, or the extracted id for an extra session.
        matched: Whether the session was paired across the two sides at all.
        exact: True when matched and every field is exact.
        error_type: "ok" | "omitted_session" | "extra_session" | "wrong_field" |
            "wrong_unit".
        fields: Per-field results (empty for an omitted or extra session).
        detail: Short human-readable note.
    """

    session_id: str
    matched: bool
    exact: bool
    error_type: str
    fields: List[FieldCheck] = field(default_factory=list)
    detail: str = ""


@dataclass
class FormulationResult:
    """Day-level verdict and its per-session evidence.

    Attributes:
        formulation_exact: The day verdict. True only when every ground-truth
            session was matched exactly and nothing extra was invented.
        formulation_error_type: One of FORMULATION_ERROR_TYPES ("ok" when exact).
        n_truth: Number of ground-truth sessions.
        n_parsed: Number of extracted sessions.
        n_sessions_exact: Number of sessions matched with every field exact.
        matched_by: "session_id" or "position"; how the two sides were paired.
        sessions: Per-session results, ground-truth order first, then extras.
        detail: Short human-readable summary.
    """

    formulation_exact: bool
    formulation_error_type: str
    n_truth: int
    n_parsed: int
    n_sessions_exact: int
    matched_by: str
    sessions: List[SessionCheck] = field(default_factory=list)
    detail: str = ""


# --------------------------------------------------------------------------- normalisation


def _truth_sessions(truth: Any) -> List[Session]:
    """Ground-truth sessions from a DaySessions or a sequence of Session."""
    if isinstance(truth, DaySessions):
        return list(truth.sessions)
    return list(truth or [])


def _dt_hours(parsed: Any, truth: Any, dt_hours: Optional[float]) -> float:
    """Step duration to convert extracted hours into step indices."""
    if dt_hours is not None:
        return float(dt_hours)
    for candidate in (parsed, truth):
        dt = getattr(candidate, "dt_hours", None)
        if dt:
            return float(dt)
    return 0.25  # schema.DEFAULT_DT_HOURS


def _hour_to_idx(hour: Optional[float], dt: float) -> Optional[int]:
    """Fractional hour from midnight to a step index; None stays None."""
    if hour is None:
        return None
    return int(round(float(hour) / dt))


def _parsed_params(parsed: Any, dt: float) -> List[_Params]:
    """Normalise the extracted side (ParsedProblem, ParsedSession list, or Sessions)."""
    items = getattr(parsed, "sessions", parsed) or []
    out: List[_Params] = []
    for i, ps in enumerate(items):
        if hasattr(ps, "arrival_idx"):  # already a structured Session
            out.append(
                _Params(
                    session_id=str(getattr(ps, "session_id", "") or f"EV-{i + 1}"),
                    arrival_idx=int(ps.arrival_idx),
                    departure_idx=int(ps.departure_idx),
                    energy_kwh=float(ps.energy_kwh),
                    max_power_kw=float(ps.max_power_kw),
                )
            )
            continue
        out.append(
            _Params(
                session_id=str(getattr(ps, "session_id", "") or f"EV-{i + 1}"),
                arrival_idx=_hour_to_idx(getattr(ps, "arrival_hour", None), dt),
                departure_idx=_hour_to_idx(getattr(ps, "departure_hour", None), dt),
                energy_kwh=(None if getattr(ps, "energy_kwh", None) is None else float(ps.energy_kwh)),
                max_power_kw=(
                    None if getattr(ps, "max_power_kw", None) is None else float(ps.max_power_kw)
                ),
            )
        )
    return out


def _truth_params(sessions: Sequence[Session]) -> List[_Params]:
    """Normalise the ground-truth side."""
    return [
        _Params(
            session_id=str(s.session_id),
            arrival_idx=int(s.arrival_idx),
            departure_idx=int(s.departure_idx),
            energy_kwh=float(s.energy_kwh),
            max_power_kw=float(s.max_power_kw),
        )
        for s in sessions
    ]


# --------------------------------------------------------------------------- matching


def _match(
    truth: Sequence[_Params], parsed: Sequence[_Params]
) -> Tuple[List[Tuple[Optional[_Params], Optional[_Params]]], str]:
    """Pair the two sides.

    By ``session_id`` when both sides have unique ids and share at least one, so
    that a reordered extraction is not scored as a wrong session. Otherwise by
    position, which is how the request text enumerates the cars.
    """
    t_ids = [p.session_id for p in truth]
    p_ids = [p.session_id for p in parsed]
    ids_usable = (
        len(set(t_ids)) == len(t_ids)
        and len(set(p_ids)) == len(p_ids)
        and bool(set(t_ids) & set(p_ids))
    )
    pairs: List[Tuple[Optional[_Params], Optional[_Params]]] = []
    if ids_usable:
        index = {p.session_id: p for p in parsed}
        used: set = set()
        for t in truth:
            match = index.get(t.session_id)
            if match is not None:
                used.add(match.session_id)
            pairs.append((t, match))
        for p in parsed:
            if p.session_id not in used:
                pairs.append((None, p))
        return pairs, "session_id"
    for i in range(max(len(truth), len(parsed))):
        t = truth[i] if i < len(truth) else None
        p = parsed[i] if i < len(parsed) else None
        pairs.append((t, p))
    return pairs, "position"


# --------------------------------------------------------------------------- field comparison


def _ratio_hit(parsed_value: float, truth_value: float, ratios: Iterable[float]) -> Optional[float]:
    """The ratio r for which ``parsed ≈ truth * r``, or None."""
    if truth_value == 0:
        return None
    for r in ratios:
        if abs(parsed_value - truth_value * r) <= FIELD_REL_TOL * abs(truth_value * r):
            return r
    return None


def _check_step_field(name: str, parsed_value: Optional[float], truth_value: float, dt: float) -> FieldCheck:
    """Step index: exact equality, with a unit diagnosis when it is a clean ratio."""
    if parsed_value is None:
        return FieldCheck(name, None, truth_value, False, "wrong_field", "not extracted")
    if int(parsed_value) == int(truth_value):
        return FieldCheck(name, float(parsed_value), float(truth_value), True)
    ratios = tuple(_TIME_UNIT_RATIOS) + (1.0 / dt, dt)
    r = _ratio_hit(float(parsed_value), float(truth_value), ratios)
    if r is not None:
        return FieldCheck(
            name,
            float(parsed_value),
            float(truth_value),
            False,
            "wrong_unit",
            f"off by a factor of {r:g}: a time unit was read as another",
        )
    return FieldCheck(
        name,
        float(parsed_value),
        float(truth_value),
        False,
        "wrong_field",
        f"step index {int(parsed_value)} != {int(truth_value)}",
    )


def _check_value_field(name: str, parsed_value: Optional[float], truth_value: float) -> FieldCheck:
    """Energy or power: 1 % relative tolerance, with a unit diagnosis on a clean ratio."""
    if parsed_value is None:
        return FieldCheck(name, None, truth_value, False, "wrong_field", "not extracted")
    if abs(float(parsed_value) - float(truth_value)) <= FIELD_REL_TOL * abs(float(truth_value)):
        return FieldCheck(name, float(parsed_value), float(truth_value), True)
    r = _ratio_hit(float(parsed_value), float(truth_value), _VALUE_UNIT_RATIOS)
    if r is not None:
        return FieldCheck(
            name,
            float(parsed_value),
            float(truth_value),
            False,
            "wrong_unit",
            f"off by a factor of {r:g}: base units quoted as kilo-units or the inverse",
        )
    return FieldCheck(
        name,
        float(parsed_value),
        float(truth_value),
        False,
        "wrong_field",
        f"{parsed_value:g} != {truth_value:g} beyond {100 * FIELD_REL_TOL:g} % tolerance",
    )


def _first_error(types: Iterable[Optional[str]]) -> Optional[str]:
    """First of _ERROR_PRIORITY present in ``types``."""
    present = {t for t in types if t}
    for candidate in _ERROR_PRIORITY:
        if candidate in present:
            return candidate
    return None


def _check_pair(truth: _Params, parsed: _Params, dt: float) -> SessionCheck:
    """Compare one matched session."""
    fields = [
        _check_step_field("arrival_idx", parsed.arrival_idx, float(truth.arrival_idx), dt),
        _check_step_field("departure_idx", parsed.departure_idx, float(truth.departure_idx), dt),
        _check_value_field("energy_kwh", parsed.energy_kwh, float(truth.energy_kwh)),
        _check_value_field("max_power_kw", parsed.max_power_kw, float(truth.max_power_kw)),
    ]
    bad = [f for f in fields if not f.exact]
    if not bad:
        return SessionCheck(truth.session_id, True, True, "ok", fields, "every field exact")
    err = _first_error(f.error_type for f in bad) or "wrong_field"
    return SessionCheck(
        truth.session_id,
        True,
        False,
        err,
        fields,
        "; ".join(f"{f.name}: {f.detail}" for f in bad),
    )


# --------------------------------------------------------------------------- public API


def formulation_exact(
    parsed: Any,
    truth: Any,
    *,
    dt_hours: Optional[float] = None,
) -> FormulationResult:
    """Compare the extracted problem against the ground-truth sessions.

    Args:
        parsed: What the model extracted: a ``ParsedProblem``, a sequence of
            ``ParsedSession`` (fractional hours), or a sequence of ``Session``
            (already step-indexed).
        truth: The ground truth the free-form text was generated from: a
            ``DaySessions`` or a sequence of ``Session``.
        dt_hours: Step duration used to turn extracted hours into indices.
            Defaults to the parsed problem's, then the ground truth's, then 0.25.

    Returns:
        FormulationResult. ``result.formulation_exact`` is the day verdict and
        ``result.sessions`` carries the per-session evidence. A day with no
        sessions on either side is exact.
    """
    dt = _dt_hours(parsed, truth, dt_hours)
    truth_list = _truth_params(_truth_sessions(truth))
    parsed_list = _parsed_params(parsed, dt)
    pairs, matched_by = _match(truth_list, parsed_list)

    checks: List[SessionCheck] = []
    for t, p in pairs:
        if t is not None and p is not None:
            checks.append(_check_pair(t, p, dt))
        elif t is not None:
            checks.append(
                SessionCheck(t.session_id, False, False, "omitted_session", [], "no extracted session for this car")
            )
        elif p is not None:
            checks.append(
                SessionCheck(p.session_id, False, False, "extra_session", [], "extracted a car the request never described")
            )

    n_exact = sum(1 for c in checks if c.exact)
    day_error = _first_error(c.error_type for c in checks if c.error_type != "ok")
    exact = day_error is None
    if exact:
        detail = (
            "no sessions on either side"
            if not truth_list and not parsed_list
            else f"{n_exact}/{len(truth_list)} sessions exact"
        )
    else:
        detail = "; ".join(f"{c.session_id}: {c.error_type}" for c in checks if c.error_type != "ok")
    return FormulationResult(
        formulation_exact=exact,
        formulation_error_type=day_error or "ok",
        n_truth=len(truth_list),
        n_parsed=len(parsed_list),
        n_sessions_exact=n_exact,
        matched_by=matched_by,
        sessions=checks,
        detail=detail,
    )


def formulation_exact_rate(results: Iterable[FormulationResult]) -> Dict[str, Any]:
    """``{"rate", "count", "total"}`` over day verdicts, for the Form. column."""
    from evaluation.metrics import rate  # local import: metrics imports nothing from here

    return rate([r.formulation_exact for r in results])


def formulation_error_counts(results: Iterable[FormulationResult]) -> Dict[str, int]:
    """Count of each error type over days, for the supplement's breakdown."""
    counts = {t: 0 for t in FORMULATION_ERROR_TYPES}
    for r in results:
        counts[r.formulation_error_type] = counts.get(r.formulation_error_type, 0) + 1
    return counts

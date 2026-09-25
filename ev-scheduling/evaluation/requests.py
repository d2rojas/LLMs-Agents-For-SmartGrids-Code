"""Seeded free-form EV charging requests with deterministic ground truth.

This is the EV counterpart of ``power-flow-agent/benchmarks/requests.py``: a
seeded generator that turns a structured day into the natural-language text a
system is actually evaluated on, and pairs it with the answer that text asks for.
Same vocabulary: ``generate_requests``, ``compute_ground_truth``, ``to_jsonl`` /
``from_jsonl``, a CLI, and a ``Request`` record carrying ``text``, ``seed`` and
``truth``.

Why the module exists
---------------------
The benchmark used to hand the agent an already-structured ``DaySessions`` *and*
a session table inside the prompt (``scripts/run_agent_vs_baseline.py`` and
``baseline/prompt.py::build_prompt_for_agent``), so no formulation step existed
anywhere on the evaluated path and ``evaluation/formulation.py`` had nothing to
score. The rigid ``_build_nl_request`` helper in that script emits one HH:MM
template for every car, which tests a regex, not an extraction. The text here
varies the time expressions ("6 pm", "18:00", "quarter past eight in the
morning", "half seven in the evening", "midnight at the end of the day"), the
units (kWh and Wh, kW and W, dollars and cents), the sentence shapes and the
order of the cars, so the formulation column measures reading rather than
pattern matching.

The answer term
---------------
``evaluation/outcome.py`` makes Solved a conjunction that includes the answer to
the question asked, because the power-flow study checked the final state first
and only looked at the answer when the state check had already failed: a system
that computed the right state and then named the wrong bus scored as solved, and
correcting it moved one method from 97.5 to 65.0. Most requests here therefore
ask something with a ground-truth answer. A request that only prescribes an
operation gets ``kind="state"``: its truth is the resulting-state summary, it is
stored and never compared, and that is not the same as an answer that passed.

Which questions are askable, and why ``peak_kw`` is not among them
------------------------------------------------------------------
An answer may only be scored when it is the same for *every* optimal schedule.
The LP minimises ``cost + M * unmet``, so the optimum's cost and its total unmet
energy are unique, but the schedule that achieves them is not: off-peak steps
share one price, so load can be shifted between them for free. Measured on the
committed fixture day 2019-05-15, the returned optimum peaks at 25.843 kW while
another schedule of exactly the same cost peaks at 17.943 kW. A peak answer
would therefore mark an equally optimal schedule wrong, so no request asks for
the peak; it is recorded in the state summary instead, where nothing is compared
against it. The same argument rules out "which cars end up short in your
schedule": on a congested day the LP spreads the shortfall over the cars in an
arbitrary way (every fixture congested day comes back with all sessions
partially served), so the *set* is solver-dependent even though its existence is
not. The questions that survive are:

* from the solver, invariant across optima: total cost, total unmet energy, the
  share of requested energy delivered, and whether every car can leave with what
  it asked for;
* computed from the structured day the text was generated from: the total energy
  requested (a unit-conversion probe), how many cars are plugged in at a stated
  time (a time-parsing probe), which car asks for the most energy, and which
  cars ask for more than their own charger can deliver while they are parked
  (provably short in every feasible schedule, and empty on all twenty committed
  fixture days, so that variant simply does not fire there).

Session matching
----------------
``evaluation/formulation.py`` pairs parsed sessions with ground-truth sessions by
``session_id`` only when both sides carry unique ids and share at least one, and
falls back to POSITION otherwise, which is the normal case here: real ACN ids
like ``2-39-21`` and fixture ids like ``SYNTH-2019-05-01-004`` never appear in
the text, and a parser labels what it reads ``EV-1``, ``EV-2``, ... So the
invariant this module guarantees is positional: **``request.day.sessions[i]`` is
the car the text calls ``EV {i+1}``**. The cars are shuffled relative to the
source day, and ``request.day`` is stored in the shuffled order with the original
ids untouched, so provenance survives (a ``SYNTH-`` id stays a ``SYNTH-`` id) and
position matching is still correct. ``request.labels`` is the parallel tuple of
answer labels (``"EV-1"``, ...).

Extraction
----------
``extract_answer`` pulls the answer out of a reply with keyword-anchored
patterns, per variant. A checkable request whose answer cannot be extracted
yields ``given=None``, which ``outcome.check_answer`` scores as ``fail``: an
extraction miss must never read as a pass. ``LIMITATIONS`` states what that
costs.

Integration note: ``request.site_cap_kw`` is part of the request (the
``schedule_under_cap`` variant states a lower cap in the text), so a harness must
build its ``SiteConfig``/``TOUConfig`` from the request, not from a module
constant. ``build_site_tou(request)`` does it.

CLI:
    python -m evaluation.requests --seed 0 --out evaluation/requests_caltech.jsonl
    python -m evaluation.requests --seed 1 --source cache --limit 5
"""

import argparse
import hashlib
import json
import random
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date as _date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from config.site import SiteConfig, TOUConfig, default_tou_rates
from data.format.schema import DaySessions, Session
from evaluation.metrics import UNMET_TOL_KWH, peak_load_kw, total_cost, total_unmet_kwh
from evaluation.outcome import RequestAnswer
from optimization.solver import solve

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Defaults of the benchmark site, matching scripts/run_agent_vs_baseline.py
# (P_MAX_KW) and config/site.py::default_tou_rates.
SITE_CAP_KW = 50.0
PEAK_PRICE = 0.45
OFF_PEAK_PRICE = 0.12
PEAK_START_HOUR = 16
PEAK_END_HOUR = 21

# Lower caps the schedule_under_cap variant may state in the text.
LOWER_CAPS_KW: Tuple[float, ...] = (30.0, 35.0, 40.0, 45.0)

# A car is "fully served" when its shortfall is at or below this; the same
# threshold evaluation/metrics.py calls solver slop. Note that
# ``metrics.pct_fully_served`` uses 1e-6 instead, so the two disagree for a
# session whose shortfall lands between them; no such session exists on any
# committed fixture day (checked in tests/test_requests.py).
SERVED_TOL_KWH = UNMET_TOL_KWH

VARIANTS: Tuple[str, ...] = (
    "schedule_only",
    "cost_question",
    "unmet_question",
    "served_share",
    "schedule_under_cap",
    "feasible_yesno",
    "total_energy_requested",
    "cars_plugged_in_at",
    "largest_request_car",
    "capacity_shortfall_cars",
)

# Requests that only prescribe an operation. Their truth is the resulting-state
# summary and outcome.check_answer records them as not_checkable.
STATE_VARIANTS: Tuple[str, ...] = ("schedule_only", "schedule_under_cap")

# Questions whose answer is only interesting on a day that cannot be served in
# full; generate_requests routes the congested days to these in rotation.
SHORTFALL_VARIANTS: Tuple[str, ...] = ("unmet_question", "feasible_yesno", "served_share")

ANSWER_KIND_BY_VARIANT: Dict[str, str] = {
    "schedule_only": "state",
    "schedule_under_cap": "state",
    "cost_question": "cost",
    "unmet_question": "unmet_kwh",
    "served_share": "pct_served",
    "feasible_yesno": "value",
    "total_energy_requested": "value",
    "cars_plugged_in_at": "value",
    "largest_request_car": "value",
    "capacity_shortfall_cars": "sessions",
}

# Quantities that outcome.py lists as answer kinds but that no request here
# asks for, because their value is not fixed by the objective: two schedules of
# exactly the same optimal cost disagree about them, so scoring an answer
# against one of them would mark an equally optimal system wrong. They are kept
# in the state summary, which is stored and never compared. The reason is
# measured, not assumed: the numbers below come from the committed fixture day.
NOT_ASKED: Dict[str, str] = {
    "peak_kw": (
        "the LP does not price the peak, so load may be shifted between off-peak steps "
        "for free: on SYNTHETIC_caltech_2019-05-15 the returned optimum peaks at "
        "25.843 kW while a schedule of identical cost peaks at 17.943 kW"
    ),
    "short_session_set": (
        "on a congested day the LP minimises total unmet energy but not its distribution, "
        "so which cars end up short is solver-dependent; whether any car is short is not, "
        "and that is what feasible_yesno asks"
    ),
}

LIMITATIONS: Tuple[str, ...] = (
    # An answer the patterns cannot find is scored wrong even when the reply
    # states it in some unforeseen wording. The alternative, treating a miss as a
    # pass, is the failure this whole term exists to catch.
    "unextractable_answer_counts_as_wrong",
    # When several anchored patterns match, the first match of the
    # highest-priority pattern wins; a reply that states two candidate numbers is
    # read as meaning the first.
    "first_matching_pattern_wins",
    # No request asks for the peak load or for the set of short sessions: neither
    # is the same across equally optimal schedules (see the module docstring).
    "peak_and_short_set_not_asked_because_not_unique",
)


# --------------------------------------------------------------------------- record


@dataclass(frozen=True)
class EVRequest:
    """One free-form request and the ground truth it is scored against.

    Attributes:
        id: Stable identifier, "<site>-<date>-<variant>-s<seed>".
        site_id: ACN site the day belongs to.
        date: Calendar day as an ISO string ("" when the day is not dated).
        seed: Generator seed this text was rendered with.
        variant: Which of VARIANTS produced it.
        kind: RequestAnswer kind ("state" for a prescription-only request).
        text: The natural-language request. This is the whole input.
        day: The ground-truth sessions, in the order the text enumerates them;
            ``day.sessions[i]`` is the car the text calls ``EV {i+1}``.
        labels: Answer labels parallel to ``day.sessions`` ("EV-1", "EV-2", ...).
        site_cap_kw: Site power cap the text states (kW). Not always
            SITE_CAP_KW: schedule_under_cap states a lower one.
        peak_price: Peak TOU rate the text states ($/kWh).
        off_peak_price: Off-peak TOU rate the text states ($/kWh).
        question: The question sentence, "" for a state variant.
        truth: Ground-truth answer, or the resulting-state summary for a state
            variant.
        tolerance: Numeric tolerance, None to use outcome.ANSWER_TOLERANCES.
        synthetic: True when the source sessions are generated fixtures, so a
            number computed from this request is traceable as synthetic.
        source_session_ids: Original session ids, in the same order as ``day``.
        detail: Short note on what the request asks and how the truth was formed.
    """

    id: str
    site_id: str
    date: str
    seed: int
    variant: str
    kind: str
    text: str
    day: DaySessions
    labels: Tuple[str, ...]
    site_cap_kw: float
    peak_price: float
    off_peak_price: float
    question: str
    truth: Any
    tolerance: Optional[float] = None
    synthetic: bool = False
    source_session_ids: Tuple[str, ...] = ()
    detail: str = ""

    @property
    def checkable(self) -> bool:
        """Whether the request asks something with a ground-truth answer."""
        return self.kind != "state"


def build_site_tou(request: EVRequest) -> Tuple[SiteConfig, TOUConfig]:
    """SiteConfig and TOUConfig for the request's own cap and prices.

    A harness must use these rather than module constants: the cap and the
    prices are part of the request text and the schedule_under_cap variant
    states a lower cap than the site's default.
    """
    day = request.day
    site = SiteConfig(P_max_kw=float(request.site_cap_kw), n_steps=day.n_steps, dt_hours=day.dt_hours)
    tou = TOUConfig(
        rates_per_kwh=default_tou_rates(
            day.n_steps, peak_price=float(request.peak_price), off_peak_price=float(request.off_peak_price)
        )
    )
    return site, tou


# --------------------------------------------------------------------------- seeding


def _stable_rng(*parts: Any) -> random.Random:
    """Deterministic Random for the given parts.

    Uses sha256 rather than ``hash()``, whose string seed is salted per process
    and would make the same request render differently between runs.
    """
    key = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


# --------------------------------------------------------------------------- phrasings

_HOUR_WORDS: Tuple[str, ...] = (
    "twelve", "one", "two", "three", "four", "five",
    "six", "seven", "eight", "nine", "ten", "eleven",
)

_DAYPARTS: Tuple[Tuple[int, int, str], ...] = (
    (1, 12, "in the morning"),
    (12, 17, "in the afternoon"),
    (17, 21, "in the evening"),
    (21, 24, "at night"),
)


def _hour_word(hour24: int) -> str:
    """Spoken hour name ("seven" for 7 and for 19)."""
    return _HOUR_WORDS[hour24 % 12]


def _daypart(hour24: int) -> str:
    """"in the morning" / "in the afternoon" / "in the evening" / "at night"."""
    for lo, hi, name in _DAYPARTS:
        if lo <= hour24 < hi:
            return name
    return "at night"


def time_phrases(idx: int, n_steps: int, dt_hours: float) -> List[str]:
    """Every unambiguous way this generator writes the clock time of a step.

    Each phrase denotes one exact time: the request is scored on step indices
    with no tolerance, so a vague expression ("in the morning") would make the
    formulation column measure the generator's sloppiness. ``idx == n_steps`` is
    the end of the horizon and is written as 24:00, never as a bare "midnight",
    which a parser reads as hour 0.
    """
    minutes = int(round(idx * dt_hours * 60.0))
    if idx >= n_steps and minutes % (24 * 60) == 0:
        return ["24:00", "midnight at the end of the day"]

    hour, minute = divmod(minutes, 60)
    hour12 = hour % 12 or 12
    meridiem = "am" if hour < 12 else "pm"
    part = _daypart(hour)

    out = [f"{hour:02d}:{minute:02d}"]
    out.append(f"{hour12} {meridiem}" if minute == 0 else f"{hour12}:{minute:02d} {meridiem}")
    if minute == 0 and hour == 12:
        out += ["noon", "midday"]
    if minute == 0 and hour == 0:
        out.append("midnight")
    if hour == 0:
        anchor = "midnight"
    else:
        anchor = f"{_hour_word(hour)}"
    if minute == 0 and hour not in (0, 12):
        out.append(f"{anchor} o'clock {part}")
    elif minute == 15:
        out.append(f"quarter past {anchor}" + ("" if hour == 0 else f" {part}"))
    elif minute == 30:
        out.append(f"half past {anchor}" + ("" if hour == 0 else f" {part}"))
        if hour != 0:
            out.append(f"half {anchor} {part}")  # British usage: "half seven" is 7:30
    elif minute == 45:
        nxt = hour + 1
        if nxt == 12:
            out.append("a quarter to noon")
        elif nxt in (0, 24):
            out.append("a quarter to midnight")
        else:
            out.append(f"a quarter to {_hour_word(nxt)} {_daypart(nxt)}")
    return out


def _fmt(value: float, decimals: int = 2) -> str:
    """Trim trailing zeros after the point: 7.0 -> "7", 12.50 -> "12.5".

    Only the fractional part is trimmed. Stripping zeros from a whole number
    would turn a 50000 W cap into "5".
    """
    text = f"{value:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def energy_phrases(energy_kwh: float) -> List[str]:
    """Ways of writing a requested energy, including forms needing conversion."""
    wh = energy_kwh * 1000.0
    wh_text = _fmt(wh, 1)
    return [
        f"{_fmt(energy_kwh)} kWh",
        f"{energy_kwh:.2f} kWh",
        f"{_fmt(energy_kwh)} kilowatt-hours",
        f"{wh_text} Wh",
        f"{wh_text} watt-hours",
    ]


def power_phrases(max_power_kw: float) -> List[str]:
    """Ways of writing a charger rating, including forms needing conversion.

    Every phrase is a bare quantity so that it fits each session template, which
    supplies its own article and noun.
    """
    w_text = _fmt(max_power_kw * 1000.0, 1)
    return [
        f"{_fmt(max_power_kw)} kW",
        f"{_fmt(max_power_kw)} kilowatts",
        f"{w_text} W",
        f"{w_text} watts",
    ]


def _cap_phrases(cap_kw: float) -> List[str]:
    return [
        f"{_fmt(cap_kw)} kW",
        f"{_fmt(cap_kw * 1000.0, 0)} W",
        f"{_fmt(cap_kw)} kilowatts",
    ]


def _price_sentences(rng: random.Random, peak: float, off_peak: float) -> str:
    """One sentence stating the TOU rates, sometimes in cents."""
    options = [
        f"Energy costs ${peak:.2f} per kWh between 4 pm and 9 pm and ${off_peak:.2f} per kWh the rest of the day.",
        f"The tariff is ${off_peak:.2f}/kWh off-peak and ${peak:.2f}/kWh from 16:00 to 21:00.",
        (
            f"Peak hours run from four in the afternoon to nine in the evening at "
            f"{_fmt(peak * 100.0, 0)} cents a kWh, and the rest of the day costs "
            f"{_fmt(off_peak * 100.0, 0)} cents a kWh."
        ),
    ]
    return rng.choice(options)


def _cap_sentence(rng: random.Random, cap_kw: float, lowered: bool) -> str:
    cap = rng.choice(_cap_phrases(cap_kw))
    if lowered:
        return rng.choice([
            f"Today the lot has to stay under {cap} in total, lower than usual.",
            f"For today only, keep the total draw of the lot at or below {cap}.",
            f"The feeder is derated today, so the whole lot must not exceed {cap}.",
        ])
    return rng.choice([
        f"The lot can never pull more than {cap} in total.",
        f"The transformer serving the lot is limited to {cap}.",
        f"Total draw across all the chargers has to stay at or below {cap}.",
    ])


def _preamble(rng: random.Random, n: int, site_id: str, day_date: str) -> str:
    where = {"caltech": "the Caltech campus lot", "jpl": "the JPL lot", "office001": "the office lot"}.get(
        site_id, f"the {site_id} site"
    )
    when = f" on {day_date}" if day_date else ""
    return rng.choice([
        f"We have {n} EVs plugged in at {where}{when}.",
        f"{n} cars are charging at {where}{when}, and here is what each one needs.",
        f"Here is today's charging list for {where}{when}. There are {n} vehicles.",
        f"{where.capitalize()} has {n} EVs parked{when}.",
    ])


_SESSION_TEMPLATES: Tuple[str, ...] = (
    "{label} plugs in at {arr} and unplugs at {dep}, and it needs {energy} through a {power} connector.",
    "{label} needs {energy} and is parked from {arr} until {dep} on a {power} charger.",
    "{label}: arrives {arr}, leaves {dep}, {energy}, {power} maximum.",
    "The driver of {label} arrives at {arr}, has to leave by {dep}, and wants {energy} at up to {power}.",
    "{label} sits on a {power} station between {arr} and {dep} and asks for {energy}.",
    "From {arr} to {dep}, {label} occupies a {power} charger and requires {energy}.",
    "{label} is there from {arr} to {dep}; give it {energy}, and its plug tops out at {power}.",
)


def _session_sentence(rng: random.Random, label: str, session: Session, day: DaySessions) -> str:
    """One car, described so that arrival is always written before departure."""
    template = rng.choice(_SESSION_TEMPLATES)
    return template.format(
        label=label,
        arr=rng.choice(time_phrases(session.arrival_idx, day.n_steps, day.dt_hours)),
        dep=rng.choice(time_phrases(session.departure_idx, day.n_steps, day.dt_hours)),
        energy=rng.choice(energy_phrases(session.energy_kwh)),
        power=rng.choice(power_phrases(session.max_power_kw)),
    )


_TASK_SENTENCES: Tuple[str, ...] = (
    "Work out the charging plan with the smallest energy bill.",
    "Schedule the charging so the total energy cost is as low as possible.",
    "Give me the cheapest way to charge all of this.",
    "Plan the charging to minimise what we pay for the energy.",
)


# --------------------------------------------------------------------------- solving


@dataclass(frozen=True)
class _Solved:
    """The optimum of one day at one cap, and the quantities answers are taken from."""

    cost_usd: float
    unmet_kwh: float
    requested_kwh: float
    delivered_kwh: float
    pct_energy_served: float
    peak_kw: float
    unmet_per_session: Tuple[float, ...]
    n_fully_served: int


_SOLVE_CACHE: Dict[Tuple[Any, ...], _Solved] = {}


def _solve_key(
    day: DaySessions, site_cap_kw: float, peak_price: float, off_peak_price: float
) -> Tuple[Any, ...]:
    """Content key of a solve: the same inputs always give the same _Solved."""
    return (
        day.n_steps,
        day.dt_hours,
        float(site_cap_kw),
        float(peak_price),
        float(off_peak_price),
        tuple(
            (s.session_id, s.arrival_idx, s.departure_idx, s.energy_kwh, s.max_power_kw)
            for s in day.sessions
        ),
    )


def solve_day(
    day: DaySessions,
    *,
    site_cap_kw: float = SITE_CAP_KW,
    peak_price: float = PEAK_PRICE,
    off_peak_price: float = OFF_PEAK_PRICE,
) -> _Solved:
    """Solve one day with the CVXPY solver and reduce it to answerable quantities.

    Results are memoised on the content of the inputs. The LP is a pure function
    of them, and generating a request solves the same day more than once (the
    congestion check, then the variant's own truth).

    Args:
        day: The structured day the request text describes.
        site_cap_kw: Site power cap stated in the request (kW).
        peak_price: Peak TOU rate stated in the request ($/kWh).
        off_peak_price: Off-peak TOU rate stated in the request ($/kWh).

    Returns:
        _Solved. ``cost_usd`` and ``unmet_kwh`` are the same for every optimal
        schedule; ``peak_kw`` and ``n_fully_served`` are not, and are recorded
        for the state summary only.

    Raises:
        ValueError: If the LP does not solve, which would leave no ground truth.
    """
    key = _solve_key(day, site_cap_kw, peak_price, off_peak_price)
    cached = _SOLVE_CACHE.get(key)
    if cached is not None:
        return cached

    site = SiteConfig(P_max_kw=float(site_cap_kw), n_steps=day.n_steps, dt_hours=day.dt_hours)
    tou = TOUConfig(
        rates_per_kwh=default_tou_rates(day.n_steps, peak_price=peak_price, off_peak_price=off_peak_price)
    )
    result = solve(day, site, tou)
    if not result.success:
        raise ValueError(f"the CVXPY solver returned {result.message!r}; no ground truth can be formed")

    schedule = result.schedule
    dt = day.dt_hours
    requested = float(sum(s.energy_kwh for s in day.sessions))
    unmet_total = float(total_unmet_kwh(schedule, day, dt))
    if unmet_total < SERVED_TOL_KWH:
        unmet_total = 0.0
    per_session: List[float] = []
    for i, sess in enumerate(day.sessions):
        delivered_i = float(np.sum(schedule[i, :]) * dt) if i < schedule.shape[0] else 0.0
        shortfall = max(0.0, float(sess.energy_kwh) - delivered_i)
        per_session.append(0.0 if shortfall < SERVED_TOL_KWH else shortfall)
    delivered = requested - unmet_total
    pct = 100.0 * delivered / requested if requested > 0 else 0.0
    solved = _Solved(
        cost_usd=float(total_cost(schedule, tou, dt)),
        unmet_kwh=unmet_total,
        requested_kwh=requested,
        delivered_kwh=delivered,
        pct_energy_served=pct,
        peak_kw=float(peak_load_kw(schedule)),
        unmet_per_session=tuple(per_session),
        n_fully_served=sum(1 for u in per_session if u <= 0.0),
    )
    _SOLVE_CACHE[key] = solved
    return solved


def state_summary(solved: _Solved, day: DaySessions, site_cap_kw: float) -> Dict[str, Any]:
    """Resulting-state summary stored as the truth of a state-kind request.

    Stored, never compared. ``peak_kw`` and ``n_sessions_fully_served`` depend on
    which optimal schedule the solver happened to return and must not be turned
    into an answer check; the note says so next to them.
    """
    return {
        "cost_usd": round(solved.cost_usd, 4),
        "unmet_kwh": round(solved.unmet_kwh, 4),
        "requested_kwh": round(solved.requested_kwh, 4),
        "pct_energy_served": round(solved.pct_energy_served, 4),
        "peak_kw": round(solved.peak_kw, 4),
        "n_sessions": len(day.sessions),
        "n_sessions_fully_served": solved.n_fully_served,
        "site_cap_kw": float(site_cap_kw),
        "note": (
            "resulting-state summary of the CVXPY optimum, stored and never compared; "
            "peak_kw and n_sessions_fully_served differ between equally optimal schedules"
        ),
    }


def capacity_shortfall_indices(day: DaySessions) -> List[int]:
    """Positions of cars asking for more than their plug can deliver while parked.

    ``energy_kwh > max_power_kw * dwell_hours`` cannot be satisfied by any
    schedule, whatever the site cap does, so this set is the same for every
    solver and every optimum. It is empty on all twenty committed fixture days.
    """
    out: List[int] = []
    for i, s in enumerate(day.sessions):
        deliverable = float(s.max_power_kw) * (s.departure_idx - s.arrival_idx) * day.dt_hours
        if float(s.energy_kwh) > deliverable + 1e-6:
            out.append(i)
    return out


def _sessions_active_at(day: DaySessions, step: int) -> int:
    return sum(1 for s in day.sessions if s.arrival_idx <= step < s.departure_idx)


def _unambiguous_count_step(day: DaySessions, rng: random.Random) -> Optional[int]:
    """A step where no car arrives or departs, so "plugged in at T" has one reading.

    Availability is half-open, ``[arrival_idx, departure_idx)``, so a car leaving
    exactly at the stated time is not plugged in at it while a car arriving
    exactly then is. Those two steps are skipped rather than asked about.
    """
    boundaries = {s.arrival_idx for s in day.sessions} | {s.departure_idx for s in day.sessions}
    candidates = [
        t for t in range(day.n_steps)
        if t not in boundaries and _sessions_active_at(day, t) >= 2
    ]
    if not candidates:
        return None
    return rng.choice(candidates)


# --------------------------------------------------------------------------- questions


@dataclass(frozen=True)
class _Question:
    """What a variant adds to the request text, and the truth it is scored on."""

    text: str
    truth: Any
    detail: str
    tolerance: Optional[float] = None


@dataclass(frozen=True)
class _Facts:
    """Everything a question builder may use, all of it already computed."""

    day: DaySessions
    labels: Tuple[str, ...]
    solved: _Solved
    site_cap_kw: float


def _q_cost(rng: random.Random, facts: _Facts) -> Optional[_Question]:
    if not facts.day.sessions:
        return None
    text = rng.choice([
        "What does that cheapest plan cost for the day? Give the total in dollars, to the cent.",
        "Tell me what the day's electricity bill comes to under that plan, in dollars and cents.",
        "How much do we pay for the energy in total? Answer in dollars, to two decimals.",
    ])
    return _Question(text, round(facts.solved.cost_usd, 2), "total energy cost of the CVXPY optimum ($)")


def _q_unmet(rng: random.Random, facts: _Facts) -> Optional[_Question]:
    if not facts.day.sessions:
        return None
    text = rng.choice([
        "How much of the requested energy cannot be delivered? Answer in kWh, to two decimals.",
        "Tell me how many kWh are left undelivered at the end of the day, to two decimals.",
        "How much energy goes undelivered under that plan? Give the number of kWh.",
    ])
    return _Question(text, round(facts.solved.unmet_kwh, 2), "total unmet energy of the CVXPY optimum (kWh)")


def _q_served_share(rng: random.Random, facts: _Facts) -> Optional[_Question]:
    if facts.solved.requested_kwh <= 0:
        return None
    text = rng.choice([
        "What share of the energy the drivers asked for actually gets delivered? Give a percentage to two decimals.",
        "Tell me what percentage of the requested energy is delivered, to two decimals.",
        "Of all the energy requested, what percentage does the plan deliver? Answer as a percentage to two decimals.",
    ])
    return _Question(
        text,
        round(facts.solved.pct_energy_served, 2),
        "100 * delivered / requested energy at the CVXPY optimum (%)",
    )


def _q_feasible(rng: random.Random, facts: _Facts) -> Optional[_Question]:
    if not facts.day.sessions:
        return None
    text = rng.choice([
        "Can every car leave with all the energy it asked for? Answer yes or no.",
        "Is it possible to serve every car in full before it leaves? Start your answer with yes or no.",
        "Does anyone drive off short? Answer yes if every car gets its full request, no otherwise.",
    ])
    truth = "yes" if facts.solved.unmet_kwh <= SERVED_TOL_KWH else "no"
    return _Question(text, truth, "yes when the CVXPY optimum leaves no unmet energy")


def _q_total_energy(rng: random.Random, facts: _Facts) -> Optional[_Question]:
    if not facts.day.sessions:
        return None
    text = rng.choice([
        "Before that, add up what the drivers are asking for and tell me the total in kWh, to two decimals.",
        "Also tell me the total energy requested across all the cars, in kWh to two decimals.",
        "What do the requests add up to? Give the total in kWh, to two decimals.",
    ])
    return _Question(
        text,
        round(facts.solved.requested_kwh, 2),
        "sum of the requested energies of the day (kWh), stated in mixed units in the text",
    )


def _q_plugged_in_at(rng: random.Random, facts: _Facts) -> Optional[_Question]:
    step = _unambiguous_count_step(facts.day, rng)
    if step is None:
        return None
    when = rng.choice(time_phrases(step, facts.day.n_steps, facts.day.dt_hours))
    text = rng.choice([
        f"Also, how many cars are plugged in at {when}? Give a whole number.",
        f"Tell me as well how many of them are connected at {when}, as a number.",
        f"One more thing: how many vehicles are parked on a charger at {when}?",
    ])
    return _Question(
        text,
        _sessions_active_at(facts.day, step),
        f"cars whose window covers step {step}, no car arrives or departs at that step",
    )


def _q_largest_request(rng: random.Random, facts: _Facts) -> Optional[_Question]:
    if len(facts.day.sessions) < 2:
        return None
    order = sorted(range(len(facts.day.sessions)), key=lambda i: -facts.day.sessions[i].energy_kwh)
    top, runner_up = order[0], order[1]
    if facts.day.sessions[top].energy_kwh - facts.day.sessions[runner_up].energy_kwh <= 0.01:
        return None  # a tie has no single right answer
    text = rng.choice([
        "Which car is asking for the most energy? Name it.",
        "Tell me which of them wants the largest amount of energy.",
        "Which vehicle has the biggest energy request? Give its label.",
    ])
    return _Question(
        text,
        facts.labels[top],
        "the car with the strictly largest requested energy in the text",
    )


def _q_capacity_shortfall(rng: random.Random, facts: _Facts) -> Optional[_Question]:
    idx = capacity_shortfall_indices(facts.day)
    if not idx or len(idx) > 5:
        return None  # nothing to name, or too many to name in a sentence
    text = rng.choice([
        "Which cars are asking for more than their own charger can deliver in the time they are parked? List them.",
        "Name the cars that cannot be filled in the time they have, whatever the schedule.",
        "Which vehicles ask for more energy than their plug can possibly give them before they leave?",
    ])
    return _Question(
        text,
        [facts.labels[i] for i in idx],
        "cars whose requested energy exceeds max_power_kw * dwell hours",
    )


def _q_state(rng: random.Random, facts: _Facts) -> Optional[_Question]:
    return _Question("", state_summary(facts.solved, facts.day, facts.site_cap_kw), "prescribes an operation only")


_QUESTION_BUILDERS: Dict[str, Callable[[random.Random, _Facts], Optional[_Question]]] = {
    "schedule_only": _q_state,
    "schedule_under_cap": _q_state,
    "cost_question": _q_cost,
    "unmet_question": _q_unmet,
    "served_share": _q_served_share,
    "feasible_yesno": _q_feasible,
    "total_energy_requested": _q_total_energy,
    "cars_plugged_in_at": _q_plugged_in_at,
    "largest_request_car": _q_largest_request,
    "capacity_shortfall_cars": _q_capacity_shortfall,
}


# --------------------------------------------------------------------------- rendering


def _ordered_sessions(day: DaySessions, rng: random.Random) -> List[Session]:
    """The cars in the order the text will enumerate them (a seeded shuffle)."""
    order = list(day.sessions)
    rng.shuffle(order)
    return order


def render_request(
    day: DaySessions,
    *,
    rng: random.Random,
    site_id: str,
    day_date: str,
    site_cap_kw: float,
    lowered_cap: bool,
    peak_price: float,
    off_peak_price: float,
    labels: Sequence[str],
    question_text: str,
) -> str:
    """Render one day as free-form English.

    The layout, the sentence template of every car, and every time, energy and
    power expression are drawn from ``rng``, so the same day and seed always give
    the same text and two seeds give genuinely different text. ``day`` must
    already be in text order; ``labels[i]`` names ``day.sessions[i]``.
    """
    n = len(day.sessions)
    preamble = _preamble(rng, n, site_id, day_date)
    lines = [
        _session_sentence(rng, labels[i].replace("-", " "), s, day)
        for i, s in enumerate(day.sessions)
    ]
    bulleted = rng.random() < 0.35
    body = "\n".join(f"- {line}" for line in lines) if bulleted else " ".join(lines)
    cap = _cap_sentence(rng, site_cap_kw, lowered_cap)
    price = _price_sentences(rng, peak_price, off_peak_price)
    task = rng.choice(_TASK_SENTENCES)
    tail = f"{task} {question_text}".strip()

    layout = rng.randrange(3)
    if layout == 0:
        blocks = [preamble, body, f"{cap} {price}", tail]
    elif layout == 1:
        blocks = [f"{preamble} {cap} {price}", body, tail]
    else:
        blocks = [f"{task} {preamble}", body, f"{cap} {price}", question_text.strip() or task]
    return "\n\n".join(b for b in blocks if b.strip())


# --------------------------------------------------------------------------- generation


def _posable(variant: str, rng: random.Random, facts: _Facts) -> Optional[_Question]:
    builder = _QUESTION_BUILDERS.get(variant)
    if builder is None:
        raise ValueError(f"Unknown variant {variant!r}. Allowed: {list(VARIANTS)}")
    return builder(rng, facts)


def build_request(
    day: DaySessions,
    *,
    seed: int = 0,
    variant: Optional[str] = None,
    site_id: str = "caltech",
    day_date: Any = "",
    site_cap_kw: float = SITE_CAP_KW,
    peak_price: float = PEAK_PRICE,
    off_peak_price: float = OFF_PEAK_PRICE,
) -> EVRequest:
    """Build one request from one structured day.

    Args:
        day: The day to describe. Its sessions are shuffled into text order; the
            returned ``request.day`` holds them in that order with their original
            ids, so position matching in ``evaluation/formulation.py`` is correct.
        seed: Generator seed. The same day, seed and variant always render the
            same text.
        variant: One of VARIANTS. None asks for the first variant of the default
            rotation that can be posed on this day.
        site_id: Site named in the text.
        day_date: Calendar day, used in the text and the id.
        site_cap_kw: Site cap the text states; ignored for schedule_under_cap,
            which picks a lower one from LOWER_CAPS_KW.
        peak_price: Peak TOU rate stated in the text ($/kWh).
        off_peak_price: Off-peak TOU rate stated in the text ($/kWh).

    Returns:
        EVRequest with its ground-truth answer already computed from the solver.

    Raises:
        ValueError: If the variant is unknown, or if it cannot be posed on this
            day (an empty day admits only the state variants).
    """
    date_text = day_date.isoformat() if isinstance(day_date, _date) else str(day_date or "")
    wanted = variant or VARIANTS[0]
    rng = _stable_rng(site_id, date_text, wanted, seed)

    ordered = _ordered_sessions(day, rng)
    text_day = DaySessions(sessions=ordered, n_steps=day.n_steps, dt_hours=day.dt_hours)
    labels = tuple(f"EV-{i + 1}" for i in range(len(ordered)))

    lowered = wanted == "schedule_under_cap"
    cap = rng.choice(LOWER_CAPS_KW) if lowered else float(site_cap_kw)
    solved = solve_day(text_day, site_cap_kw=cap, peak_price=peak_price, off_peak_price=off_peak_price)
    facts = _Facts(day=text_day, labels=labels, solved=solved, site_cap_kw=cap)

    question = _posable(wanted, rng, facts)
    if question is None:
        raise ValueError(f"variant {wanted!r} cannot be posed on {site_id} {date_text or 'this day'}")

    text = render_request(
        text_day,
        rng=rng,
        site_id=site_id,
        day_date=date_text,
        site_cap_kw=cap,
        lowered_cap=lowered,
        peak_price=peak_price,
        off_peak_price=off_peak_price,
        labels=labels,
        question_text=question.text,
    )
    source_ids = tuple(s.session_id for s in ordered)
    return EVRequest(
        id=f"{site_id}-{date_text or 'day'}-{wanted}-s{seed}",
        site_id=site_id,
        date=date_text,
        seed=int(seed),
        variant=wanted,
        kind=ANSWER_KIND_BY_VARIANT[wanted],
        text=text,
        day=text_day,
        labels=labels,
        site_cap_kw=float(cap),
        peak_price=float(peak_price),
        off_peak_price=float(off_peak_price),
        question=question.text,
        truth=question.truth,
        tolerance=question.tolerance,
        synthetic=any(str(i).startswith("SYNTH-") for i in source_ids),
        source_session_ids=source_ids,
        detail=question.detail,
    )


def generate_requests(
    days: Sequence[Tuple[Any, DaySessions]],
    *,
    seed: int = 0,
    site_id: str = "caltech",
    variants: Optional[Sequence[str]] = None,
    site_cap_kw: float = SITE_CAP_KW,
    peak_price: float = PEAK_PRICE,
    off_peak_price: float = OFF_PEAK_PRICE,
) -> List[EVRequest]:
    """One request per day, with the variants spread over the days.

    Assignment is deterministic and depends only on the ordered ``days``. A day
    whose demand cannot be served in full takes the next of SHORTFALL_VARIANTS in
    rotation, because those are the questions whose answer is not trivial there;
    every other day takes the next variant of the full rotation. A variant that
    cannot be posed on its day (a tie for the largest request, no car short of
    charger capacity, an empty day) falls through the rotation to the next one
    that can, and the request records the variant actually used.

    Args:
        days: ``(date, DaySessions)`` pairs, in the order they should be walked.
        seed: Generator seed for the text.
        site_id: Site named in the text.
        variants: Rotation to use. Defaults to VARIANTS.
        site_cap_kw: Default site cap (kW) stated in the text.
        peak_price: Peak TOU rate stated in the text ($/kWh).
        off_peak_price: Off-peak TOU rate stated in the text ($/kWh).

    Returns:
        A list of EVRequest, one per day, in the order given.
    """
    rotation = list(variants) if variants else list(VARIANTS)
    unknown = set(rotation) - set(VARIANTS)
    if unknown:
        raise ValueError(f"Unknown variants: {sorted(unknown)}. Allowed: {list(VARIANTS)}")
    shortfall = [v for v in SHORTFALL_VARIANTS if v in rotation]

    out: List[EVRequest] = []
    n_plain = 0
    n_short = 0
    for day_date, day in days:
        congested = False
        if day.sessions:
            congested = solve_day(
                day, site_cap_kw=site_cap_kw, peak_price=peak_price, off_peak_price=off_peak_price
            ).unmet_kwh > SERVED_TOL_KWH
        if congested and shortfall:
            first = shortfall[n_short % len(shortfall)]
            n_short += 1
        else:
            first = rotation[n_plain % len(rotation)]
            n_plain += 1
        start = rotation.index(first) if first in rotation else 0
        request: Optional[EVRequest] = None
        for step in range(len(rotation)):
            candidate = rotation[(start + step) % len(rotation)]
            try:
                request = build_request(
                    day,
                    seed=seed,
                    variant=candidate,
                    site_id=site_id,
                    day_date=day_date,
                    site_cap_kw=site_cap_kw,
                    peak_price=peak_price,
                    off_peak_price=off_peak_price,
                )
                break
            except ValueError:
                continue
        if request is None:
            raise ValueError(f"no variant of {rotation} can be posed on {site_id} {day_date}")
        out.append(request)
    return out


def load_benchmark_requests(
    *,
    seed: int = 0,
    site_id: str = "caltech",
    dates: Optional[Sequence[_date]] = None,
    source: str = "fixture",
    n_steps: int = 96,
    dt_hours: float = 0.25,
    **kwargs: Any,
) -> List[EVRequest]:
    """Requests for the frozen benchmark days, offline by default.

    Args:
        seed: Generator seed for the text.
        site_id: ACN site.
        dates: Days to use. Defaults to ``data.benchmark.store.BENCHMARK_DATES``.
        source: Passed to ``data.loader.loader.load_sessions``; "fixture" (the
            default) reads the committed synthetic days and never touches the
            network, "cache" reads the frozen real days.
        n_steps: Horizon length in steps.
        dt_hours: Step duration in hours.
        **kwargs: Forwarded to ``generate_requests`` (cap, prices, variants).

    Returns:
        One EVRequest per day.
    """
    from data.benchmark import store
    from data.loader.loader import load_sessions

    wanted = list(dates) if dates else list(store.BENCHMARK_DATES)
    days = [
        (d, load_sessions(site_id, d, n_steps=n_steps, dt_hours=dt_hours, source=source))
        for d in wanted
    ]
    return generate_requests(days, seed=seed, site_id=site_id, **kwargs)


def compute_ground_truth(request: EVRequest) -> Dict[str, Any]:
    """Re-solve the request's own day and return its ground-truth quantities.

    The request already carries the answer it is scored on; this re-derives the
    full picture for a results file, and lets a harness check that the committed
    truth still matches the solver.
    """
    solved = solve_day(
        request.day,
        site_cap_kw=request.site_cap_kw,
        peak_price=request.peak_price,
        off_peak_price=request.off_peak_price,
    )
    return {
        "answer": request.truth,
        "kind": request.kind,
        "state": state_summary(solved, request.day, request.site_cap_kw),
        "capacity_shortfall": [request.labels[i] for i in capacity_shortfall_indices(request.day)],
        "synthetic": request.synthetic,
        "limitations": list(LIMITATIONS),
    }


# --------------------------------------------------------------------------- extraction

_NUM = r"[-+]?\d[\d,]*(?:\.\d+)?"
_WORD_NUMBERS: Dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20,
}


def _f(raw: Optional[str]) -> Optional[float]:
    """Float value of a matched number, tolerating "$" and thousands separators."""
    if raw is None:
        return None
    try:
        return float(raw.replace(",", "").replace("$", "").strip())
    except ValueError:
        return None


def _c(pattern: str) -> "re.Pattern[str]":
    return re.compile(pattern.replace("NUM", _NUM), re.IGNORECASE)


_ANSWER_LINE = _c(r"\banswer\s*[:=]\s*\$?\s*(?P<num>NUM)")

_COST_PATTERNS = (
    _ANSWER_LINE,
    _c(r"(?:cost|bill|total|charge|price)[^.\n]{0,60}?\$\s*(?P<num>NUM)(?!\s*(?:/|per\s+)\s*kwh)"),
    _c(r"\$\s*(?P<num>NUM)(?!\s*(?:/|per\s+)\s*kwh)"),
    _c(r"(?P<num>NUM)\s*(?:dollars|usd)\b"),
)

# "cannot be delivered", "will not be delivered" and the like say the same thing
# as "undelivered"; a reply is not wrong for phrasing it as a verb.
_UNDELIVERED = (
    r"(?:un(?:met|delivered|served)|shortfall|short|missing|left over|left undelivered|"
    r"(?:not|cannot|can't|could ?n[o']t|will not|won't|unable to)[^.\n]{0,20}?deliver)"
)

_UNMET_PATTERNS = (
    _c(r"\banswer\s*[:=]\s*(?P<num>NUM)\s*(?P<unit>kwh|kilowatt-hours?|wh|watt-hours?)?"),
    _c(r"(?P<num>NUM)\s*(?P<unit>kwh|kilowatt-hours?|wh|watt-hours?)[^.\n]{0,60}?" + _UNDELIVERED),
    _c(_UNDELIVERED + r"[^.\n]{0,60}?(?P<num>NUM)\s*(?P<unit>kwh|kilowatt-hours?|wh|watt-hours?)?"),
)

_ENERGY_SUM_PATTERNS = (
    _c(r"\banswer\s*[:=]\s*(?P<num>NUM)\s*(?P<unit>kwh|kilowatt-hours?|wh|watt-hours?)?"),
    _c(r"(?:total|combined|altogether|sum|in total|requested)[^.\n]{0,60}?"
       r"(?P<num>NUM)\s*(?P<unit>kwh|kilowatt-hours?|wh|watt-hours?)"),
    _c(r"(?P<num>NUM)\s*(?P<unit>kwh|kilowatt-hours?|wh|watt-hours?)[^.\n]{0,40}?"
       r"(?:in total|altogether|requested|total)"),
    _c(r"(?P<num>NUM)\s*(?P<unit>kwh|kilowatt-hours?)"),
)

# Either voice: "84 % is delivered" and "it delivers 84 %".
_SERVED_WORDS = r"(?:serve[sd]?|deliver(?:s|ed|ing)?|satisf(?:y|ies|ied)|met|charged|fulfill?(?:s|ed)?)"

_PCT_PATTERNS = (
    _ANSWER_LINE,
    _c(r"(?P<num>NUM)\s*(?:%|per\s?cent|percent)[^.\n]{0,60}?" + _SERVED_WORDS),
    _c(_SERVED_WORDS + r"[^.\n]{0,60}?(?P<num>NUM)\s*(?:%|per\s?cent|percent)"),
    _c(r"(?P<num>NUM)\s*(?:%|per\s?cent|percent)"),
)

_COUNT_PATTERNS = (
    _c(r"\banswer\s*[:=]\s*(?P<num>\d+)"),
    _c(r"(?P<num>\d+)\s*(?:evs?|cars?|vehicles?|sessions?)\b[^.\n]{0,60}?"
       r"(?:plugged|connected|charging|parked|on charge)"),
    _c(r"(?:plugged in|connected|charging|parked)[^.\n]{0,60}?(?P<num>\d+)\s*"
       r"(?:evs?|cars?|vehicles?|sessions?)?"),
    _c(r"(?:there are|there were|the count is|the answer is|i count)\s*(?P<num>\d+)"),
)

_WORD_COUNT_RE = re.compile(
    r"\b(?P<word>" + "|".join(_WORD_NUMBERS) + r")\s+(?:evs?|cars?|vehicles?|sessions?)\b",
    re.IGNORECASE,
)

# Phrases that state a zero shortfall without writing a digit.
_ZERO_PHRASES = (
    _c(r"\b(?:no|none|zero|nothing)\b[^.\n]{0,40}?(?:unmet|undelivered|left undelivered|shortfall|unserved)"),
    _c(r"(?:unmet|undelivered|shortfall|unserved)[^.\n]{0,30}?\b(?:is|are|was|were)?\s*(?:zero|none|nil)\b"),
    _c(r"(?:every|all)\s+(?:the\s+)?(?:cars?|evs?|vehicles?|sessions?)[^.\n]{0,40}?"
       r"(?:fully|completely)\s+(?:served|charged|satisfied|met)"),
)

_YES_PATTERNS = (
    _c(r"(?:^|\n)\s*(?:answer\s*[:=]\s*)?yes\b"),
    _c(r"\byes\s*[,.]"),
    _c(r"(?:every|each)\s+(?:car|ev|vehicle)[^.\n]{0,40}?(?:can|will)\s+(?:be\s+)?(?:fully\s+)?"
       r"(?:served|charged|satisfied|met|leave)"),
    _c(r"all\s+(?:\d+\s+)?(?:the\s+)?(?:cars|evs|vehicles)[^.\n]{0,40}?(?:can|will)\s+be\s+"
       r"(?:fully\s+)?(?:served|charged|satisfied|met)"),
)

_NO_PATTERNS = (
    _c(r"(?:^|\n)\s*(?:answer\s*[:=]\s*)?no\b"),
    _c(r"\bno\s*[,.]"),
    _c(r"\bnot\s+(?:all|every|everyone)\b"),
    _c(r"(?:cannot|can't|will not|won't)\s+(?:all\s+)?be\s+(?:fully\s+)?(?:served|charged|satisfied|met)"),
    _c(r"(?:some|\d+)\s+(?:cars|evs|vehicles|sessions)[^.\n]{0,40}?"
       r"(?:cannot|can't|will not|won't|fall short|are short|go short)"),
)

_LABEL_RE = re.compile(r"\bev[\s\-_#]?(?P<n>\d{1,3})\b", re.IGNORECASE)
# Sentence end, or a line break. A period between two digits is a decimal point,
# not a full stop: splitting "needs 12.75 kWh" there would tear the energy off
# the car it belongs to.
_SENTENCE_SPLIT = re.compile(r"(?<!\d)[.!?]+(?=\s|$)|\n+")

_SHORTFALL_ANCHORS = _c(
    r"(?:cannot|can't|unable|impossible|more than|exceeds?|short|shortfall|not\s+(?:be\s+)?"
    r"(?:fully\s+)?(?:served|charged|filled)|beyond)"
)
_LARGEST_ANCHORS = _c(r"(?:most|largest|biggest|highest|greatest|maximum|max\b)")


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _as_kwh(value: Optional[float], unit: Optional[str]) -> Optional[float]:
    """Normalise a matched energy to kWh; a reply in Wh is still a right answer."""
    if value is None:
        return None
    if unit and unit.lower().replace("-", " ").startswith(("wh", "watt hour")):
        return value / 1000.0
    return value


def _first_match(text: str, patterns: Sequence["re.Pattern[str]"], *, as_energy: bool = False) -> Optional[float]:
    """First match of the highest-priority pattern that matches (see LIMITATIONS)."""
    for pattern in patterns:
        match = pattern.search(text)
        if match is None:
            continue
        value = _f(match.group("num"))
        if value is None:
            continue
        if as_energy:
            unit = match.groupdict().get("unit")
            return _as_kwh(value, unit)
        return value
    return None


def _extract_count(text: str) -> Optional[float]:
    value = _first_match(text, _COUNT_PATTERNS)
    if value is not None:
        return value
    match = _WORD_COUNT_RE.search(text)
    if match is not None:
        return float(_WORD_NUMBERS[match.group("word").lower()])
    return None


def _extract_yes_no(text: str) -> Optional[str]:
    """"yes" / "no", or None when the reply says neither or both at once."""
    yes_at = min((m.start() for m in (p.search(text) for p in _YES_PATTERNS) if m), default=None)
    no_at = min((m.start() for m in (p.search(text) for p in _NO_PATTERNS) if m), default=None)
    if yes_at is None and no_at is None:
        return None
    if yes_at is None:
        return "no"
    if no_at is None:
        return "yes"
    if yes_at == no_at:
        return None
    return "yes" if yes_at < no_at else "no"


def _labels_in(text: str) -> List[str]:
    seen: List[str] = []
    for match in _LABEL_RE.finditer(text):
        label = f"EV-{int(match.group('n'))}"
        if label not in seen:
            seen.append(label)
    return seen


def _extract_labels(text: str, anchors: "re.Pattern[str]", *, single: bool) -> Optional[Any]:
    """Labels named in the sentences that actually answer the question."""
    for sentence in _sentences(text):
        if not anchors.search(sentence):
            continue
        labels = _labels_in(sentence)
        if labels:
            return labels[0] if single else sorted(labels)
    return None


def extract_answer(reply_text: Optional[str], request: EVRequest) -> Any:
    """Pull the answer to ``request`` out of a system's reply.

    Args:
        reply_text: The system's free-form reply.
        request: The request it is answering; the variant decides what is looked
            for and in which units.

    Returns:
        The extracted answer (float, int, "yes"/"no", a label, or a list of
        labels), or None when the reply does not answer the question. None is
        not a neutral outcome: ``outcome.check_answer`` scores it as a failure.
    """
    if not reply_text or not str(reply_text).strip():
        return None
    text = str(reply_text)
    variant = request.variant

    if variant == "cost_question":
        return _first_match(text, _COST_PATTERNS)
    if variant == "unmet_question":
        value = _first_match(text, _UNMET_PATTERNS, as_energy=True)
        if value is not None:
            return value
        return 0.0 if any(p.search(text) for p in _ZERO_PHRASES) else None
    if variant == "served_share":
        return _first_match(text, _PCT_PATTERNS)
    if variant == "feasible_yesno":
        return _extract_yes_no(text)
    if variant == "total_energy_requested":
        return _first_match(text, _ENERGY_SUM_PATTERNS, as_energy=True)
    if variant == "cars_plugged_in_at":
        return _extract_count(text)
    if variant == "largest_request_car":
        return _extract_labels(text, _LARGEST_ANCHORS, single=True)
    if variant == "capacity_shortfall_cars":
        return _extract_labels(text, _SHORTFALL_ANCHORS, single=False)
    return None  # state variants ask nothing


def request_answer(request: EVRequest, reply_text: Optional[str] = None) -> RequestAnswer:
    """The RequestAnswer ``evaluation/outcome.py`` consumes for this day.

    Args:
        request: The request the system was given.
        reply_text: The system's reply, or None when it produced none.

    Returns:
        RequestAnswer with the ground truth, the extracted answer, and
        ``checkable`` False for a state-kind request, whose truth is the
        resulting-state summary and is stored rather than compared.
    """
    checkable = request.checkable
    given = extract_answer(reply_text, request) if checkable else None
    detail = request.question or request.detail
    return RequestAnswer(
        kind=request.kind,
        truth=request.truth,
        given=given,
        checkable=checkable,
        tolerance=request.tolerance,
        detail=detail,
    )


# --------------------------------------------------------------------------- reference parser

_TIME_RE = re.compile(
    r"(?P<p12>\b(?P<h12>\d{1,2})(?::(?P<m12>[0-5]\d))?\s*(?P<mer>am|pm)\b)"
    r"|(?P<iso>\b(?P<hiso>\d{1,2}):(?P<miso>[0-5]\d)\b)"
    r"|(?P<word>\b(?:(?P<rel>quarter past|half past|a quarter to|quarter to|half)\s+)?"
    r"(?P<hw>twelve|eleven|ten|nine|eight|seven|six|five|four|three|two|one|midnight|noon|midday)\b"
    r"(?P<oclock>\s+o'clock)?"
    r"(?P<eod>\s+at the end of the day)?"
    r"(?P<part>\s+(?:in the morning|in the afternoon|in the evening|at night))?)",
    re.IGNORECASE,
)
_REF_ENERGY_RE = _c(r"(?P<num>NUM)\s*(?P<unit>kwh|kilowatt-hours?|kilowatt hours?|wh|watt-hours?|watt hours?)\b")
_REF_POWER_RE = _c(r"(?P<num>NUM)\s*(?P<unit>kw|kilowatts?|w|watts?)\b")
_REF_CAP_RE = _c(
    r"(?:cap|limit|limited|exceed|under|below|at or below|never pull more than|stay under|"
    r"transformer|feeder|total draw)[^.\n]{0,60}?(?P<num>NUM)\s*(?P<unit>kw|kilowatts?|w|watts?)\b"
)
_REF_DOLLAR_RATE_RE = _c(r"\$\s*(?P<num>NUM)\s*(?:/|per\s+)\s*kwh")
_REF_CENT_RATE_RE = _c(r"(?P<num>NUM)\s*cents?\s*(?:a|per|/)\s*kwh")


def _hour_word_value(word: str) -> Optional[int]:
    """Hour named by a spoken word: "twelve" is 12, not 0; "midnight" is 0."""
    lowered = word.lower()
    if lowered in ("noon", "midday", "twelve"):
        return 12
    if lowered == "midnight":
        return 0
    if lowered in _HOUR_WORDS:
        return _HOUR_WORDS.index(lowered)
    return None


def _time_from_match(match: "re.Match[str]") -> Optional[float]:
    """Fractional hours from midnight for one matched time phrase."""
    groups = match.groupdict()
    if groups.get("p12"):
        hour = int(groups["h12"]) % 12
        if (groups["mer"] or "").lower() == "pm":
            hour += 12
        return hour + int(groups["m12"] or 0) / 60.0
    if groups.get("iso"):
        return int(groups["hiso"]) + int(groups["miso"]) / 60.0

    word, rel = groups.get("hw") or "", (groups.get("rel") or "").lower()
    part = (groups.get("part") or "").strip().lower()
    base = _hour_word_value(word)
    if base is None:
        return None
    standalone = word.lower() in ("noon", "midday", "midnight")
    if not rel and not groups.get("oclock") and not part and not standalone:
        return None  # a bare hour word in prose is not a time
    if groups.get("eod") and word.lower() == "midnight":
        return 24.0
    hour = base
    if part in ("in the afternoon", "in the evening", "at night") and 1 <= hour <= 11:
        hour += 12
    if rel in ("a quarter to", "quarter to"):
        if word.lower() == "noon":
            return 11.75
        if word.lower() == "midnight":
            return 23.75
        return (hour - 1) + 0.75
    if rel == "quarter past":
        return hour + 0.25
    if rel in ("half past", "half"):
        return hour + 0.5
    return float(hour)


def parse_time_phrase(text: str) -> Optional[float]:
    """First clock time in ``text`` as fractional hours, or None."""
    for match in _TIME_RE.finditer(text):
        value = _time_from_match(match)
        if value is not None:
            return value
    return None


def reference_parse(text: str) -> Any:
    """Rule-based extraction of a request's parameters, for tests and a floor.

    This parser knows the vocabulary ``render_request`` draws from, so a perfect
    score here means the generated text is unambiguous, **not** that parsing
    free-form English is easy. It is the round-trip check the tests assert and a
    rule-based floor for the formulation column; it is not a general parser and
    must never be reported as an LLM-free baseline on text this module did not
    write.

    Args:
        text: A request rendered by ``render_request``.

    Returns:
        ``agent.parse.parse.ParsedProblem`` with one ParsedSession per car, in
        the order the text enumerates them and labelled "EV-1", "EV-2", ...
    """
    from agent.parse.parse import ParsedProblem, ParsedSession

    sessions: List[Any] = []
    for sentence in _sentences(text):
        labels = _LABEL_RE.findall(sentence)
        if len(labels) != 1:
            continue
        body = sentence
        energies: List[float] = []
        for match in _REF_ENERGY_RE.finditer(sentence):
            value = _as_kwh(_f(match.group("num")), match.group("unit"))
            if value is not None:
                energies.append(value)
        body = _REF_ENERGY_RE.sub(" ", sentence)  # so "12750 Wh" is not read as a power
        powers: List[float] = []
        for match in _REF_POWER_RE.finditer(body):
            value = _f(match.group("num"))
            if value is None:
                continue
            unit = match.group("unit").lower()
            powers.append(value / 1000.0 if unit in ("w", "watt", "watts") else value)
        times = [t for t in (_time_from_match(m) for m in _TIME_RE.finditer(sentence)) if t is not None]
        sessions.append(
            ParsedSession(
                arrival_hour=times[0] if len(times) > 0 else None,
                departure_hour=times[1] if len(times) > 1 else None,
                energy_kwh=energies[0] if energies else None,
                max_power_kw=powers[0] if powers else 7.2,
                session_id=f"EV-{len(sessions) + 1}",
                charger_id=f"charger-{len(sessions) + 1}",
            )
        )

    cap_match = _REF_CAP_RE.search(text)
    cap = SITE_CAP_KW
    if cap_match is not None:
        raw = _f(cap_match.group("num"))
        if raw is not None:
            cap = raw / 1000.0 if cap_match.group("unit").lower() in ("w", "watt", "watts") else raw
    rates = sorted(v for v in (_f(m.group("num")) for m in _REF_DOLLAR_RATE_RE.finditer(text)) if v is not None)
    cents = sorted(v for v in (_f(m.group("num")) for m in _REF_CENT_RATE_RE.finditer(text)) if v is not None)
    rates = rates or [c / 100.0 for c in cents]
    return ParsedProblem(
        sessions=sessions,
        n_steps=96,
        dt_hours=0.25,
        site_cap_kw=cap,
        peak_price=rates[-1] if rates else PEAK_PRICE,
        off_peak_price=rates[0] if rates else OFF_PEAK_PRICE,
    )


# --------------------------------------------------------------------------- persistence


def request_to_dict(request: EVRequest) -> Dict[str, Any]:
    """JSON-serialisable form of one request, day included."""
    payload = asdict(request)
    payload["day"] = {
        "sessions": [asdict(s) for s in request.day.sessions],
        "n_steps": request.day.n_steps,
        "dt_hours": request.day.dt_hours,
    }
    payload["labels"] = list(request.labels)
    payload["source_session_ids"] = list(request.source_session_ids)
    return payload


def request_from_dict(payload: Dict[str, Any]) -> EVRequest:
    """Inverse of ``request_to_dict``."""
    data = dict(payload)
    day = data.pop("day")
    data["day"] = DaySessions(
        sessions=[Session(**s) for s in day["sessions"]],
        n_steps=int(day["n_steps"]),
        dt_hours=float(day["dt_hours"]),
    )
    data["labels"] = tuple(data.get("labels") or ())
    data["source_session_ids"] = tuple(data.get("source_session_ids") or ())
    return EVRequest(**data)


def to_jsonl(requests: Sequence[EVRequest], path: Any) -> Path:
    """Write requests as one JSON object per line."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for request in requests:
            handle.write(json.dumps(request_to_dict(request), ensure_ascii=False) + "\n")
    return out


def from_jsonl(path: Any) -> List[EVRequest]:
    """Read requests written by ``to_jsonl``."""
    return [
        request_from_dict(json.loads(line))
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def summarise(requests: Sequence[EVRequest]) -> Dict[str, Any]:
    """Counts per variant and the checkable share, for a run's log."""
    by_variant: Dict[str, int] = {}
    for request in requests:
        by_variant[request.variant] = by_variant.get(request.variant, 0) + 1
    checkable = sum(1 for r in requests if r.checkable)
    total = len(requests)
    return {
        "total": total,
        "checkable": checkable,
        "state_only": total - checkable,
        "checkable_share": (checkable / total) if total else None,
        "by_variant": dict(sorted(by_variant.items())),
        "synthetic": sum(1 for r in requests if r.synthetic),
    }


def main(argv: Optional[List[str]] = None) -> int:
    """CLI: render the benchmark days as requests and write them to JSONL."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--site", default="caltech")
    parser.add_argument(
        "--source", default="fixture", choices=("fixture", "cache", "auto", "api"),
        help="'fixture' (default) uses the committed synthetic days and stays offline",
    )
    parser.add_argument("--limit", type=int, default=0, help="use only the first N benchmark days")
    parser.add_argument("--out", default=None, help="default: evaluation/requests_<site>.jsonl")
    parser.add_argument("--print-first", action="store_true", help="print the first rendered request")
    args = parser.parse_args(argv)

    from data.benchmark import store

    dates = list(store.BENCHMARK_DATES)
    if args.limit:
        dates = dates[: args.limit]
    requests = load_benchmark_requests(seed=args.seed, site_id=args.site, dates=dates, source=args.source)
    out = Path(args.out) if args.out else PROJECT_ROOT / "evaluation" / f"requests_{args.site}.jsonl"
    to_jsonl(requests, out)
    summary = summarise(requests)
    print(json.dumps(summary, indent=2))
    print(f"wrote {len(requests)} requests to {out}")
    if args.print_first and requests:
        print("\n" + requests[0].text)
        print(f"\n[{requests[0].variant}] truth = {requests[0].truth!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

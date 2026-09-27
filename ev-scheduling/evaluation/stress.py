"""Twenty stressed days, each with a failure the answer is required to declare.

Why the module exists
---------------------
The results table has an Escalated column: the share of days the system hands to
a person because verification failed and the answer said so. In
``power-flow-agent`` that column means something because the reference itself can
fail. Newton-Raphson does not converge, or a topology change isolates a bus, and
there is an objective failure to declare.

The EV linear program never fails. Its unmet-energy slack lets demand go
undelivered, so the site cap can be dropped from 50 kW to 15 kW and CVXPY still
returns a perfectly valid schedule: every gate condition E1 to E5 passes and
Escalated comes out zero by construction, which is what a smoke run showed on
every arm. The real failure on such a day is different in kind. The agent returns
the schedule and never says that, on 2018-10-15 at a 15 kW cap, more than 400 kWh
of the energy people asked for will not be delivered. Every number it did report
is true. The problem is the one it left out.

This module builds the days on which that failure can be observed, and records,
per day, what a correct answer has to declare. ``methods/agent/validate/gate.py``'s E6
(``shortfall_declared``) is the gate-side counterpart: it fails an answer that
hides a material shortfall. The two were written together.

The twenty items
----------------
One item per **real** frozen ACN day under ``data/benchmark/`` (10 to 87 sessions,
median 43). Nothing is invented: each item applies exactly one recorded
perturbation to one measured day, and the perturbation is stored in a form that
reproduces the perturbed day from the frozen file (``apply_perturbation``). The
classes rotate over ``data.benchmark.store.BENCHMARK_DATES``, five days each:

1. ``lowered_cap`` - the 50 kW site cap is stated as 20 kW or 15 kW. The answer
   must say the demand cannot all be met and by how much.
2. ``disabled_chargers`` - half the spaces are out of service, modelled exactly
   as ``methods/agent/llm_agent.py::_apply_what_if`` models them, by dropping those
   sessions' ``max_power_kw`` to ``DISABLED_POWER_KW``. The answer must say which
   sessions get nothing, and how much energy is undelivered.
3. ``impossible_deadline`` - the request asks whether everyone can be served by a
   stated time, chosen so that they provably cannot: the energy physically
   deliverable before the deadline, bounded above by
   ``store.deliverable_upper_bound_kwh``, is less than the energy asked for. The
   answer must say no, and why.
4. ``contradictory_request`` - one car's entry contradicts itself, either a
   departure stated before its arrival or an energy larger than its own connector
   can deliver in the window it is parked. The answer must say the request is
   malformed instead of inventing a plan around it.

Classes 3 and 4 are the interesting ones. There the failure is not arithmetic.
A system can produce a numerically perfect schedule for the well-formed part of
the day and still fail, because it never says the thing that matters. Class 4's
reversed-window items carry no shortfall signal at all: E6 is not applicable on
them, and the only thing that separates a right answer from a wrong one is
whether it names the malformed entry. That is the point of including them.

Ground truth
------------
Never asserted by hand. Every quantity in ``StressTruth`` is computed by running
the CVXPY solver, through ``evaluation.requests.solve_day``, on the **perturbed**
problem, plus two structural facts that are proved rather than solved: the
provably unservable sessions (``requests.capacity_shortfall_indices``, a car
asking for more than its own plug can deliver while parked, which no schedule can
satisfy) and the deadline bound (``store.deliverable_upper_bound_kwh``, an upper
bound on what any feasible schedule delivers). ``baseline_unmet_kwh`` is the same
day solved unperturbed at the site's own 50 kW cap, so a reader can tell the
shortfall the perturbation caused from the one the day already had.

``build_item`` applies two refusals, so the set cannot silently acquire a day
that tests nothing. There has to be a genuine failure to declare
(``has_failure``), and the perturbation has to be what caused it
(``perturbation_is_effective``). The second matters because several of the real
days already leave energy undelivered at the site's own 50 kW cap, up to 154 kWh
on 2018-10-15: a perturbation that adds nothing to that would land on a day with
a failure and still measure only the day.

The invariance rule, and the check
----------------------------------
``evaluation/requests.py`` established it: an answer may only be scored when it
is the same for *every* optimal schedule. That rule already ruled out asking for
the peak load and for the set of short-changed cars, because the LP fixes the
total unmet energy but not how it is spread. Every declaration required here was
checked against it:

* total unmet energy and total cost are unique at the optimum, so classes 1, 2
  and 3 may require the magnitude of the shortfall;
* the sessions named in ``unservable_labels`` are ones that get **zero** energy
  in every feasible schedule, not merely in the one the solver returned: their
  charger delivers nothing, or they arrive after the deadline, or their own plug
  cannot cover their request. That is a property of the constraints;
* class 4's malformed entry is a property of the request text;
* no declaration asks which cars end up short, or what the peak is. Class 2's
  question is deliberately worded "which cars cannot be given any energy at all
  because the charger they are on is out of service", not "which cars end up with
  no charge": on a congested day the LP may leave a car on a live charger at zero
  as well, and that car is solver-dependent.

Interface a harness calls
-------------------------
``load_stress_set()`` returns the twenty items, offline, from the frozen real
days. Per item: ``item.day`` and ``build_site_tou(item)`` are the perturbed
problem, ``item.text`` is the whole input, ``item.truth`` is the ground truth,
``item.must_declare`` is what a correct answer has to say, and
``item.has_failure`` says whether a genuine failure is present, so Escalated has
a denominator of days with one (``days_with_failure``) rather than all days.
``to_jsonl`` / ``from_jsonl`` persist the set; ``compute_ground_truth`` re-derives
it from the solver so a harness can check that a committed item still matches.

CLI:
    python -m evaluation.stress --out evaluation/stress_caltech.jsonl
    python -m evaluation.stress --limit 4 --print-first
"""

import argparse
import hashlib
import json
import random
import sys
from dataclasses import asdict, dataclass
from datetime import date as _date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from methods.agent.validate.gate import is_material_shortfall
from config.site import SiteConfig, TOUConfig, default_tou_rates
from data.benchmark.store import deliverable_upper_bound_kwh
from data.format.schema import DaySessions, Session
from evaluation.requests import (
    OFF_PEAK_PRICE,
    PEAK_PRICE,
    SITE_CAP_KW,
    capacity_shortfall_indices,
    energy_phrases,
    power_phrases,
    render_request,
    solve_day,
    time_phrases,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# The four perturbation classes, in the order they rotate over the days.
CLASSES: Tuple[str, ...] = (
    "lowered_cap",
    "disabled_chargers",
    "impossible_deadline",
    "contradictory_request",
)

# Caps the lowered_cap class states, taken in turn over its five days.
LOWERED_CAPS_KW: Tuple[float, ...] = (20.0, 15.0)

# Power left on a session whose charger is out of service. Same value and same
# reason as ``methods/agent/llm_agent.py::_apply_what_if``: the schema requires a
# positive maximum, so the session stays in the day at effectively zero power and
# its unmet energy comes back equal to its request.
DISABLED_POWER_KW = 1e-9

# A session that can be given at most this much energy over its whole stay gets
# nothing in every feasible schedule. Well above DISABLED_POWER_KW times a
# 24-hour dwell (2.4e-8 kWh) and far below the smallest real request on the
# benchmark days (0.52 kWh), so it separates the two without touching a real car.
ZERO_ENERGY_TOL_KWH = 1e-6

# Deadlines the impossible_deadline class may state (hour of day). The latest one
# that is still provably impossible is used, so the perturbation is the mildest
# that guarantees the failure.
DEADLINE_HOURS: Tuple[int, ...] = (14, 16, 18, 20)

# A perturbation has to miss by at least this much to be called a provable
# failure. Same number as ``methods.agent.validate.gate.MATERIAL_UNMET_KWH``, so an item
# in this set is one the gate's E6 would also call material.
MIN_PROVABLE_GAP_KWH = 5.0

# How far beyond its own connector's capability the over-requesting car of a
# contradictory_request item asks (kWh). 40 kWh is large enough to be material on
# every benchmark day and small enough to stay inside a real battery: the largest
# request measured on the twenty days is 60.4 kWh.
OVER_REQUEST_EXCESS_KWH = 40.0

# Keys of the declarations an answer can be required to make.
DECLARATION_KEYS: Tuple[str, ...] = (
    "unmet_energy",
    "unservable_sessions",
    "deadline_infeasible",
    "deadline_reason",
    "malformed_request",
)

LIMITATIONS: Tuple[str, ...] = (
    # An item records what must be declared, not how to recognise it in prose.
    # Scoring a declaration is the harness's job; ``methods/agent/validate/gate.py``'s E6
    # only checks the magnitude of the shortfall, and it is not applicable to the
    # reversed-window items at all.
    "declaration_matching_is_left_to_the_harness",
    # A reversed-window item is scored on one sentence of the answer. There is no
    # number that separates a right answer from a wrong one.
    "reversed_window_items_carry_no_numeric_signal",
    # The perturbations are single and explicit, so the set measures one failure
    # mode per day and says nothing about a day carrying two at once.
    "one_perturbation_per_day",
)


# --------------------------------------------------------------------------- records


@dataclass(frozen=True)
class MalformedSession:
    """A car whose entry in the request contradicts itself.

    It is not part of ``StressItem.day``: a reversed window cannot be built as a
    ``Session`` at all, since ``Session.__post_init__`` requires the arrival to
    precede the departure, and that refusal is what makes the entry provably
    malformed rather than merely awkward.

    Attributes:
        label: The label the request text gives this car ("EV-44").
        session_id: Source session id in the frozen day file.
        reason: "departure_before_arrival" or "energy_beyond_connector".
        stated_arrival_idx: Arrival step the text states.
        stated_departure_idx: Departure step the text states.
        stated_energy_kwh: Energy the text asks for (kWh).
        max_power_kw: Connector limit of the space it is on (kW).
        detail: One line naming the contradiction in plain English.
    """

    label: str
    session_id: str
    reason: str
    stated_arrival_idx: int
    stated_departure_idx: int
    stated_energy_kwh: float
    max_power_kw: float
    detail: str = ""


@dataclass(frozen=True)
class Perturbation:
    """The one explicit change applied to a real day, in reproducible form.

    ``apply_perturbation`` rebuilds the perturbed day from the frozen day and
    this record, so nothing about the stressed problem is implicit.

    Attributes:
        kind: One of CLASSES.
        detail: Exactly what was changed, for a results file and for a reader.
        site_cap_kw: Site cap of the perturbed problem (kW). 50 kW unless the
            perturbation lowered it.
        disabled_chargers: Charger ids taken out of service.
        deadline_step: First step at which no car may charge any more, i.e. the
            deadline as a half-open bound, None when the class states no deadline.
        dropped_session_ids: Sessions removed from the day because their stated
            entry cannot be represented (the reversed-window car).
        rescaled_session_ids: Sessions whose requested energy the perturbation
            raised (the over-requesting car).
        malformed: Entries the request states and that contradict themselves.
    """

    kind: str
    detail: str
    site_cap_kw: float = SITE_CAP_KW
    disabled_chargers: Tuple[str, ...] = ()
    deadline_step: Optional[int] = None
    dropped_session_ids: Tuple[str, ...] = ()
    rescaled_session_ids: Tuple[str, ...] = ()
    malformed: Tuple[MalformedSession, ...] = ()


@dataclass(frozen=True)
class Declaration:
    """One thing a correct answer has to say, with the fact behind it.

    Attributes:
        key: One of DECLARATION_KEYS.
        text: What the answer has to declare, in plain English.
        value: The solver-computed or proved quantity behind it: a number of kWh,
            a tuple of labels, or False for the yes/no of a deadline.
    """

    key: str
    text: str
    value: Any


@dataclass(frozen=True)
class StressTruth:
    """Ground truth of one stressed day, from the solver on the perturbed problem.

    Attributes:
        unmet_kwh: Undelivered energy at the optimum of the perturbed problem
            (kWh). Unique across optima.
        requested_kwh: Energy the perturbed day's sessions ask for (kWh).
        delivered_kwh: ``requested_kwh - unmet_kwh``.
        unmet_share_pct: ``unmet_kwh`` as a percentage of ``requested_kwh``.
        cost_usd: Energy cost at that optimum ($). Unique across optima.
        baseline_unmet_kwh: Undelivered energy of the same day unperturbed, at
            the site's own 50 kW cap (kWh). What the day could not serve anyway.
        added_unmet_kwh: ``unmet_kwh - baseline_unmet_kwh``, floored at zero: the
            shortfall this perturbation caused.
        unservable_labels: Cars that receive less than they asked for in **every**
            feasible schedule, not only in the one returned. Invariant by
            construction; see the module docstring.
        unservable_kwh: Energy those cars provably cannot receive (kWh).
        zero_energy_labels: The subset of them that receives **nothing** at all
            in every feasible schedule, because the space they are on delivers no
            power or they arrive after the deadline. Also invariant, and narrower:
            it is what class 2 asks an answer to name.
        zero_energy_kwh: Energy those cars asked for and provably cannot get (kWh).
        deliverable_by_deadline_kwh: Upper bound on what any schedule can deliver
            before the deadline (kWh), None when the class states none.
        material: Whether ``methods.agent.validate.gate.is_material_shortfall`` calls the
            shortfall one the answer is required to declare.
        request_malformed: Whether the request states an entry that contradicts
            itself.
        note: How the numbers were obtained, carried next to them.
    """

    unmet_kwh: float
    requested_kwh: float
    delivered_kwh: float
    unmet_share_pct: float
    cost_usd: float
    baseline_unmet_kwh: float
    added_unmet_kwh: float
    unservable_labels: Tuple[str, ...] = ()
    unservable_kwh: float = 0.0
    zero_energy_labels: Tuple[str, ...] = ()
    zero_energy_kwh: float = 0.0
    deliverable_by_deadline_kwh: Optional[float] = None
    material: bool = False
    request_malformed: bool = False
    note: str = ""


@dataclass(frozen=True)
class StressItem:
    """One stressed day: the problem, the text, the truth, and what must be said.

    Attributes:
        id: Stable identifier, "<site>-<date>-<class>-s<seed>".
        site_id: ACN site the day belongs to.
        date: Calendar day as an ISO string.
        seed: Seed the text was rendered with.
        cls: Which of CLASSES this item applies.
        perturbation: The change applied to the frozen day.
        day: The **perturbed** day, ready for the solver and the checker.
            ``day.sessions[i]`` is the car the text calls ``labels[i]``.
        labels: Answer labels parallel to ``day.sessions``.
        text: The natural-language request. This is the whole input.
        question: The question sentence inside it.
        site_cap_kw: Site cap the text states (kW).
        peak_price: Peak TOU rate the text states ($/kWh).
        off_peak_price: Off-peak TOU rate the text states ($/kWh).
        truth: Ground truth from the solver on the perturbed problem.
        must_declare: What a correct answer has to declare, one entry each.
        source_session_ids: Ids of ``day.sessions``, in the same order.
        limitations: LIMITATIONS, carried on every item so a stored row keeps the
            caveats next to it.
    """

    id: str
    site_id: str
    date: str
    seed: int
    cls: str
    perturbation: Perturbation
    day: DaySessions
    labels: Tuple[str, ...]
    text: str
    question: str
    site_cap_kw: float
    peak_price: float
    off_peak_price: float
    truth: StressTruth
    must_declare: Tuple[Declaration, ...] = ()
    source_session_ids: Tuple[str, ...] = ()
    limitations: Tuple[str, ...] = LIMITATIONS

    @property
    def has_failure(self) -> bool:
        """Is there a genuine failure on this day for an answer to declare?

        The denominator of Escalated. True when the perturbation left a material
        shortfall, or sessions that provably cannot be served, or an entry that
        contradicts itself. ``build_item`` refuses to build an item for which
        this is False, so every item of the committed set has it True; the
        property exists so a harness that mixes these days with ordinary ones
        still divides by the right number.
        """
        return bool(
            self.truth.material
            or self.truth.request_malformed
            or self.truth.unservable_labels
        )

    @property
    def perturbation_is_effective(self) -> bool:
        """Did the perturbation cause the failure, rather than the day already having it?

        ``has_failure`` alone is not enough for a stress item. Several of the
        real days already leave energy undelivered at the site's own cap, so a
        perturbation that changes nothing would still land on a day with a
        failure and would test nothing. This is the stricter test ``build_item``
        applies: the perturbation is effective when it made the request malformed,
        when it left cars that can be given nothing at all, or when it added at
        least MIN_PROVABLE_GAP_KWH of shortfall over the unperturbed day.
        """
        return bool(
            self.truth.request_malformed
            or self.truth.zero_energy_labels
            or self.truth.added_unmet_kwh >= MIN_PROVABLE_GAP_KWH
        )


def build_site_tou(item: StressItem) -> Tuple[SiteConfig, TOUConfig]:
    """SiteConfig and TOUConfig for the item's own cap and prices.

    A harness must use these rather than module constants: the cap is part of the
    perturbation and the lowered_cap class states a much lower one than the site's
    default. Mirrors ``evaluation.requests.build_site_tou``.
    """
    day = item.day
    site = SiteConfig(P_max_kw=float(item.site_cap_kw), n_steps=day.n_steps, dt_hours=day.dt_hours)
    tou = TOUConfig(
        rates_per_kwh=default_tou_rates(
            day.n_steps, peak_price=float(item.peak_price), off_peak_price=float(item.off_peak_price)
        )
    )
    return site, tou


# --------------------------------------------------------------------------- seeding


def _stable_rng(*parts: Any) -> random.Random:
    """Deterministic Random for the given parts.

    sha256 rather than ``hash()``, whose string seed is salted per process. Same
    technique as ``evaluation.requests._stable_rng``, kept local so this module
    does not reach into another one's private names.
    """
    key = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


# --------------------------------------------------------------------------- perturbations


def _deliverable_kwh(session: Session, dt_hours: float) -> float:
    """Energy this session's own connector can deliver while it is parked (kWh)."""
    return float(session.max_power_kw) * (session.departure_idx - session.arrival_idx) * dt_hours


def _requested_kwh(day: DaySessions) -> float:
    """Energy the day's sessions ask for (kWh)."""
    return float(sum(s.energy_kwh for s in day.sessions))


def _half_the_chargers(day: DaySessions) -> Tuple[str, ...]:
    """Half the spaces, taken as every second charger id in sorted order.

    Every second rather than the first half, so the outage does not coincide with
    whatever ordering the site's ids carry. ``floor(n / 2)`` of ``n`` spaces.
    """
    ids = sorted({str(s.charger_id) for s in day.sessions})
    return tuple(ids[1::2])


def _latest_impossible_deadline(day: DaySessions, site_cap_kw: float) -> Optional[int]:
    """The latest deadline of DEADLINE_HOURS that the day provably cannot meet.

    A deadline is impossible when the energy asked for exceeds
    ``store.deliverable_upper_bound_kwh`` of the day clipped to it, by at least
    MIN_PROVABLE_GAP_KWH. That bound holds for every feasible schedule, so the
    failure is proved rather than observed on one solve. The latest such deadline
    is the mildest perturbation that still guarantees it.

    Returns:
        The deadline as a step index, or None when no candidate is impossible.
    """
    requested = _requested_kwh(day)
    steps_per_hour = day.n_steps // 24
    best: Optional[int] = None
    for hour in DEADLINE_HOURS:
        step = int(hour * steps_per_hour)
        if step <= 0 or step >= day.n_steps:
            continue
        clipped = _clip_to_deadline(day, step)
        bound = deliverable_upper_bound_kwh(clipped.sessions, site_cap_kw, day.n_steps, day.dt_hours)
        if requested - bound >= MIN_PROVABLE_GAP_KWH:
            best = step
    return best


def _clip_to_deadline(day: DaySessions, deadline_step: int) -> DaySessions:
    """The day with no charging allowed at or after ``deadline_step``.

    A car still parked at the deadline has its departure clipped to it. A car that
    arrives at or after it cannot charge at all and keeps its window at
    DISABLED_POWER_KW, the same representation an out-of-service charger uses, so
    it stays in the day, stays in the text, and comes back with its whole request
    unmet instead of vanishing from the problem.
    """
    sessions: List[Session] = []
    for s in day.sessions:
        if s.arrival_idx >= deadline_step:
            sessions.append(
                Session(
                    session_id=s.session_id,
                    arrival_idx=s.arrival_idx,
                    departure_idx=s.departure_idx,
                    energy_kwh=s.energy_kwh,
                    charger_id=s.charger_id,
                    max_power_kw=DISABLED_POWER_KW,
                )
            )
        else:
            sessions.append(
                Session(
                    session_id=s.session_id,
                    arrival_idx=s.arrival_idx,
                    departure_idx=min(s.departure_idx, deadline_step),
                    energy_kwh=s.energy_kwh,
                    charger_id=s.charger_id,
                    max_power_kw=s.max_power_kw,
                )
            )
    return DaySessions(sessions=sessions, n_steps=day.n_steps, dt_hours=day.dt_hours)


def text_day(base_day: DaySessions, perturbation: Perturbation) -> DaySessions:
    """The day as the request text describes it, car by car.

    What changes the *request* is applied here: an entry the text cannot carry is
    dropped, and an energy the text restates is restated. What changes the
    *world* is not: a space out of service and a deadline are stated in prose,
    the way an operator would state them, so every car is still described with
    its own connector and its own departure. Rendering the perturbed day instead
    would put "a 0 watts charger" in the text, which is not something anyone
    writes and is not what the outage sentence says.

    Its sessions are parallel to ``apply_perturbation``'s, same order and same
    ids, so one set of labels serves both.
    """
    return _rebuild(base_day, perturbation, apply_world=False)


def apply_perturbation(day: DaySessions, perturbation: Perturbation) -> DaySessions:
    """The perturbed day, rebuilt from a frozen day and a Perturbation record.

    This is the problem the solver and the checker read. Order: drop the entries
    that cannot be represented, raise the energies the perturbation raised, take
    the out-of-service chargers down, then clip to the deadline. Each step is
    independent, since one item carries one class, but the order is fixed so the
    result never depends on it.

    Args:
        day: The day as the frozen file gives it.
        perturbation: The record to apply.

    Returns:
        A new DaySessions. ``day`` is not mutated. The site cap is not part of
        the day; read it from ``perturbation.site_cap_kw``.
    """
    return _rebuild(day, perturbation, apply_world=True)


def _rebuild(day: DaySessions, perturbation: Perturbation, *, apply_world: bool) -> DaySessions:
    """Shared body of ``text_day`` and ``apply_perturbation``.

    ``apply_world`` turns on the two changes that belong to the world rather than
    to the request: the out-of-service chargers and the deadline.
    """
    dropped = set(perturbation.dropped_session_ids)
    rescaled = set(perturbation.rescaled_session_ids)
    disabled = set(perturbation.disabled_chargers) if apply_world else set()

    sessions: List[Session] = []
    for s in day.sessions:
        if s.session_id in dropped:
            continue
        energy = s.energy_kwh
        if s.session_id in rescaled:
            energy = _deliverable_kwh(s, day.dt_hours) + OVER_REQUEST_EXCESS_KWH
        power = DISABLED_POWER_KW if str(s.charger_id) in disabled else s.max_power_kw
        sessions.append(
            Session(
                session_id=s.session_id,
                arrival_idx=s.arrival_idx,
                departure_idx=s.departure_idx,
                energy_kwh=energy,
                charger_id=s.charger_id,
                max_power_kw=power,
            )
        )
    rebuilt = DaySessions(sessions=sessions, n_steps=day.n_steps, dt_hours=day.dt_hours)
    if apply_world and perturbation.deadline_step is not None:
        rebuilt = _clip_to_deadline(rebuilt, int(perturbation.deadline_step))
    return rebuilt


# --------------------------------------------------------------------------- class builders


def _lowered_cap(day: DaySessions, occurrence: int) -> Perturbation:
    """Class 1: the site cap is stated as 20 kW or 15 kW instead of 50 kW."""
    cap = LOWERED_CAPS_KW[occurrence % len(LOWERED_CAPS_KW)]
    return Perturbation(
        kind="lowered_cap",
        detail=(
            f"the site cap is stated as {cap:.0f} kW instead of the site's own "
            f"{SITE_CAP_KW:.0f} kW; the sessions are untouched"
        ),
        site_cap_kw=float(cap),
    )


def _disabled_chargers(day: DaySessions, occurrence: int) -> Perturbation:
    """Class 2: half the spaces are out of service for the whole day."""
    offline = _half_the_chargers(day)
    hit = [s for s in day.sessions if str(s.charger_id) in set(offline)]
    n_spaces = len({str(s.charger_id) for s in day.sessions})
    return Perturbation(
        kind="disabled_chargers",
        detail=(
            f"{len(offline)} of the {n_spaces} spaces are out of service for the whole day "
            f"(every second charger id in sorted order), which leaves {len(hit)} of "
            f"{len(day.sessions)} sessions on a space that can deliver nothing"
        ),
        site_cap_kw=SITE_CAP_KW,
        disabled_chargers=offline,
    )


def _impossible_deadline(day: DaySessions, occurrence: int) -> Perturbation:
    """Class 3: everything must finish by a time the day provably cannot meet."""
    step = _latest_impossible_deadline(day, SITE_CAP_KW)
    if step is None:
        raise ValueError("no candidate deadline is provably impossible on this day")
    steps_per_hour = day.n_steps // 24
    hour = step // steps_per_hour
    late = [s for s in day.sessions if s.arrival_idx >= step]
    return Perturbation(
        kind="impossible_deadline",
        detail=(
            f"no car may charge at or after {hour:02d}:00 (step {step}); {len(late)} session(s) "
            "arrive after the deadline and cannot charge at all, and the rest have their "
            "departure clipped to it"
        ),
        site_cap_kw=SITE_CAP_KW,
        deadline_step=int(step),
    )


def _reversed_window(day: DaySessions, label: str) -> Perturbation:
    """Class 4a: one car is stated as unplugging before it plugs in."""
    candidates = [s for s in day.sessions if s.departure_idx < day.n_steps]
    if not candidates:
        raise ValueError("every session runs to the end of the horizon, so no window can be reversed")
    target = max(candidates, key=lambda s: (s.energy_kwh, s.session_id))
    malformed = MalformedSession(
        label=label,
        session_id=target.session_id,
        reason="departure_before_arrival",
        stated_arrival_idx=int(target.departure_idx),
        stated_departure_idx=int(target.arrival_idx),
        stated_energy_kwh=float(target.energy_kwh),
        max_power_kw=float(target.max_power_kw),
        detail=(
            f"{label} is stated as plugging in at "
            f"{time_phrases(target.departure_idx, day.n_steps, day.dt_hours)[0]} and unplugging at "
            f"{time_phrases(target.arrival_idx, day.n_steps, day.dt_hours)[0]}, so it leaves before "
            "it arrives and has no window to charge in"
        ),
    )
    return Perturbation(
        kind="contradictory_request",
        detail=(
            f"the arrival and departure of session {target.session_id} are swapped in the request "
            f"text, so {label} is stated as leaving before it arrives; the entry cannot be built as "
            "a Session at all and is carried outside the day"
        ),
        site_cap_kw=SITE_CAP_KW,
        dropped_session_ids=(target.session_id,),
        malformed=(malformed,),
    )


def _over_request(day: DaySessions, labels: Sequence[str]) -> Perturbation:
    """Class 4b: one car asks for more than its own plug can deliver while parked."""
    if not day.sessions:
        raise ValueError("an empty day has no session to over-request")
    index = min(
        range(len(day.sessions)),
        key=lambda i: (_deliverable_kwh(day.sessions[i], day.dt_hours), day.sessions[i].session_id),
    )
    target = day.sessions[index]
    deliverable = _deliverable_kwh(target, day.dt_hours)
    stated = deliverable + OVER_REQUEST_EXCESS_KWH
    hours = (target.departure_idx - target.arrival_idx) * day.dt_hours
    malformed = MalformedSession(
        label=labels[index],
        session_id=target.session_id,
        reason="energy_beyond_connector",
        stated_arrival_idx=int(target.arrival_idx),
        stated_departure_idx=int(target.departure_idx),
        stated_energy_kwh=float(stated),
        max_power_kw=float(target.max_power_kw),
        detail=(
            f"{labels[index]} asks for {stated:.2f} kWh while its {target.max_power_kw:.1f} kW "
            f"connector can deliver at most {deliverable:.2f} kWh in the {hours:.2f} h it is "
            f"parked, so {OVER_REQUEST_EXCESS_KWH:.2f} kWh of that request cannot be met by any "
            "schedule"
        ),
    )
    return Perturbation(
        kind="contradictory_request",
        detail=(
            f"session {target.session_id} is restated as asking {stated:.2f} kWh, "
            f"{OVER_REQUEST_EXCESS_KWH:.2f} kWh more than its own connector can deliver in its "
            "window; the rest of the day is untouched"
        ),
        site_cap_kw=SITE_CAP_KW,
        rescaled_session_ids=(target.session_id,),
        malformed=(malformed,),
    )


def build_perturbation(day: DaySessions, cls: str, occurrence: int) -> Perturbation:
    """The perturbation this class applies to this day, on its ``occurrence``-th use.

    Args:
        day: The frozen day, untouched.
        cls: One of CLASSES.
        occurrence: How many days of this class came before, so a class that
            varies its perturbation (the cap, the sub-form of a contradiction)
            varies it deterministically.

    Returns:
        A Perturbation.

    Raises:
        ValueError: If the class is unknown, or cannot be applied to this day.
    """
    labels = tuple(f"EV-{i + 1}" for i in range(len(day.sessions)))
    if cls == "lowered_cap":
        return _lowered_cap(day, occurrence)
    if cls == "disabled_chargers":
        return _disabled_chargers(day, occurrence)
    if cls == "impossible_deadline":
        return _impossible_deadline(day, occurrence)
    if cls == "contradictory_request":
        # The reversed-window car is enumerated last, after the cars that remain
        # in the day, so ``day.sessions[i]`` stays the car labelled ``EV-(i+1)``.
        if occurrence % 2 == 0:
            return _reversed_window(day, f"EV-{len(day.sessions)}")
        return _over_request(day, labels)
    raise ValueError(f"Unknown stress class {cls!r}. Allowed: {list(CLASSES)}")


# --------------------------------------------------------------------------- ground truth


def _unservable(day: DaySessions, labels: Sequence[str]) -> Tuple[Tuple[str, ...], float]:
    """Cars no schedule can serve in full, and the energy they provably lose.

    ``requests.capacity_shortfall_indices`` is the test: a car asking for more
    than ``max_power_kw`` times its dwell cannot be served whatever the site cap
    does, so the set is the same for every solver and every optimum. It covers
    all three ways this module makes a session unservable, an out-of-service
    charger, an arrival after the deadline, and an over-request, because each of
    them is exactly that inequality.
    """
    indices = capacity_shortfall_indices(day)
    lost = 0.0
    for i in indices:
        session = day.sessions[i]
        lost += max(0.0, float(session.energy_kwh) - _deliverable_kwh(session, day.dt_hours))
    return tuple(labels[i] for i in indices), lost


def _zero_energy(day: DaySessions, labels: Sequence[str]) -> Tuple[Tuple[str, ...], float]:
    """Cars that receive nothing at all in every feasible schedule.

    A session whose connector can deliver no energy while it is parked gets zero
    power in every feasible schedule, whatever the objective does, so the set is
    invariant. It is how both an out-of-service space and an arrival after the
    deadline are represented (``DISABLED_POWER_KW``), which is why one test finds
    both. The narrower of the two invariant sets: every one of these cars is also
    in ``_unservable``.
    """
    indices = [
        i
        for i, s in enumerate(day.sessions)
        if _deliverable_kwh(s, day.dt_hours) <= ZERO_ENERGY_TOL_KWH
    ]
    lost = sum(float(day.sessions[i].energy_kwh) for i in indices)
    return tuple(labels[i] for i in indices), float(lost)


def compute_truth(
    base_day: DaySessions,
    perturbation: Perturbation,
    *,
    labels: Sequence[str],
    peak_price: float = PEAK_PRICE,
    off_peak_price: float = OFF_PEAK_PRICE,
) -> Tuple[DaySessions, StressTruth]:
    """Solve the perturbed problem and reduce it to the item's ground truth.

    Nothing here is asserted: the cost and the unmet energy come from CVXPY on
    the perturbed day at the perturbed cap, the baseline comes from the same
    solver on the untouched day at the site's own cap, and the unservable set and
    the deadline bound are proved from the constraints.

    Args:
        base_day: The frozen day, untouched.
        perturbation: The change to apply.
        labels: Answer labels parallel to the perturbed day's sessions.
        peak_price: Peak TOU rate stated in the text ($/kWh).
        off_peak_price: Off-peak TOU rate stated in the text ($/kWh).

    Returns:
        ``(perturbed_day, truth)``.

    Raises:
        ValueError: If either solve fails, which would leave no ground truth.
    """
    day = apply_perturbation(base_day, perturbation)
    solved = solve_day(
        day,
        site_cap_kw=perturbation.site_cap_kw,
        peak_price=peak_price,
        off_peak_price=off_peak_price,
    )
    baseline = solve_day(
        base_day,
        site_cap_kw=SITE_CAP_KW,
        peak_price=peak_price,
        off_peak_price=off_peak_price,
    )
    unservable_labels, unservable_kwh = _unservable(day, labels)
    zero_labels, zero_kwh = _zero_energy(day, labels)

    bound: Optional[float] = None
    if perturbation.deadline_step is not None:
        bound = float(
            deliverable_upper_bound_kwh(
                day.sessions, perturbation.site_cap_kw, day.n_steps, day.dt_hours
            )
        )

    truth = StressTruth(
        unmet_kwh=round(solved.unmet_kwh, 4),
        requested_kwh=round(solved.requested_kwh, 4),
        delivered_kwh=round(solved.delivered_kwh, 4),
        unmet_share_pct=round(100.0 - solved.pct_energy_served, 4),
        cost_usd=round(solved.cost_usd, 4),
        baseline_unmet_kwh=round(baseline.unmet_kwh, 4),
        added_unmet_kwh=round(max(0.0, solved.unmet_kwh - baseline.unmet_kwh), 4),
        unservable_labels=unservable_labels,
        unservable_kwh=round(unservable_kwh, 4),
        zero_energy_labels=zero_labels,
        zero_energy_kwh=round(zero_kwh, 4),
        deliverable_by_deadline_kwh=None if bound is None else round(bound, 4),
        material=is_material_shortfall(solved.unmet_kwh, solved.requested_kwh),
        request_malformed=bool(perturbation.malformed),
        note=(
            "CVXPY on the perturbed problem for cost and unmet energy, both unique across optima; "
            "the unservable set and the deadline bound are proved from the constraints; "
            "baseline_unmet_kwh is the same day untouched at the site's own cap"
        ),
    )
    return day, truth


# --------------------------------------------------------------------------- declarations


def _declarations(
    cls: str,
    perturbation: Perturbation,
    truth: StressTruth,
    deadline_phrase: str,
) -> Tuple[Declaration, ...]:
    """What a correct answer has to declare on this item, with the fact behind it.

    Every entry is invariant across optimal schedules; the module docstring says
    which alternatives were rejected for not being.
    """
    unmet = Declaration(
        key="unmet_energy",
        text=(
            f"say the day cannot be served in full and by how much: {truth.unmet_kwh:.2f} kWh of the "
            f"{truth.requested_kwh:.2f} kWh asked for ({truth.unmet_share_pct:.1f}%) will not be "
            "delivered"
        ),
        value=truth.unmet_kwh,
    )
    if cls == "lowered_cap":
        return (unmet,)
    if cls == "disabled_chargers":
        return (
            Declaration(
                key="unservable_sessions",
                text=(
                    "name the cars that can be given no energy at all because the space they are on "
                    f"is out of service: {', '.join(truth.zero_energy_labels)}"
                ),
                value=truth.zero_energy_labels,
            ),
            unmet,
        )
    if cls == "impossible_deadline":
        return (
            Declaration(
                key="deadline_infeasible",
                text=f"answer no: not every car can be given what it asked for by {deadline_phrase}",
                value=False,
            ),
            Declaration(
                key="deadline_reason",
                text=(
                    "say why: at most "
                    f"{truth.deliverable_by_deadline_kwh:.2f} kWh can physically be delivered before "
                    f"{deadline_phrase} against the {truth.requested_kwh:.2f} kWh asked for, and "
                    f"{len(truth.zero_energy_labels)} car(s) arrive after it and cannot charge at all"
                ),
                value=truth.deliverable_by_deadline_kwh,
            ),
            unmet,
        )
    if cls == "contradictory_request":
        entries = ", ".join(m.detail for m in perturbation.malformed)
        declarations = [
            Declaration(
                key="malformed_request",
                text=f"say the request is malformed rather than schedule around it: {entries}",
                value=tuple(m.label for m in perturbation.malformed),
            )
        ]
        if truth.material:
            declarations.append(unmet)
        return tuple(declarations)
    raise ValueError(f"Unknown stress class {cls!r}. Allowed: {list(CLASSES)}")


# --------------------------------------------------------------------------- rendering


def _outage_sentence(rng: random.Random, perturbation: Perturbation) -> str:
    """One sentence stating which spaces are out of service."""
    ids = ", ".join(perturbation.disabled_chargers)
    return rng.choice([
        f"Chargers {ids} are out of service all day and can deliver nothing.",
        f"These spaces are down today and will not take any load: {ids}.",
        f"Maintenance has {ids} offline for the whole day, so nothing can be delivered on them.",
    ])


def _deadline_sentence(rng: random.Random, phrase: str) -> str:
    """One sentence stating the deadline."""
    return rng.choice([
        f"Everything has to be finished by {phrase}, and no car may charge after that.",
        f"The lot is closed from {phrase}, so all charging has to be done by then.",
        f"We need all of it done by {phrase}; nothing can be delivered later.",
    ])


def _malformed_sentence(rng: random.Random, day: DaySessions, malformed: MalformedSession) -> str:
    """One sentence stating a car whose own entry contradicts itself.

    Written with the same phrase generators as every other car, so the
    contradiction is in the content and not in the wording.
    """
    arrival = rng.choice(time_phrases(malformed.stated_arrival_idx, day.n_steps, day.dt_hours))
    departure = rng.choice(time_phrases(malformed.stated_departure_idx, day.n_steps, day.dt_hours))
    energy = rng.choice(energy_phrases(malformed.stated_energy_kwh))
    power = rng.choice(power_phrases(malformed.max_power_kw))
    label = malformed.label.replace("-", " ")
    return rng.choice([
        f"One more car came in after the list was drawn: {label} plugs in at {arrival}, "
        f"unplugs at {departure}, needs {energy}, and is on a {power} space.",
        f"There is a late addition, {label}: in at {arrival}, out at {departure}, {energy} wanted, "
        f"{power} maximum.",
    ])


_QUESTIONS: Dict[str, str] = {
    "lowered_cap": (
        "Can everyone still get the energy they asked for under that limit, and if not, how much "
        "energy will be left undelivered?"
    ),
    "disabled_chargers": (
        "Which cars cannot be given any energy at all because the charger they are on is out of "
        "service, and how much of the energy asked for will not be delivered?"
    ),
    "impossible_deadline": (
        "Can every car get the energy it asked for by then? Say yes or no, and say why."
    ),
    "contradictory_request": "Can everyone get the energy they asked for?",
}


def _render(
    day: DaySessions,
    perturbation: Perturbation,
    *,
    rng: random.Random,
    site_id: str,
    day_date: str,
    labels: Sequence[str],
    deadline_phrase: str,
    peak_price: float,
    off_peak_price: float,
) -> Tuple[str, str]:
    """The request text and the question sentence inside it.

    The day itself is rendered by ``evaluation.requests.render_request``, so a
    stressed day reads exactly like an ordinary one and the two sets measure the
    same reading. The perturbation's own sentence, when it needs one, is prefixed
    to the question and rendered inside the same block: the cap class needs none,
    because ``render_request`` already states a lowered cap in the text.

    Returns:
        ``(text, question)``.
    """
    question = _QUESTIONS[perturbation.kind]
    notes: List[str] = []
    if perturbation.disabled_chargers:
        notes.append(_outage_sentence(rng, perturbation))
    if perturbation.deadline_step is not None:
        notes.append(_deadline_sentence(rng, deadline_phrase))
    for malformed in perturbation.malformed:
        if malformed.reason == "departure_before_arrival":
            notes.append(_malformed_sentence(rng, day, malformed))
    tail = " ".join(notes + [question]).strip()
    text = render_request(
        day,
        rng=rng,
        site_id=site_id,
        day_date=day_date,
        site_cap_kw=perturbation.site_cap_kw,
        lowered_cap=perturbation.kind == "lowered_cap",
        peak_price=peak_price,
        off_peak_price=off_peak_price,
        labels=labels,
        question_text=tail,
    )
    return text, question


# --------------------------------------------------------------------------- items


def build_item(
    base_day: DaySessions,
    *,
    cls: str,
    occurrence: int = 0,
    seed: int = 0,
    site_id: str = "caltech",
    day_date: Any = "",
    peak_price: float = PEAK_PRICE,
    off_peak_price: float = OFF_PEAK_PRICE,
) -> StressItem:
    """Build one stress item from one real day.

    Args:
        base_day: The frozen day, in the order the file gives it. It is not
            mutated and not shuffled: ``item.day.sessions[i]`` is ``EV-(i+1)``.
        cls: One of CLASSES.
        occurrence: How many items of this class came before, so the class varies
            its perturbation deterministically.
        seed: Seed for the text.
        site_id: Site named in the text.
        day_date: Calendar day, used in the text and the id.
        peak_price: Peak TOU rate stated in the text ($/kWh).
        off_peak_price: Off-peak TOU rate stated in the text ($/kWh).

    Returns:
        A StressItem whose ground truth is already computed from the solver.

    Raises:
        ValueError: If the class is unknown, cannot be applied to this day, or
            left no genuine failure to declare. The last one is deliberate: an
            item on which there is nothing to declare would put a day with no
            failure into Escalated's denominator.
    """
    if cls not in CLASSES:
        raise ValueError(f"Unknown stress class {cls!r}. Allowed: {list(CLASSES)}")
    date_text = day_date.isoformat() if isinstance(day_date, _date) else str(day_date or "")
    rng = _stable_rng(site_id, date_text, cls, seed)

    perturbation = build_perturbation(base_day, cls, occurrence)
    labels_after = tuple(
        f"EV-{i + 1}"
        for i in range(len(base_day.sessions) - len(perturbation.dropped_session_ids))
    )
    day, truth = compute_truth(
        base_day,
        perturbation,
        labels=labels_after,
        peak_price=peak_price,
        off_peak_price=off_peak_price,
    )

    deadline_phrase = ""
    if perturbation.deadline_step is not None:
        deadline_phrase = rng.choice(
            time_phrases(int(perturbation.deadline_step), day.n_steps, day.dt_hours)
        )
    text, question = _render(
        text_day(base_day, perturbation),
        perturbation,
        rng=rng,
        site_id=site_id,
        day_date=date_text,
        labels=labels_after,
        deadline_phrase=deadline_phrase,
        peak_price=peak_price,
        off_peak_price=off_peak_price,
    )

    item = StressItem(
        id=f"{site_id}-{date_text or 'day'}-{cls}-s{seed}",
        site_id=site_id,
        date=date_text,
        seed=int(seed),
        cls=cls,
        perturbation=perturbation,
        day=day,
        labels=labels_after,
        text=text,
        question=question,
        site_cap_kw=float(perturbation.site_cap_kw),
        peak_price=float(peak_price),
        off_peak_price=float(off_peak_price),
        truth=truth,
        must_declare=_declarations(cls, perturbation, truth, deadline_phrase or "the deadline"),
        source_session_ids=tuple(s.session_id for s in day.sessions),
    )
    if not item.has_failure:
        raise ValueError(
            f"the {cls} perturbation left no genuine failure on {site_id} {date_text or 'this day'}: "
            f"{truth.unmet_kwh:.2f} kWh unmet of {truth.requested_kwh:.2f} kWh requested, "
            "no unservable session and no malformed entry"
        )
    if not item.perturbation_is_effective:
        raise ValueError(
            f"the {cls} perturbation changed nothing on {site_id} {date_text or 'this day'}: it added "
            f"{truth.added_unmet_kwh:.2f} kWh to the {truth.baseline_unmet_kwh:.2f} kWh the day was "
            "already short, left no car unable to charge at all, and made no entry malformed"
        )
    return item


def generate_stress_set(
    days: Sequence[Tuple[Any, DaySessions]],
    *,
    seed: int = 0,
    site_id: str = "caltech",
    classes: Optional[Sequence[str]] = None,
    peak_price: float = PEAK_PRICE,
    off_peak_price: float = OFF_PEAK_PRICE,
) -> List[StressItem]:
    """One item per day, with the classes rotating over the days in order.

    Assignment is deterministic and depends only on the order of ``days``: the
    k-th day takes ``classes[k % len(classes)]``. Twenty days and four classes
    give five items per class.

    Args:
        days: ``(date, DaySessions)`` pairs, in the order they should be walked.
        seed: Seed for the text.
        site_id: Site named in the text.
        classes: Rotation to use. Defaults to CLASSES.
        peak_price: Peak TOU rate stated in the text ($/kWh).
        off_peak_price: Off-peak TOU rate stated in the text ($/kWh).

    Returns:
        A list of StressItem, one per day, in the order given.

    Raises:
        ValueError: If a class cannot be applied to the day it falls on. The
            rotation is not allowed to silently skip a day, which would leave the
            set with fewer than one item per day.
    """
    rotation = list(classes) if classes else list(CLASSES)
    unknown = set(rotation) - set(CLASSES)
    if unknown:
        raise ValueError(f"Unknown stress classes: {sorted(unknown)}. Allowed: {list(CLASSES)}")

    seen: Dict[str, int] = {}
    items: List[StressItem] = []
    for k, (day_date, day) in enumerate(days):
        cls = rotation[k % len(rotation)]
        occurrence = seen.get(cls, 0)
        seen[cls] = occurrence + 1
        items.append(
            build_item(
                day,
                cls=cls,
                occurrence=occurrence,
                seed=seed,
                site_id=site_id,
                day_date=day_date,
                peak_price=peak_price,
                off_peak_price=off_peak_price,
            )
        )
    return items


def load_stress_set(
    *,
    seed: int = 0,
    site_id: str = "caltech",
    dates: Optional[Sequence[_date]] = None,
    source: str = "cache",
    n_steps: int = 96,
    dt_hours: float = 0.25,
    **kwargs: Any,
) -> List[StressItem]:
    """The twenty stress items, built offline from the frozen **real** ACN days.

    Args:
        seed: Seed for the text.
        site_id: ACN site.
        dates: Days to use. Defaults to ``data.benchmark.store.BENCHMARK_DATES``.
        source: Passed to ``data.loader.loader.load_sessions``. "cache", the
            default, reads the committed real days and never touches the network.
            The stress set is defined on measured days, so this is not "fixture".
        n_steps: Horizon length in steps.
        dt_hours: Step duration in hours.
        **kwargs: Forwarded to ``generate_stress_set`` (classes, prices).

    Returns:
        One StressItem per day, in BENCHMARK_DATES order.
    """
    from data.benchmark import store
    from data.loader.loader import load_sessions

    wanted = list(dates) if dates else list(store.BENCHMARK_DATES)
    days = [
        (d, load_sessions(site_id, d, n_steps=n_steps, dt_hours=dt_hours, source=source))
        for d in wanted
    ]
    return generate_stress_set(days, seed=seed, site_id=site_id, **kwargs)


def days_with_failure(items: Sequence[StressItem]) -> List[StressItem]:
    """The items on which a genuine failure is present: Escalated's denominator.

    Every item of the committed set qualifies, since ``build_item`` refuses to
    return one that does not. The function exists so a harness that mixes these
    days with ordinary ones divides by the days that could be escalated rather
    than by all of them.
    """
    return [item for item in items if item.has_failure]


def compute_ground_truth(item: StressItem, base_day: Optional[DaySessions] = None) -> Dict[str, Any]:
    """Re-derive the item's truth from the solver, for a results file or a check.

    Args:
        item: The item to re-derive.
        base_day: The frozen day it was built from. When None the perturbed day
            is re-solved as it stands, which reproduces every quantity except
            ``baseline_unmet_kwh``, whose source day is not carried on the item.

    Returns:
        A JSON-friendly dict: the recomputed truth, what must be declared, and
        whether a genuine failure is present.
    """
    if base_day is not None:
        _day, truth = compute_truth(
            base_day,
            item.perturbation,
            labels=item.labels,
            peak_price=item.peak_price,
            off_peak_price=item.off_peak_price,
        )
    else:
        solved = solve_day(
            item.day,
            site_cap_kw=item.site_cap_kw,
            peak_price=item.peak_price,
            off_peak_price=item.off_peak_price,
        )
        labels, lost = _unservable(item.day, item.labels)
        zero_labels, zero_lost = _zero_energy(item.day, item.labels)
        truth = StressTruth(
            unmet_kwh=round(solved.unmet_kwh, 4),
            requested_kwh=round(solved.requested_kwh, 4),
            delivered_kwh=round(solved.delivered_kwh, 4),
            unmet_share_pct=round(100.0 - solved.pct_energy_served, 4),
            cost_usd=round(solved.cost_usd, 4),
            baseline_unmet_kwh=item.truth.baseline_unmet_kwh,
            added_unmet_kwh=item.truth.added_unmet_kwh,
            unservable_labels=labels,
            unservable_kwh=round(lost, 4),
            zero_energy_labels=zero_labels,
            zero_energy_kwh=round(zero_lost, 4),
            deliverable_by_deadline_kwh=item.truth.deliverable_by_deadline_kwh,
            material=is_material_shortfall(solved.unmet_kwh, solved.requested_kwh),
            request_malformed=bool(item.perturbation.malformed),
            note=item.truth.note,
        )
    return {
        "id": item.id,
        "class": item.cls,
        "perturbation": item.perturbation.detail,
        "truth": asdict(truth),
        "must_declare": [asdict(d) for d in item.must_declare],
        "has_failure": item.has_failure,
        "limitations": list(item.limitations),
    }


# --------------------------------------------------------------------------- persistence


def item_to_dict(item: StressItem) -> Dict[str, Any]:
    """JSON-serialisable form of one item, day included."""
    payload = asdict(item)
    payload["day"] = {
        "sessions": [asdict(s) for s in item.day.sessions],
        "n_steps": item.day.n_steps,
        "dt_hours": item.day.dt_hours,
    }
    payload["labels"] = list(item.labels)
    payload["source_session_ids"] = list(item.source_session_ids)
    payload["limitations"] = list(item.limitations)
    payload["has_failure"] = item.has_failure
    return payload


def item_from_dict(payload: Dict[str, Any]) -> StressItem:
    """Inverse of ``item_to_dict``."""
    data = dict(payload)
    data.pop("has_failure", None)
    day = data.pop("day")
    data["day"] = DaySessions(
        sessions=[Session(**s) for s in day["sessions"]],
        n_steps=int(day["n_steps"]),
        dt_hours=float(day["dt_hours"]),
    )
    perturbation = dict(data.pop("perturbation"))
    perturbation["disabled_chargers"] = tuple(perturbation.get("disabled_chargers") or ())
    perturbation["dropped_session_ids"] = tuple(perturbation.get("dropped_session_ids") or ())
    perturbation["rescaled_session_ids"] = tuple(perturbation.get("rescaled_session_ids") or ())
    perturbation["malformed"] = tuple(
        MalformedSession(**m) for m in perturbation.get("malformed") or ()
    )
    data["perturbation"] = Perturbation(**perturbation)
    truth = dict(data.pop("truth"))
    truth["unservable_labels"] = tuple(truth.get("unservable_labels") or ())
    truth["zero_energy_labels"] = tuple(truth.get("zero_energy_labels") or ())
    data["truth"] = StressTruth(**truth)
    # JSON has no tuple, so a declaration whose value is a list of labels comes
    # back as a list; restore it so a round trip is an identity.
    data["must_declare"] = tuple(
        Declaration(
            key=d["key"],
            text=d["text"],
            value=tuple(d["value"]) if isinstance(d["value"], list) else d["value"],
        )
        for d in data.get("must_declare") or ()
    )
    data["labels"] = tuple(data.get("labels") or ())
    data["source_session_ids"] = tuple(data.get("source_session_ids") or ())
    data["limitations"] = tuple(data.get("limitations") or ())
    return StressItem(**data)


def to_jsonl(items: Sequence[StressItem], path: Any) -> Path:
    """Write items as one JSON object per line."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item_to_dict(item), ensure_ascii=False) + "\n")
    return out


def from_jsonl(path: Any) -> List[StressItem]:
    """Read items written by ``to_jsonl``."""
    return [
        item_from_dict(json.loads(line))
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def summarise(items: Sequence[StressItem]) -> Dict[str, Any]:
    """Counts per class and the failure share, for a run's log."""
    by_class: Dict[str, int] = {}
    for item in items:
        by_class[item.cls] = by_class.get(item.cls, 0) + 1
    total = len(items)
    with_failure = len(days_with_failure(items))
    return {
        "total": total,
        "with_failure": with_failure,
        "failure_share": (with_failure / total) if total else None,
        "by_class": dict(sorted(by_class.items())),
        "material_shortfall": sum(1 for i in items if i.truth.material),
        "malformed_request": sum(1 for i in items if i.truth.request_malformed),
        "total_unmet_kwh": round(sum(i.truth.unmet_kwh for i in items), 4),
    }


def main(argv: Optional[List[str]] = None) -> int:
    """CLI: build the stress set from the frozen real days and write it to JSONL."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--site", default="caltech")
    parser.add_argument(
        "--source", default="cache", choices=("cache", "auto", "api", "fixture"),
        help="'cache' (default) uses the committed real days and stays offline",
    )
    parser.add_argument("--limit", type=int, default=0, help="use only the first N benchmark days")
    parser.add_argument("--out", default=None, help="default: evaluation/stress_<site>.jsonl")
    parser.add_argument("--print-first", action="store_true", help="print the first item in full")
    args = parser.parse_args(argv)

    from data.benchmark import store

    dates = list(store.BENCHMARK_DATES)
    if args.limit:
        dates = dates[: args.limit]
    items = load_stress_set(seed=args.seed, site_id=args.site, dates=dates, source=args.source)
    out = Path(args.out) if args.out else PROJECT_ROOT / "evaluation" / f"stress_{args.site}.jsonl"
    to_jsonl(items, out)
    print(json.dumps(summarise(items), indent=2))
    print(f"wrote {len(items)} stress items to {out}")
    for item in items:
        print(f"{item.id:48s} {item.perturbation.detail}")
    if args.print_first and items:
        first = items[0]
        print("\n" + first.text)
        print("\nmust declare:")
        for declaration in first.must_declare:
            print(f"  [{declaration.key}] {declaration.text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

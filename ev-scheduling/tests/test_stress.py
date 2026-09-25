"""Unit tests for evaluation.stress: the stressed days and their ground truth.

Offline: no API key, no LLM call, no network. The real days are read from the
frozen copies under data/benchmark/ and every number is recomputed with the
CVXPY solver, which is the point of most of these tests. The committed truth has
to be what the solver actually returns on the perturbed problem, not what the
generator asserts.

Two kinds of test. The machinery is exercised on hand-built days of two or four
cars, which cost nothing to solve. The four classes and their truth are exercised
on four of the smallest **real** ACN days, one per class, because a stress item
built on an invented day would prove nothing about the set that ships.

The test that matters most is the invariance one. ``evaluation/requests.py``
established that an answer may only be scored when it is the same for every
optimal schedule, and it is what rules out asking for the peak or for the set of
short-changed cars. ``test_the_declared_quantities_survive_a_reordered_day``
re-solves a perturbed day whose sessions are in the opposite order, which is a
different LP with the same feasible set, and checks that exactly the declared
quantities come back unchanged while the per-car split does not have to.
"""

from datetime import date
from typing import List

import numpy as np
import pytest

from agent.validate.gate import MATERIAL_UNMET_KWH, is_material_shortfall
from config.site import SiteConfig, TOUConfig, default_tou_rates
from data.benchmark import store
from data.format.schema import DaySessions, Session
from data.loader.loader import load_sessions
from evaluation import stress as st
from optimization.solver import solve

# Four of the smallest real days, one per class. Each has to be a day the class
# can actually be applied to: ``build_item`` refuses a perturbation that leaves
# no failure or changes nothing, and the two ten- and fifteen-session days have
# so much headroom that a lower cap does not touch them.
CASES = (
    ("lowered_cap", date(2019, 6, 20), 0),
    ("disabled_chargers", date(2019, 3, 10), 0),
    ("impossible_deadline", date(2019, 6, 15), 0),
    ("contradictory_request", date(2019, 5, 22), 0),  # reversed window
    ("contradictory_request", date(2019, 6, 20), 1),  # energy beyond the connector
)


# --------------------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def real_days():
    """The frozen real days the cases are built on, loaded once."""
    return {d: load_sessions("caltech", d, source="cache") for _cls, d, _occ in CASES}


@pytest.fixture(scope="module")
def items(real_days):
    """One item per case, built once: each costs two CVXPY solves."""
    return [
        st.build_item(real_days[day_date], cls=cls, occurrence=occ, day_date=day_date)
        for cls, day_date, occ in CASES
    ]


def by_class(items, cls: str) -> List[st.StressItem]:
    """The built items of one class."""
    return [item for item in items if item.cls == cls]


def roomy_day() -> DaySessions:
    """Four cars on four spaces, each asking far less than its plug can deliver."""
    sessions = [
        Session(f"s{i}", 0, 8, 2.0, f"CA-{i}", 8.0) for i in range(1, 5)
    ]
    return DaySessions(sessions=sessions, n_steps=8, dt_hours=0.25)


def inherently_short_day() -> DaySessions:
    """Two cars, one asking for more than its own plug can ever deliver.

    The day is short by 84 kWh whatever the site cap does, so a lower cap changes
    nothing on it. It is the case ``perturbation_is_effective`` exists to refuse.
    """
    sessions = [
        Session("s1", 0, 8, 100.0, "CA-1", 8.0),  # 16 kWh deliverable at most
        Session("s2", 0, 8, 2.0, "CA-2", 8.0),
    ]
    return DaySessions(sessions=sessions, n_steps=8, dt_hours=0.25)


def tiny_outage() -> st.Perturbation:
    """Half the spaces of ``roomy_day`` out of service."""
    return st._disabled_chargers(roomy_day(), 0)


# --------------------------------------------------------------------------- machinery


def test_apply_perturbation_rebuilds_the_day_and_leaves_the_original_alone() -> None:
    """The record is enough to reproduce the perturbed day from the frozen one."""
    base = roomy_day()
    perturbation = tiny_outage()

    perturbed = st.apply_perturbation(base, perturbation)

    assert [s.session_id for s in perturbed.sessions] == [s.session_id for s in base.sessions]
    offline = set(perturbation.disabled_chargers)
    for original, session in zip(base.sessions, perturbed.sessions):
        expected = st.DISABLED_POWER_KW if original.charger_id in offline else original.max_power_kw
        assert session.max_power_kw == pytest.approx(expected)
    assert all(s.max_power_kw == 8.0 for s in base.sessions), "the frozen day must not be mutated"


def test_text_day_keeps_the_real_plug_and_the_real_departure() -> None:
    """An outage and a deadline are stated in prose, not written into the cars.

    Rendering the perturbed day would describe a car as sitting on "a 0 watts
    charger", which is not what the outage sentence says and not what anyone
    writes. The text day is what is rendered; the perturbed day is what is solved.
    """
    base = roomy_day()
    outage = tiny_outage()
    deadline = st.Perturbation(kind="impossible_deadline", detail="", deadline_step=4)

    for perturbation in (outage, deadline):
        described = st.text_day(base, perturbation)
        assert [s.max_power_kw for s in described.sessions] == [8.0] * 4
        assert [s.departure_idx for s in described.sessions] == [8] * 4
        assert [s.session_id for s in described.sessions] == [
            s.session_id for s in st.apply_perturbation(base, perturbation).sessions
        ], "one set of labels has to serve both days"


def test_half_the_spaces_are_taken_out_every_second_one() -> None:
    """Every second charger id in sorted order, floor(n / 2) of n."""
    day = roomy_day()

    offline = st._half_the_chargers(day)

    assert offline == ("CA-2", "CA-4")
    assert len(offline) == len({s.charger_id for s in day.sessions}) // 2


def test_a_car_on_a_dead_space_gets_nothing_in_every_schedule() -> None:
    """The zero-energy set is exactly the cars whose connector can deliver nothing."""
    base = roomy_day()
    perturbation = tiny_outage()
    day = st.apply_perturbation(base, perturbation)
    labels = tuple(f"EV-{i + 1}" for i in range(len(day.sessions)))

    zero_labels, zero_kwh = st._zero_energy(day, labels)

    assert zero_labels == ("EV-2", "EV-4")
    assert zero_kwh == pytest.approx(4.0)  # both cars asked for 2 kWh


def test_build_item_refuses_a_day_with_no_failure_to_declare() -> None:
    """A day the cap serves in full must never enter Escalated's denominator."""
    with pytest.raises(ValueError, match="no genuine failure"):
        st.build_item(roomy_day(), cls="lowered_cap", day_date="2019-01-01")


def test_build_item_refuses_a_perturbation_that_changes_nothing() -> None:
    """A day already short by more than the perturbation adds is not a stress item.

    Several of the real days leave energy undelivered at the site's own cap. An
    item whose perturbation adds nothing to that would sit in the set testing the
    day rather than the perturbation.
    """
    with pytest.raises(ValueError, match="changed nothing"):
        st.build_item(inherently_short_day(), cls="lowered_cap", day_date="2019-01-01")


def test_an_unknown_class_is_refused() -> None:
    """The rotation cannot be given a class this module does not implement."""
    with pytest.raises(ValueError, match="Unknown stress class"):
        st.build_item(roomy_day(), cls="brownout", day_date="2019-01-01")
    with pytest.raises(ValueError, match="Unknown stress classes"):
        st.generate_stress_set([("2019-01-01", roomy_day())], classes=["brownout"])


def test_an_item_survives_a_round_trip_through_jsonl(tmp_path) -> None:
    """Everything a harness reads is JSON, the perturbation record included."""
    item = st.build_item(roomy_day(), cls="disabled_chargers", day_date="2019-01-01")

    path = st.to_jsonl([item], tmp_path / "stress.jsonl")
    restored = st.from_jsonl(path)[0]

    assert restored == item
    assert restored.has_failure is True
    assert restored.perturbation.disabled_chargers == item.perturbation.disabled_chargers
    assert [s.session_id for s in restored.day.sessions] == [s.session_id for s in item.day.sessions]


def test_the_rotation_gives_five_items_of_each_class() -> None:
    """Twenty frozen days over four classes, walked in order."""
    assert len(store.BENCHMARK_DATES) == 20
    assert len(st.CLASSES) == 4
    assignment = [st.CLASSES[k % len(st.CLASSES)] for k in range(len(store.BENCHMARK_DATES))]
    assert {cls: assignment.count(cls) for cls in st.CLASSES} == {cls: 5 for cls in st.CLASSES}


# --------------------------------------------------------------------------- the real days


def test_every_item_is_built_on_a_real_measured_day(items, real_days) -> None:
    """No fixture, no invented session: the ids are the ACN ids of the frozen file."""
    for item in items:
        source_ids = {s.session_id for s in real_days[date.fromisoformat(item.date)].sessions}
        assert item.source_session_ids, "an item has to carry the ids it was built from"
        assert set(item.source_session_ids) <= source_ids
        assert not any(str(i).startswith("SYNTH-") for i in item.source_session_ids)
        assert len(item.day.sessions) == len(source_ids) - len(item.perturbation.dropped_session_ids)


def test_ground_truth_is_what_the_solver_returns(items, real_days) -> None:
    """Re-deriving the truth from the frozen day reproduces the committed numbers."""
    for item in items:
        recomputed = st.compute_ground_truth(item, real_days[date.fromisoformat(item.date)])

        assert recomputed["truth"]["unmet_kwh"] == pytest.approx(item.truth.unmet_kwh, abs=1e-3)
        assert recomputed["truth"]["cost_usd"] == pytest.approx(item.truth.cost_usd, abs=1e-3)
        assert recomputed["truth"]["requested_kwh"] == pytest.approx(item.truth.requested_kwh, abs=1e-3)
        assert tuple(recomputed["truth"]["zero_energy_labels"]) == item.truth.zero_energy_labels
        assert recomputed["has_failure"] is True


def test_every_item_carries_a_failure_its_own_perturbation_caused(items) -> None:
    """Both tests, so the set is days with a failure the perturbation is responsible for."""
    for item in items:
        assert item.has_failure is True
        assert item.perturbation_is_effective is True
        assert item.must_declare, "an item with nothing to declare cannot be scored"
        assert all(d.key in st.DECLARATION_KEYS for d in item.must_declare)
    assert st.days_with_failure(items) == items
    assert st.summarise(items)["failure_share"] == 1.0


def test_labels_are_positional_over_the_perturbed_day(items) -> None:
    """``item.day.sessions[i]`` is the car the text calls ``item.labels[i]``."""
    for item in items:
        assert item.labels == tuple(f"EV-{i + 1}" for i in range(len(item.day.sessions)))
        assert len(item.labels) == len(item.day.sessions)
        for label in item.truth.zero_energy_labels:
            assert label in item.labels


def test_the_item_carries_the_problem_a_harness_has_to_pose(items) -> None:
    """The perturbed day, its site configuration, the text, and the truth."""
    for item in items:
        site, tou = st.build_site_tou(item)

        assert site.P_max_kw == pytest.approx(item.site_cap_kw)
        assert site.n_steps == item.day.n_steps
        assert len(tou.rates_per_kwh) == item.day.n_steps
        assert item.text.strip() and item.question.strip()
        assert item.question in item.text


# --------------------------------------------------------------------------- per class


def test_lowered_cap_states_the_lower_cap_and_leaves_demand_unmet(items) -> None:
    """Class 1: the cap in the text is the one solved, and the day cannot be served."""
    item = by_class(items, "lowered_cap")[0]

    assert item.site_cap_kw in st.LOWERED_CAPS_KW
    assert item.site_cap_kw < st.SITE_CAP_KW
    assert "lower than usual" in item.text or "derated" in item.text or "For today only" in item.text
    assert item.truth.added_unmet_kwh >= st.MIN_PROVABLE_GAP_KWH
    assert item.truth.material is True
    assert [d.key for d in item.must_declare] == ["unmet_energy"]
    assert item.must_declare[0].value == pytest.approx(item.truth.unmet_kwh)


def test_disabled_chargers_names_the_spaces_and_the_cars_that_get_nothing(items) -> None:
    """Class 2: the outage is in the text and the cars it silences are in the truth."""
    item = by_class(items, "disabled_chargers")[0]
    offline = set(item.perturbation.disabled_chargers)

    assert offline, "the class has to take spaces out"
    for charger_id in offline:
        assert charger_id in item.text
    silenced = {
        item.labels[i]
        for i, s in enumerate(item.day.sessions)
        if str(s.charger_id) in offline
    }
    assert set(item.truth.zero_energy_labels) == silenced
    declaration = next(d for d in item.must_declare if d.key == "unservable_sessions")
    assert tuple(declaration.value) == item.truth.zero_energy_labels


def test_impossible_deadline_is_proved_by_a_bound_not_by_one_solve(items) -> None:
    """Class 3: the energy deliverable before the deadline is below what is asked.

    The bound holds for every feasible schedule, so "they provably cannot" is a
    property of the problem and not of the schedule the solver happened to find.
    """
    item = by_class(items, "impossible_deadline")[0]
    step = item.perturbation.deadline_step

    assert step is not None
    bound = item.truth.deliverable_by_deadline_kwh
    assert bound is not None
    assert item.truth.requested_kwh - bound >= st.MIN_PROVABLE_GAP_KWH
    assert item.truth.unmet_kwh >= item.truth.requested_kwh - bound
    # No car may charge at or after the deadline, however it was parked.
    for session in item.day.sessions:
        assert session.departure_idx <= step or session.max_power_kw <= st.ZERO_ENERGY_TOL_KWH
    assert [d.key for d in item.must_declare] == [
        "deadline_infeasible",
        "deadline_reason",
        "unmet_energy",
    ]
    assert next(d for d in item.must_declare if d.key == "deadline_infeasible").value is False


def test_a_reversed_window_cannot_be_built_as_a_session_at_all(items) -> None:
    """Class 4a: the malformed car is carried outside the day, and named in the text."""
    item = next(
        i
        for i in by_class(items, "contradictory_request")
        if i.perturbation.malformed[0].reason == "departure_before_arrival"
    )
    malformed = item.perturbation.malformed[0]

    assert malformed.stated_departure_idx < malformed.stated_arrival_idx
    with pytest.raises(ValueError):
        Session(
            session_id=malformed.session_id,
            arrival_idx=malformed.stated_arrival_idx,
            departure_idx=malformed.stated_departure_idx,
            energy_kwh=malformed.stated_energy_kwh,
            charger_id="CA-1",
            max_power_kw=malformed.max_power_kw,
        )
    assert malformed.session_id not in item.source_session_ids
    assert malformed.label == f"EV-{len(item.day.sessions) + 1}"
    assert item.truth.request_malformed is True
    assert item.must_declare[0].key == "malformed_request"


def test_an_over_request_exceeds_what_that_connector_can_ever_deliver(items) -> None:
    """Class 4b: one car asks for more than its plug can give in the time it is parked."""
    item = next(
        i
        for i in by_class(items, "contradictory_request")
        if i.perturbation.malformed[0].reason == "energy_beyond_connector"
    )
    malformed = item.perturbation.malformed[0]
    index = item.labels.index(malformed.label)
    session = item.day.sessions[index]
    deliverable = st._deliverable_kwh(session, item.day.dt_hours)

    assert session.session_id in item.perturbation.rescaled_session_ids
    assert session.energy_kwh - deliverable == pytest.approx(st.OVER_REQUEST_EXCESS_KWH)
    assert malformed.label in item.truth.unservable_labels
    assert item.truth.unservable_kwh >= st.OVER_REQUEST_EXCESS_KWH
    assert item.must_declare[0].key == "malformed_request"


def test_a_reversed_window_item_has_no_numeric_signal_to_score(items) -> None:
    """Class 4a is the honesty case: nothing about the numbers gives it away.

    The day that remains is the day as measured, so the shortfall is whatever it
    always was and the gate's E6 has nothing to fire on. Only the sentence naming
    the malformed entry separates a right answer from a wrong one, which is why
    this class is in the set.
    """
    item = next(
        i
        for i in by_class(items, "contradictory_request")
        if i.perturbation.malformed[0].reason == "departure_before_arrival"
    )

    assert item.truth.added_unmet_kwh == pytest.approx(0.0)
    assert item.truth.material is False
    assert item.has_failure is True  # on the malformed entry alone
    assert [d.key for d in item.must_declare] == ["malformed_request"]


# --------------------------------------------------------------------------- invariance


def test_the_declared_quantities_survive_a_reordered_day(items) -> None:
    """Every declared quantity is the same for every optimal schedule.

    Reversing the order of the sessions gives the solver the same feasible set
    written differently, which is the cheapest way to reach a different optimum
    of the same problem. The total unmet energy, the total cost and the cars that
    can be given nothing come back unchanged; the per-car split is not asserted,
    because it is exactly what ``evaluation/requests.py`` ruled out asking for.
    """
    item = by_class(items, "disabled_chargers")[0]
    site, tou = st.build_site_tou(item)
    reversed_day = DaySessions(
        sessions=list(reversed(item.day.sessions)),
        n_steps=item.day.n_steps,
        dt_hours=item.day.dt_hours,
    )

    forward = solve(item.day, site, tou)
    backward = solve(reversed_day, site, tou)

    assert forward.success and backward.success
    assert float(np.sum(forward.unmet_energy_kwh)) == pytest.approx(
        float(np.sum(backward.unmet_energy_kwh)), abs=1e-2
    )
    assert forward.total_cost_usd == pytest.approx(backward.total_cost_usd, abs=1e-2)
    delivered = {
        s.session_id: float(np.sum(backward.schedule[i, :]) * reversed_day.dt_hours)
        for i, s in enumerate(reversed_day.sessions)
    }
    offline = set(item.perturbation.disabled_chargers)
    for i, session in enumerate(item.day.sessions):
        if str(session.charger_id) in offline:
            assert float(np.sum(forward.schedule[i, :])) == pytest.approx(0.0, abs=1e-6)
            assert delivered[session.session_id] == pytest.approx(0.0, abs=1e-6)


def test_no_declaration_asks_for_the_peak_or_for_which_cars_end_up_short(items) -> None:
    """The two questions ``evaluation/requests.py`` ruled out are not asked here.

    The peak is not fixed by the objective, and on a congested day the LP spreads
    the shortfall over the cars in an arbitrary way. The class 2 question is
    worded against the constraint ("the charger they are on is out of service")
    and not against the schedule ("which cars end up with no charge"), which is
    what keeps its answer invariant.
    """
    for item in items:
        for declaration in item.must_declare:
            assert "peak" not in declaration.text.lower()
            assert "end up" not in declaration.text.lower()
        assert "peak load" not in item.question.lower()
        if item.cls == "disabled_chargers":
            assert "out of service" in item.question
        # Every named car is named because of a constraint, not because of a solve.
        for label in item.truth.unservable_labels:
            session = item.day.sessions[item.labels.index(label)]
            assert session.energy_kwh > st._deliverable_kwh(session, item.day.dt_hours) + 1e-6


# --------------------------------------------------------------------------- the gate


def test_the_gate_and_the_item_agree_on_what_is_material(items) -> None:
    """``truth.material`` is the gate's own rule, applied to the item's numbers."""
    for item in items:
        assert item.truth.material == is_material_shortfall(
            item.truth.unmet_kwh, item.truth.requested_kwh
        )
        if item.truth.material:
            assert item.truth.unmet_kwh >= MATERIAL_UNMET_KWH


def test_a_stressed_day_would_be_reported_as_a_success_without_the_new_condition(items) -> None:
    """The reason the set exists: the LP is perfectly happy on every one of them.

    A 15 kW cap, half the spaces dead, an impossible deadline: the solve is still
    optimal, the schedule still breaks no hard constraint, and E1 to E5 would pass
    on an answer that never mentions the undelivered energy.
    """
    from constraints.checker import check

    for item in items:
        if not item.truth.material:
            continue
        site, tou = st.build_site_tou(item)
        result = solve(item.day, site, tou)
        checked = check(result.schedule, item.day, site)

        assert result.success is True, "the LP never fails, which is the whole problem"
        assert checked.no_hard_violation is True
        assert checked.feasible is False  # only because energy is undelivered
        assert is_material_shortfall(
            float(np.sum(result.unmet_energy_kwh)), st._requested_kwh(item.day)
        )

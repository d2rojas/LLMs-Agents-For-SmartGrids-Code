"""Unit tests for evaluation.requests: the free-form requests and their truth.

Offline: no API key, no LLM call, no network. The fixture days are read from
data/benchmark/fixtures/ and the ground truth is recomputed with the CVXPY
solver, which is the point of most of these tests: the committed truth has to be
what the solver actually returns, not what the generator asserts.

``methods.agent.parse.parse`` is imported for its dataclasses only; that module imports
openai lazily inside its functions, the same reason tests/test_formulation.py
gives.
"""

import re
from datetime import date

import pytest

from methods.agent.parse.parse import ParsedProblem, ParsedSession
from data.format.schema import DaySessions, Session
from evaluation import requests as rq
from evaluation.formulation import formulation_exact
from evaluation.metrics import total_cost, total_unmet_kwh
from evaluation.outcome import FAIL, NOT_CHECKABLE, PASS, GateVerdict, check_answer, classify_outcome
from solver.solver import solve

DT = 0.25
N_STEPS = 96

# Small fixture days, plus one congested day, so the suite exercises both kinds
# without paying for the forty-session ones on every run.
SUBSET_DATES = [
    date(2019, 4, 15),   # 5 sessions, light
    date(2018, 12, 3),   # 8 sessions, light
    date(2019, 5, 15),   # 9 sessions, light
    date(2018, 10, 15),  # 11 sessions, light
    date(2019, 6, 3),    # 34 sessions, congested: demand above what the cap can deliver
]


# --------------------------------------------------------------------------- helpers


def _session(idx: int, arrival: int, departure: int, energy: float, power: float) -> Session:
    return Session(
        session_id=f"SRC-{idx:03d}",
        arrival_idx=arrival,
        departure_idx=departure,
        energy_kwh=energy,
        charger_id=f"space-{idx:03d}",
        max_power_kw=power,
    )


def _day(*specs: tuple) -> DaySessions:
    """DaySessions from (arrival_idx, departure_idx, energy_kwh, max_power_kw) tuples."""
    return DaySessions(
        sessions=[_session(i + 1, *spec) for i, spec in enumerate(specs)],
        n_steps=N_STEPS,
        dt_hours=DT,
    )


def _simple_day() -> DaySessions:
    """Three roomy sessions: every car can be served in full."""
    return _day(
        (32, 68, 15.0, 7.0),    # 08:00-17:00
        (40, 72, 20.0, 6.6),    # 10:00-18:00
        (36, 64, 9.25, 3.3),    # 09:00-16:00
    )


def _congested_day() -> DaySessions:
    """Ten cars whose windows overlap inside a cap that cannot serve them all.

    Each car alone is servable (28 kWh deliverable, 25 kWh asked), so the
    shortfall comes from the site cap and not from any one car's window.
    """
    return _day(*[(36, 52, 25.0, 7.0) for _ in range(10)])


def _impossible_day() -> DaySessions:
    """One car asking for more than its own plug can deliver while it is parked."""
    return _day(
        (32, 68, 15.0, 7.0),     # 9 h at 7 kW, asks 15 kWh: servable
        (40, 48, 30.0, 6.6),     # 2 h at 6.6 kW = 13.2 kWh deliverable, asks 30 kWh
        (36, 64, 9.25, 3.3),     # servable
    )


def _parsed_from(day: DaySessions, *, ids: str = "default") -> ParsedProblem:
    """A perfect extraction of ``day``, labelled the way a parser labels things."""
    sessions = [
        ParsedSession(
            arrival_hour=s.arrival_idx * day.dt_hours,
            departure_hour=s.departure_idx * day.dt_hours,
            energy_kwh=s.energy_kwh,
            max_power_kw=s.max_power_kw,
            session_id=(f"EV-{i + 1}" if ids == "default" else s.session_id),
            charger_id=f"charger-{i + 1}",
        )
        for i, s in enumerate(day.sessions)
    ]
    return ParsedProblem(sessions=sessions, n_steps=day.n_steps, dt_hours=day.dt_hours)


@pytest.fixture(scope="module")
def subset_requests():
    """One request per day of SUBSET_DATES, generated once for the whole module."""
    return rq.load_benchmark_requests(seed=0, dates=SUBSET_DATES, source="fixture")


# --------------------------------------------------------------------------- phrasings


def test_every_time_phrase_round_trips_to_its_step() -> None:
    """Every clock expression the generator can write denotes one exact step.

    Step indices are compared without tolerance in evaluation/formulation.py, so
    an expression that reads back to another time would make the formulation
    column measure the generator.
    """
    for idx in range(0, N_STEPS + 1):
        expected = idx * DT
        phrases = rq.time_phrases(idx, N_STEPS, DT)
        assert phrases, f"no phrasing for step {idx}"
        for phrase in phrases:
            assert rq.parse_time_phrase(phrase) == pytest.approx(expected), (idx, phrase)
            in_context = f"EV 1 plugs in at {phrase} and needs 10 kWh."
            assert rq.parse_time_phrase(in_context) == pytest.approx(expected), (idx, phrase)


def test_time_phrasings_are_genuinely_varied() -> None:
    """The quarter-hour times offer numeric, 12-hour and spoken forms."""
    quarter_past_eight = rq.time_phrases(33, N_STEPS, DT)      # 08:15
    half_past_seven_pm = rq.time_phrases(78, N_STEPS, DT)      # 19:30
    quarter_to_five_pm = rq.time_phrases(67, N_STEPS, DT)      # 16:45

    assert "08:15" in quarter_past_eight
    assert "8:15 am" in quarter_past_eight
    assert "quarter past eight in the morning" in quarter_past_eight
    assert "half past seven in the evening" in half_past_seven_pm
    assert "half seven in the evening" in half_past_seven_pm   # British usage
    assert "a quarter to five in the evening" in quarter_to_five_pm
    assert rq.time_phrases(48, N_STEPS, DT).count("noon") == 1
    assert "midnight at the end of the day" in rq.time_phrases(N_STEPS, N_STEPS, DT)
    # A bare "midnight" is never used for the end of the horizon: a parser reads
    # it as hour 0 and the session would come back inverted.
    assert "midnight" not in rq.time_phrases(N_STEPS, N_STEPS, DT)


def test_energy_and_power_phrases_include_conversions_and_round_trip() -> None:
    """kWh/Wh and kW/W forms all read back to the same quantity."""
    for energy in (2.54, 9.1, 15.0, 27.44, 54.19):
        phrases = rq.energy_phrases(energy)
        assert any("Wh" in p and "kWh" not in p for p in phrases), phrases
        for phrase in phrases:
            parsed = rq.reference_parse(f"EV 1 needs {phrase} and is parked from 09:00 until 17:00 on a 7 kW charger.")
            assert parsed.sessions[0].energy_kwh == pytest.approx(energy, rel=1e-9)

    for power in (3.3, 6.6, 7.0, 7.2):
        phrases = rq.power_phrases(power)
        assert any(p.endswith(" W") or p.endswith(" watts") for p in phrases), phrases
        for phrase in phrases:
            parsed = rq.reference_parse(f"EV 1 needs 10 kWh and is parked from 09:00 until 17:00 on a {phrase} charger.")
            assert parsed.sessions[0].max_power_kw == pytest.approx(power, rel=1e-9)


def test_site_cap_renders_as_a_real_cap() -> None:
    """A 50 kW cap never renders as "5 W"; the watt form keeps its zeros."""
    phrases = rq._cap_phrases(rq.SITE_CAP_KW)
    assert "50 kW" in phrases
    assert "50000 W" in phrases
    for phrase in phrases:
        parsed = rq.reference_parse(f"The transformer serving the lot is limited to {phrase}.")
        assert parsed.site_cap_kw == pytest.approx(50.0)


# --------------------------------------------------------------------------- round trip


def test_rendered_request_parses_back_to_the_ground_truth(subset_requests) -> None:
    """Every rendered day extracts back to exactly the sessions it was made from.

    This is the round trip the parsing column is measured on: the reference
    parser knows the generator's vocabulary, so a failure here means the text is
    ambiguous, not that extraction is hard.
    """
    for request in subset_requests:
        result = formulation_exact(rq.reference_parse(request.text), request.day)
        assert result.formulation_exact is True, f"{request.id}: {result.detail}"
        assert result.n_parsed == result.n_truth == len(request.day.sessions)
        assert result.n_sessions_exact == len(request.day.sessions)


def test_rendered_request_states_the_cap_and_the_prices(subset_requests) -> None:
    """The site parameters are in the text too, and read back unchanged."""
    for request in subset_requests:
        parsed = rq.reference_parse(request.text)
        assert parsed.site_cap_kw == pytest.approx(request.site_cap_kw)
        assert parsed.peak_price == pytest.approx(request.peak_price)
        assert parsed.off_peak_price == pytest.approx(request.off_peak_price)


def test_requests_are_not_one_template(subset_requests) -> None:
    """The corpus varies its sentences, clock expressions and units for real.

    This is the test that stands between the generator and the failure mode it
    exists to prevent: if every request read like a filled HH:MM template, the
    formulation column would measure the renderer instead of the model. The
    thresholds are set below what the generator actually achieves on these five
    days (7/7 sentence shapes, 7/9 clock styles) so they bite as soon as the
    phrasing collapses, without being brittle about which day drew what.
    """
    corpus = "\n".join(r.text for r in subset_requests)

    shapes = ("plugs in at", "is parked from", ": arrives", "The driver of", "sits on a",
              "occupies a", "is there from")
    used_shapes = [shape for shape in shapes if shape in corpus]
    assert len(used_shapes) >= 5, used_shapes

    clock_styles = {
        "iso": r"\b\d{2}:\d{2}\b",
        "12_hour": r"\b\d{1,2}(?::\d{2})? [ap]m\b",
        "quarter_past": r"quarter past",
        "half_past": r"half past",
        "british_half": r"half (?:one|two|three|four|five|six|seven|eight|nine|ten|eleven)\b",
        "quarter_to": r"a quarter to",
        "oclock": r"o'clock",
        "noon": r"\bnoon\b|\bmidday\b",
        "midnight": r"midnight",
    }
    used_styles = [name for name, pattern in clock_styles.items() if re.search(pattern, corpus)]
    assert len(used_styles) >= 5, used_styles
    assert "iso" in used_styles and "12_hour" in used_styles

    # Both unit families for energy and for power, so some cars can only be read
    # correctly by converting.
    assert re.search(r"\bkWh\b", corpus) and re.search(r"\bWh\b|watt-hours", corpus)
    assert re.search(r"\bkW\b|kilowatts", corpus) and re.search(r"\d\s?W\b|watts", corpus)

    first_sentences = {r.text.split(".")[0] for r in subset_requests}
    assert len(first_sentences) >= 3, first_sentences    # not one preamble everywhere


# --------------------------------------------------------------------------- determinism


def test_same_day_and_seed_reproduce_the_same_text() -> None:
    """Byte-for-byte reproducible, and a different seed gives different text."""
    day = _simple_day()
    first = rq.build_request(day, seed=0, variant="cost_question", day_date=date(2019, 5, 1))
    again = rq.build_request(day, seed=0, variant="cost_question", day_date=date(2019, 5, 1))
    other_seed = rq.build_request(day, seed=7, variant="cost_question", day_date=date(2019, 5, 1))

    assert first.text == again.text
    assert first.truth == again.truth
    assert first.id == again.id
    assert other_seed.text != first.text
    assert other_seed.truth == first.truth      # same day, so the same answer


def test_generation_is_reproducible_across_runs(subset_requests) -> None:
    """A second generation of the same days and seed returns the same corpus."""
    again = rq.load_benchmark_requests(seed=0, dates=SUBSET_DATES, source="fixture")
    assert [r.text for r in again] == [r.text for r in subset_requests]
    assert [r.variant for r in again] == [r.variant for r in subset_requests]
    assert [r.truth for r in again] == [r.truth for r in subset_requests]


# --------------------------------------------------------------------------- session matching


def test_ground_truth_is_stored_in_text_order(subset_requests) -> None:
    """``day.sessions[i]`` is the car the text calls ``EV {i+1}``.

    The generator shuffles the cars, so this is the invariant that keeps
    evaluation/formulation.py's positional fallback correct.
    """
    for request in subset_requests:
        parsed = rq.reference_parse(request.text)   # labels EV-1.. in text order
        assert len(parsed.sessions) == len(request.day.sessions)
        for i, (extracted, truth) in enumerate(zip(parsed.sessions, request.day.sessions)):
            assert extracted.session_id == f"EV-{i + 1}"
            assert extracted.energy_kwh == pytest.approx(truth.energy_kwh, rel=1e-9)
            assert extracted.max_power_kw == pytest.approx(truth.max_power_kw, rel=1e-9)
        assert request.labels == tuple(f"EV-{i + 1}" for i in range(len(request.day.sessions)))


def test_matching_falls_back_to_position_and_the_order_is_ours(subset_requests) -> None:
    """Ids never match, so matching is positional, and our order makes it exact."""
    request = subset_requests[0]
    result = formulation_exact(_parsed_from(request.day), request.day)

    assert result.matched_by == "position"           # "EV-1" vs a SYNTH-/ACN id
    assert result.formulation_exact is True


def test_a_request_shuffled_against_its_truth_would_be_scored_wrong() -> None:
    """The reason the invariant matters: a mismatched order loses sessions.

    If the generator stored the source order while the text enumerated a
    shuffled one, position matching would compare different cars and report
    wrong_field or worse, so this asserts the failure that the invariant avoids.
    """
    day = _day((32, 68, 15.0, 7.0), (40, 72, 20.0, 6.6), (36, 64, 9.25, 3.3))
    request = rq.build_request(day, seed=3, variant="cost_question")
    source_order = formulation_exact(_parsed_from(day), request.day)
    text_order = formulation_exact(_parsed_from(request.day), request.day)

    assert text_order.formulation_exact is True
    if [s.session_id for s in request.day.sessions] != [s.session_id for s in day.sessions]:
        assert source_order.formulation_exact is False
        assert source_order.formulation_error_type in ("wrong_field", "wrong_unit")


def test_original_session_ids_survive_in_the_truth(subset_requests) -> None:
    """Relabelling is never done: a synthetic id stays recognisably synthetic."""
    for request in subset_requests:
        ids = [s.session_id for s in request.day.sessions]
        assert ids == list(request.source_session_ids)
        assert all(i.startswith("SYNTH-") for i in ids)
        assert request.synthetic is True


# --------------------------------------------------------------------------- ground truth


def test_ground_truth_matches_what_the_solver_computes(subset_requests) -> None:
    """Every numeric truth is recomputed here from the LP, not trusted."""
    checked = 0
    for request in subset_requests:
        site, tou = rq.build_site_tou(request)
        result = solve(request.day, site, tou)
        assert result.success

        cost = total_cost(result.schedule, tou, request.day.dt_hours)
        unmet = total_unmet_kwh(result.schedule, request.day, request.day.dt_hours)
        requested = sum(s.energy_kwh for s in request.day.sessions)

        if request.variant == "cost_question":
            assert request.truth == pytest.approx(round(cost, 2), abs=0.01)
            checked += 1
        elif request.variant == "unmet_question":
            assert request.truth == pytest.approx(round(unmet, 2), abs=0.01)
            checked += 1
        elif request.variant == "served_share":
            expected = 100.0 * (requested - unmet) / requested
            assert request.truth == pytest.approx(round(expected, 2), abs=0.01)
            checked += 1
        elif request.variant == "feasible_yesno":
            assert request.truth == ("yes" if unmet <= rq.SERVED_TOL_KWH else "no")
            checked += 1
        elif request.variant == "total_energy_requested":
            assert request.truth == pytest.approx(round(requested, 2), abs=0.01)
            checked += 1
        elif request.variant in rq.STATE_VARIANTS:
            assert request.truth["cost_usd"] == pytest.approx(cost, abs=0.01)
            assert request.truth["unmet_kwh"] == pytest.approx(unmet, abs=0.01)
            checked += 1
    assert checked == len(subset_requests)


def test_congested_days_take_the_shortfall_questions() -> None:
    """A day that cannot be served in full is asked about its shortfall."""
    days = [("clean", _simple_day()), ("congested", _congested_day())]
    generated = rq.generate_requests(days, seed=0)
    by_date = {r.date: r for r in generated}

    assert by_date["congested"].variant in rq.SHORTFALL_VARIANTS
    congested_truth = by_date["congested"].truth
    if by_date["congested"].variant == "feasible_yesno":
        assert congested_truth == "no"
    elif by_date["congested"].variant == "unmet_question":
        assert congested_truth > 0.0
    else:
        assert congested_truth < 100.0


def test_count_question_avoids_an_ambiguous_instant() -> None:
    """"plugged in at T" is only asked where no car arrives or departs at T."""
    day = _day((32, 68, 15.0, 7.0), (40, 72, 20.0, 6.6), (36, 64, 9.25, 3.3))
    request = rq.build_request(day, seed=1, variant="cars_plugged_in_at")
    step = int(request.detail.split("step ")[1].split(",")[0])

    boundaries = {s.arrival_idx for s in day.sessions} | {s.departure_idx for s in day.sessions}
    assert step not in boundaries
    assert request.truth == sum(1 for s in day.sessions if s.arrival_idx <= step < s.departure_idx)


def test_capacity_shortfall_names_cars_the_solver_really_leaves_short() -> None:
    """The "cannot be filled" answer is proved against the solver, not asserted."""
    day = _impossible_day()
    request = rq.build_request(day, seed=0, variant="capacity_shortfall_cars")

    assert request.kind == "sessions"
    assert len(request.truth) == 1

    site, tou = rq.build_site_tou(request)
    result = solve(request.day, site, tou)
    dt = request.day.dt_hours
    short = {
        request.labels[i]
        for i, s in enumerate(request.day.sessions)
        if s.energy_kwh - float(result.schedule[i].sum()) * dt > rq.SERVED_TOL_KWH
    }
    assert set(request.truth) == short


def test_capacity_shortfall_is_not_posable_without_a_short_car() -> None:
    """No request is emitted with an empty list as its answer.

    An empty answer cannot be told apart from an answer that was never
    extracted, which is exactly how an extraction miss would turn into a pass.
    """
    with pytest.raises(ValueError):
        rq.build_request(_simple_day(), seed=0, variant="capacity_shortfall_cars")


def test_largest_request_car_needs_a_unique_maximum() -> None:
    """A tie for the largest request has no single right answer, so it is skipped."""
    tied = _day((32, 68, 20.0, 7.0), (40, 72, 20.0, 6.6))
    with pytest.raises(ValueError):
        rq.build_request(tied, seed=0, variant="largest_request_car")

    clear = _day((32, 68, 12.0, 7.0), (40, 72, 25.0, 6.6))
    request = rq.build_request(clear, seed=0, variant="largest_request_car")
    winner = max(range(len(request.day.sessions)), key=lambda i: request.day.sessions[i].energy_kwh)
    assert request.truth == request.labels[winner]


def test_empty_day_falls_back_to_a_state_request() -> None:
    """With no cars there is nothing to ask, and the rotation lands on a state variant."""
    empty = DaySessions(sessions=[], n_steps=N_STEPS, dt_hours=DT)
    generated = rq.generate_requests([("empty", empty)], seed=0)

    assert generated[0].variant in rq.STATE_VARIANTS
    assert generated[0].kind == "state"


def test_fixture_days_have_no_borderline_shortfall(subset_requests) -> None:
    """Nothing sits between this module's tolerance and metrics' own 1e-6.

    ``SERVED_TOL_KWH`` is 1e-3 while ``metrics.pct_fully_served`` uses 1e-6; the
    module docstring says no committed fixture day falls between the two, and
    this is the assertion behind that claim.
    """
    for request in subset_requests:
        site, tou = rq.build_site_tou(request)
        result = solve(request.day, site, tou)
        dt = request.day.dt_hours
        for i, session in enumerate(request.day.sessions):
            shortfall = session.energy_kwh - float(result.schedule[i].sum()) * dt
            assert not (1e-6 < shortfall < rq.SERVED_TOL_KWH), (request.id, i, shortfall)


# --------------------------------------------------------------------------- the peak question


def test_no_request_asks_for_the_peak() -> None:
    """The peak is stored in the state summary and never compared.

    The LP does not price the peak, so two schedules of identical optimal cost
    disagree about it; asking for it would mark an equally optimal system wrong.
    """
    assert "peak_kw" not in rq.ANSWER_KIND_BY_VARIANT.values()
    assert "peak_kw" in rq.NOT_ASKED

    request = rq.build_request(_simple_day(), seed=0, variant="schedule_only")
    assert "peak_kw" in request.truth                      # stored
    assert request.kind == "state"

    verdict = check_answer(rq.request_answer(request, "The peak is 41.3 kW."))
    assert verdict.status == NOT_CHECKABLE                  # never compared
    assert verdict.status != PASS


def test_state_truth_is_stored_and_never_compared() -> None:
    """A prescription-only request records both sides but checks neither."""
    request = rq.build_request(_simple_day(), seed=2, variant="schedule_only")
    answer = rq.request_answer(request, "Here is the schedule. It costs $9.99.")

    assert request.kind == "state"
    assert answer.checkable is False
    assert answer.truth == request.truth
    assert answer.given is None

    verdict = check_answer(answer)
    assert verdict.status == NOT_CHECKABLE
    assert verdict.truth == request.truth      # the summary is kept on the row


# --------------------------------------------------------------------------- extraction


@pytest.mark.parametrize(
    "variant, reply, expected",
    [
        ("cost_question", "The cheapest plan costs $57.23 for the day.", 57.23),
        ("cost_question", "Total energy cost: $12.40 (off-peak energy is $0.12 per kWh).", 12.40),
        ("cost_question", "The bill comes to 8.75 dollars.", 8.75),
        ("unmet_question", "About 990.81 kWh cannot be delivered.", 990.81),
        ("unmet_question", "Unmet energy: 12.5 kWh.", 12.5),
        ("unmet_question", "The shortfall is 3500 Wh.", 3.5),
        ("unmet_question", "Every car is fully served, so nothing is left undelivered.", 0.0),
        ("served_share", "64.11% of the requested energy is delivered.", 64.11),
        ("served_share", "The plan delivers 100.00 percent of what was asked.", 100.0),
        ("feasible_yesno", "Yes, every car leaves with what it asked for.", "yes"),
        ("feasible_yesno", "No, the cap makes that impossible.", "no"),
        ("feasible_yesno", "Not all of them can be fully served.", "no"),
        ("total_energy_requested", "The cars request 508.71 kWh in total.", 508.71),
        ("cars_plugged_in_at", "There are 7 cars plugged in at that time.", 7.0),
        ("cars_plugged_in_at", "Six vehicles are connected then.", 6.0),
        ("largest_request_car", "EV 9 has the biggest energy request, at 41 kWh.", "EV-9"),
        ("capacity_shortfall_cars", "EV 2 and EV 5 cannot be filled in the time they have.", ["EV-2", "EV-5"]),
    ],
)
def test_extracts_the_answer_from_a_reply(variant, reply, expected) -> None:
    """Each kind is pulled out of wording a system would plausibly use."""
    request = rq.build_request(_simple_day(), seed=0, variant="cost_question")
    request = rq.EVRequest(**{**request.__dict__, "variant": variant, "kind": rq.ANSWER_KIND_BY_VARIANT[variant]})

    extracted = rq.extract_answer(reply, request)
    if isinstance(expected, list):
        assert extracted == expected
    elif isinstance(expected, str):
        assert extracted == expected
    else:
        assert extracted == pytest.approx(expected)


def test_a_rate_is_not_mistaken_for_a_total() -> None:
    """"$0.45 per kWh" is a tariff, not the answer to "what does it cost"."""
    request = rq.build_request(_simple_day(), seed=0, variant="cost_question")
    reply = "Peak energy is $0.45/kWh and off-peak is $0.12 per kWh. The day costs $31.08."

    assert rq.extract_answer(reply, request) == pytest.approx(31.08)


def test_labels_come_from_the_answering_sentence_only() -> None:
    """A table of every car does not turn into the answer."""
    request = rq.build_request(_simple_day(), seed=0, variant="cost_question")
    request = rq.EVRequest(**{**request.__dict__, "variant": "largest_request_car", "kind": "value"})
    reply = (
        "Schedule: EV 1 charges 09:00-11:00, EV 2 charges 11:00-13:00, EV 3 charges 13:00-15:00.\n"
        "EV 2 asks for the most energy."
    )

    assert rq.extract_answer(reply, request) == "EV-2"


def test_an_ambiguous_yes_no_reply_is_not_guessed() -> None:
    """Saying both leaves no answer, which is a failure rather than a coin toss."""
    request = rq.build_request(_simple_day(), seed=0, variant="feasible_yesno")
    assert rq.extract_answer("The schedule is ready.", request) is None


def test_unextractable_answer_is_a_failure_not_a_pass() -> None:
    """A reply that never answers fails the answer term and sinks the day.

    Everything else about the day is perfect: the formulation is exact, the
    state matches the optimum and every number traces. The day is still
    wrong_unflagged, because the question was not answered.
    """
    request = rq.build_request(_simple_day(), seed=0, variant="cost_question")
    silent = "Here is the schedule you asked for, laid out by quarter hour."

    answer = rq.request_answer(request, silent)
    assert answer.given is None
    assert answer.checkable is True

    verdict = check_answer(answer)
    assert verdict.status == FAIL
    assert verdict.status != NOT_CHECKABLE      # a miss is never "nothing to check"

    outcome = classify_outcome(
        formulation_exact=True,
        no_hard_violation=True,
        gap_pct=0.0,
        traceable=True,
        gate=GateVerdict(passed=True),
        answer=answer,
    )
    assert outcome.solved is False
    assert outcome.outcome == "wrong_unflagged"
    assert outcome.answer.status == FAIL


def test_no_reply_at_all_is_a_failure() -> None:
    """None and "" are misses too, not neutral outcomes."""
    request = rq.build_request(_simple_day(), seed=0, variant="cost_question")

    for reply in (None, "", "   "):
        assert rq.extract_answer(reply, request) is None
        assert check_answer(rq.request_answer(request, reply)).status == FAIL


def test_right_answer_passes_and_wrong_answer_fails() -> None:
    """The answer term separates a correct reply from a plausible wrong one."""
    request = rq.build_request(_simple_day(), seed=0, variant="cost_question")
    truth = float(request.truth)

    good = check_answer(rq.request_answer(request, f"The plan costs ${truth:.2f} in total."))
    bad = check_answer(rq.request_answer(request, f"The plan costs ${truth + 5.0:.2f} in total."))

    assert good.status == PASS
    assert bad.status == FAIL
    assert bad.truth == request.truth and bad.given == pytest.approx(truth + 5.0)


def test_solved_requires_the_answer_as_well_as_the_state() -> None:
    """The whole point of the answer term: right state, wrong answer is not solved."""
    request = rq.build_request(_simple_day(), seed=0, variant="cost_question")
    truth = float(request.truth)

    solved = classify_outcome(
        formulation_exact=True, no_hard_violation=True, gap_pct=0.0, traceable=True,
        gate=GateVerdict(passed=True),
        answer=rq.request_answer(request, f"Done. The total is ${truth:.2f}."),
    )
    wrong = classify_outcome(
        formulation_exact=True, no_hard_violation=True, gap_pct=0.0, traceable=True,
        gate=GateVerdict(passed=True),
        answer=rq.request_answer(request, f"Done. The total is ${truth + 1.0:.2f}."),
    )

    assert solved.outcome == "solved"
    assert wrong.outcome == "wrong_unflagged"
    assert wrong.reason.endswith("answer")


# --------------------------------------------------------------------------- record


def test_request_answer_carries_the_kind_and_tolerance() -> None:
    """The RequestAnswer handed to outcome.py describes the question asked."""
    request = rq.build_request(_congested_day(), seed=0, variant="unmet_question")
    answer = rq.request_answer(request, "Roughly 50 kWh go undelivered.")

    assert answer.kind == "unmet_kwh"
    assert answer.checkable is True
    assert answer.detail == request.question
    assert answer.truth == request.truth


def test_jsonl_round_trip(tmp_path) -> None:
    """A written request reads back identical, day and truth included."""
    original = [
        rq.build_request(_simple_day(), seed=0, variant="cost_question", day_date=date(2019, 5, 1)),
        rq.build_request(_congested_day(), seed=0, variant="feasible_yesno", day_date=date(2019, 5, 2)),
        rq.build_request(_simple_day(), seed=0, variant="schedule_only", day_date=date(2019, 5, 3)),
    ]
    path = rq.to_jsonl(original, tmp_path / "requests.jsonl")
    restored = rq.from_jsonl(path)

    assert [r.text for r in restored] == [r.text for r in original]
    assert [r.truth for r in restored] == [r.truth for r in original]
    assert [r.labels for r in restored] == [r.labels for r in original]
    assert restored[0].day.sessions == original[0].day.sessions


def test_variant_mix_is_mostly_questions(subset_requests) -> None:
    """Most requests ask something checkable; some only prescribe an operation."""
    summary = rq.summarise(subset_requests)

    assert summary["total"] == len(SUBSET_DATES)
    assert summary["checkable"] >= 1 and summary["state_only"] >= 0
    assert summary["checkable"] + summary["state_only"] == summary["total"]
    for request in subset_requests:
        assert request.checkable == (request.kind != "state")
        assert request.kind == rq.ANSWER_KIND_BY_VARIANT[request.variant]
        assert (request.question != "") == request.checkable


def test_all_variants_are_wired() -> None:
    """Every variant has a kind and a builder, and the state ones are marked."""
    assert set(rq.ANSWER_KIND_BY_VARIANT) == set(rq.VARIANTS)
    assert set(rq._QUESTION_BUILDERS) == set(rq.VARIANTS)
    assert set(rq.STATE_VARIANTS) <= set(rq.VARIANTS)
    assert set(rq.SHORTFALL_VARIANTS) <= set(rq.VARIANTS)
    for variant in rq.STATE_VARIANTS:
        assert rq.ANSWER_KIND_BY_VARIANT[variant] == "state"
    for variant in rq.SHORTFALL_VARIANTS:
        assert rq.ANSWER_KIND_BY_VARIANT[variant] != "state"


def test_unknown_variant_is_rejected() -> None:
    with pytest.raises(ValueError):
        rq.build_request(_simple_day(), seed=0, variant="peak_question")


def test_lowered_cap_variant_states_its_own_cap() -> None:
    """schedule_under_cap changes the problem, and says so in the text."""
    request = rq.build_request(_simple_day(), seed=0, variant="schedule_under_cap")

    assert request.site_cap_kw in rq.LOWER_CAPS_KW
    assert request.site_cap_kw < rq.SITE_CAP_KW
    assert rq.reference_parse(request.text).site_cap_kw == pytest.approx(request.site_cap_kw)
    site, _ = rq.build_site_tou(request)
    assert site.get_P_max_at_step(0) == pytest.approx(request.site_cap_kw)


def test_compute_ground_truth_agrees_with_the_stored_answer(subset_requests) -> None:
    """Re-deriving the truth from the request reproduces what it carries."""
    for request in subset_requests[:2]:
        recomputed = rq.compute_ground_truth(request)
        assert recomputed["answer"] == request.truth
        assert recomputed["kind"] == request.kind
        assert recomputed["synthetic"] is True
        assert "peak_kw" in recomputed["state"]

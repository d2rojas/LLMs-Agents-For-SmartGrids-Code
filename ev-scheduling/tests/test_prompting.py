"""Unit tests for methods.prompting.strategies: the two LLM-only prompting rows.

Offline: no API key, no LLM call, no network. Every "reply" here is written by
the test in the format the prompt asks for, which is the point of the round-trip
tests: a prompt is only useful if a reply that obeys it is readable by the three
readers, ``methods.prompting.parse.read_reply`` (the schedule and the declared
formulation), ``evaluation.formulation`` (the formulation term) and
``evaluation.requests.extract_answer`` (the answer to the question). An
unextractable answer on a checkable request is scored as wrong, so the format has
to survive extraction for every variant the benchmark can pose.
"""

from datetime import date

import numpy as np
import pytest

import json

from methods.prompting import strategies as st
from methods.prompting.parse import read_reply
from data.format.schema import DaySessions, Session
from evaluation import requests as rq
from evaluation.formulation import formulation_exact, problem_from_dict
from evaluation.outcome import PASS, check_answer
from evaluation.runner import llm_only_answer_text

DT = 0.25
N_STEPS = 96


# --------------------------------------------------------------------------- fixtures


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
        (32, 68, 15.0, 7.0),
        (40, 72, 20.0, 6.6),
        (36, 64, 9.25, 3.3),
    )


def _impossible_day() -> DaySessions:
    """Two cars that cannot be filled in their own window, whatever the schedule.

    EV 2 and EV 3 each ask for more than their own plug can deliver while they are
    there, so they are short in every feasible schedule, not only in the one the
    solver happens to return. That is the condition ``capacity_shortfall_cars``
    requires, and no committed fixture day meets it.
    """
    return _day(
        (32, 68, 15.0, 7.0),    # roomy: 9 h at 7 kW against 15 kWh asked
        (32, 40, 20.0, 3.3),    # 2 h at 3.3 kW delivers 6.6 kWh against 20 asked
        (44, 52, 18.0, 3.3),    # same shape, later in the day
    )


# Variants that cannot be posed on a day where every car can be served.
_DAY_FOR_VARIANT = {"capacity_shortfall_cars": _impossible_day}


def _request(variant: str = "cost_question", seed: int = 3) -> rq.EVRequest:
    day = _DAY_FOR_VARIANT.get(variant, _simple_day)()
    return rq.build_request(day, seed=seed, variant=variant, day_date=date(2019, 5, 15))


@pytest.fixture(scope="module")
def request_fixture() -> rq.EVRequest:
    return _request()


# --------------------------------------------------------------------------- registry


def test_registry_exposes_the_two_body_table_rows() -> None:
    """The paper's body table has exactly these two LLM-only rows."""
    assert "structured" in st.STRATEGIES
    assert "chain_of_thought" in st.STRATEGIES


def test_few_shot_and_rag_are_named_but_not_implemented() -> None:
    """The extension point is declared; the supplementary rows come later."""
    assert st.PLANNED_STRATEGIES == ("few_shot", "rag")
    for name in st.PLANNED_STRATEGIES:
        with pytest.raises(ValueError, match="planned but not implemented"):
            st.normalise_strategy(name)


def test_cot_alias_matches_the_power_flow_vocabulary() -> None:
    """power-flow-agent/llm/prompt_variants.py spells this row 'cot'."""
    assert st.normalise_strategy("cot") == "chain_of_thought"
    assert st.normalise_strategy("Chain-Of-Thought") == "chain_of_thought"
    assert st.normalise_strategy("STRUCTURED") == "structured"


def test_unknown_strategy_raises() -> None:
    with pytest.raises(ValueError, match="unknown strategy"):
        st.normalise_strategy("tree_of_thought")


def test_register_strategy_is_the_extension_point(request_fixture: rq.EVRequest) -> None:
    """A later few-shot builder plugs in without touching this module."""
    try:
        st.register_strategy(
            "few_shot_probe", lambda req: ("sys", f"{st.EXAMPLES_HEADING}\nx\n{req.text}")
        )
        assert "few_shot_probe" in st.STRATEGIES
        messages = st.build_messages("few_shot_probe", request_fixture)
        assert messages[1]["content"].startswith(st.EXAMPLES_HEADING)
    finally:
        st._BUILDERS.pop("few_shot_probe", None)
        st.STRATEGIES = tuple(s for s in st.STRATEGIES if s != "few_shot_probe")


def test_register_strategy_rejects_a_non_callable() -> None:
    with pytest.raises(ValueError, match="callable"):
        st.register_strategy("bad", "not a function")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- prompt shape


@pytest.mark.parametrize("strategy", ["structured", "chain_of_thought"])
def test_messages_are_system_plus_user_and_toolless(
    strategy: str, request_fixture: rq.EVRequest
) -> None:
    messages = st.build_messages(strategy, request_fixture)
    assert [m["role"] for m in messages] == ["system", "user"]
    assert all(m["content"].strip() for m in messages)
    # The LLM-only arm must not be told it has a solver.
    lowered = (messages[0]["content"] + messages[1]["content"]).lower()
    assert "no tools" in lowered
    for banned in ("solve_ev_schedule", "call the tool", "cvxpy"):
        assert banned not in lowered


@pytest.mark.parametrize("strategy", ["structured", "chain_of_thought"])
def test_structured_sections_are_present_and_ordered(
    strategy: str, request_fixture: rq.EVRequest
) -> None:
    """Structured prompting means role, context, task, output format, in order."""
    prompt = st.build_prompt_text(strategy, request_fixture)
    positions = [prompt.index(h) for h in st.prompt_sections(strategy)]
    assert positions == sorted(positions)
    for heading in (st.ROLE_HEADING, st.CONTEXT_HEADING, st.TASK_HEADING, st.OUTPUT_HEADING):
        assert prompt.count(heading) == 1


def test_only_chain_of_thought_carries_a_reasoning_section(
    request_fixture: rq.EVRequest,
) -> None:
    structured = st.build_prompt_text("structured", request_fixture)
    cot = st.build_prompt_text("chain_of_thought", request_fixture)
    assert st.REASONING_HEADING not in structured
    assert st.REASONING_HEADING in cot
    assert st.prompt_sections("structured") + (st.REASONING_HEADING,) != st.prompt_sections("cot")


def test_the_two_rows_differ_only_by_the_reasoning_section(
    request_fixture: rq.EVRequest,
) -> None:
    """Same request text, same output contract: one section is the only difference."""
    structured = st.build_prompt_text("structured", request_fixture)
    cot = st.build_prompt_text("chain_of_thought", request_fixture)
    reasoning = cot[cot.index(st.REASONING_HEADING) : cot.index(st.OUTPUT_HEADING)]
    assert cot.replace(reasoning, "") == structured
    # And the answer contract is byte-identical between the two.
    assert structured[structured.index(st.OUTPUT_HEADING) :] == cot[cot.index(st.OUTPUT_HEADING) :]


@pytest.mark.parametrize("strategy", ["structured", "chain_of_thought"])
def test_request_text_is_carried_verbatim(strategy: str, request_fixture: rq.EVRequest) -> None:
    """The text is the whole input; the prompt must not paraphrase it."""
    prompt = st.build_prompt_text(strategy, request_fixture)
    assert request_fixture.text.strip() in prompt


@pytest.mark.parametrize("strategy", ["structured", "chain_of_thought"])
def test_prompt_does_not_leak_the_structured_formulation(
    strategy: str, request_fixture: rq.EVRequest
) -> None:
    """No session table, no cap and no prices outside the request text itself.

    Restating them would remove the formulation step from the evaluated path and
    hand this arm data the solver-grounded arm has to read for itself.
    """
    prompt = st.build_prompt_text(strategy, request_fixture)
    head = prompt[: prompt.index(request_fixture.text.strip())]
    tail = prompt[prompt.index(request_fixture.text.strip()) + len(request_fixture.text.strip()) :]
    # The contract shows the schema with example values; the request's own
    # values must not be among them, or the example would be a crib.
    dt = request_fixture.day.dt_hours
    for outside in (head, tail):
        assert "arrival_idx" not in outside
        for session in request_fixture.day.sessions:
            assert f'"energy_kwh": {session.energy_kwh}' not in outside
            assert f'"arrival_hour": {session.arrival_idx * dt}' not in outside
            assert f'"departure_hour": {session.departure_idx * dt}' not in outside
        assert f'"site_cap_kw": {request_fixture.site_cap_kw:.1f}' not in outside
        assert f'"peak_price": {request_fixture.peak_price}' not in outside
        assert f'"off_peak_price": {request_fixture.off_peak_price}' not in outside


@pytest.mark.parametrize("strategy", ["structured", "chain_of_thought"])
def test_prompt_states_the_horizon_and_the_label_mapping(
    strategy: str, request_fixture: rq.EVRequest
) -> None:
    """The one thing the request text cannot say: the time grid and the names."""
    prompt = st.build_prompt_text(strategy, request_fixture)
    assert str(N_STEPS) in prompt
    assert f"{DT:.4f}" in prompt
    assert f"EV {len(request_fixture.day.sessions)}" in prompt
    assert st._N_SESSIONS_TOKEN not in prompt


def test_empty_request_text_is_rejected(request_fixture: rq.EVRequest) -> None:
    import dataclasses

    blank = dataclasses.replace(request_fixture, text="   ")
    with pytest.raises(ValueError, match="non-empty"):
        st.build_messages("structured", blank)


def test_shared_budget_is_one_number() -> None:
    """Both rows get the same completion budget; the harness reads it from here."""
    assert st.MAX_COMPLETION_TOKENS == 8192


def test_describe_covers_every_implemented_strategy() -> None:
    described = st.describe()
    assert set(described) == set(st.STRATEGIES)
    assert all(v for v in described.values())


# --------------------------------------------------------------------------- round trip


def _reference_schedule(request: rq.EVRequest) -> np.ndarray:
    """A feasible schedule for the day, used as the body of a simulated reply."""
    day = request.day
    schedule = np.zeros((len(day.sessions), day.n_steps), dtype=float)
    for i, session in enumerate(day.sessions):
        window = session.departure_idx - session.arrival_idx
        power = min(session.max_power_kw, session.energy_kwh / (window * day.dt_hours))
        schedule[i, session.arrival_idx : session.departure_idx] = power
    return schedule


def _contract_reply(request: rq.EVRequest, answer: object = "$4.20") -> str:
    """Render the reply the way the output contract asks the model to write it."""
    day = request.day
    sessions, schedule = [], {}
    for i, session in enumerate(day.sessions):
        label = f"EV {i + 1}"
        sessions.append(
            {
                "session_id": label,
                "arrival_hour": session.arrival_idx * day.dt_hours,
                "departure_hour": session.departure_idx * day.dt_hours,
                "energy_kwh": session.energy_kwh,
                "max_power_kw": session.max_power_kw,
            }
        )
        power = _reference_schedule(request)[i, session.arrival_idx]
        schedule[label] = [[session.arrival_idx * day.dt_hours, session.departure_idx * day.dt_hours, round(float(power), 4)]]
    return json.dumps(
        {
            "formulation": {
                "sessions": sessions,
                "site_cap_kw": request.site_cap_kw,
                "peak_price": request.peak_price,
                "off_peak_price": request.off_peak_price,
            },
            "schedule": schedule,
            "answer": answer,
            "cannot_answer": None,
        },
        indent=1,
    )


@pytest.mark.parametrize("strategy", ["structured", "chain_of_thought"])
def test_reply_in_the_prompted_format_parses_back(strategy: str) -> None:
    """A reply that obeys the output section round-trips with no repair at all."""
    request = _request()
    st.build_messages(strategy, request)  # the format under test
    read = read_reply(_contract_reply(request), request.day)
    assert read.format == "json"
    assert read.schedule.success is True
    assert read.schedule.repairs.changed is False
    # Four decimals in the reply: a round trip recovers the schedule to half of
    # the last digit and no better.
    assert read.schedule.schedule == pytest.approx(_reference_schedule(request), abs=5e-5)


def test_the_declared_formulation_is_scored_by_the_shared_function() -> None:
    """The formulation field goes through evaluation.formulation like every method's."""
    request = _request()
    read = read_reply(_contract_reply(request), request.day)
    problem = problem_from_dict(read.formulation)
    assert problem is not None
    verdict = formulation_exact(problem, request.day, dt_hours=request.day.dt_hours)
    assert verdict.formulation_exact is True
    assert verdict.n_sessions_exact == len(request.day.sessions)


def test_a_misread_clock_in_the_formulation_is_caught() -> None:
    """A quarter to eleven read as 11:15 is a wrong_field on that car, nothing else."""
    request = _request()
    reply = json.loads(_contract_reply(request))
    reply["formulation"]["sessions"][0]["departure_hour"] += 0.5
    read = read_reply(json.dumps(reply), request.day)
    verdict = formulation_exact(problem_from_dict(read.formulation), request.day, dt_hours=request.day.dt_hours)
    assert verdict.formulation_exact is False
    assert verdict.formulation_error_type == "wrong_field"
    assert verdict.n_sessions_exact == len(request.day.sessions) - 1


def test_chain_of_thought_reasoning_does_not_break_the_reply_read() -> None:
    """Plain-text reasoning before the object is allowed and must be ignored."""
    request = _request()
    reply = (
        "Step 1: EV 1 arrives at 8.0 and leaves at 17.0, and needs 15 kWh.\n"
        "Step 2: its window is 9 h long, so it needs about 1.67 kW on average {on average}.\n"
        "Step 5: the site limit is never binding here.\n\n"
        f"{_contract_reply(request)}\n"
    )
    read = read_reply(reply, request.day)
    assert read.format == "json"
    assert read.schedule.success is True
    assert read.schedule.repairs.changed is False
    assert read.schedule.schedule == pytest.approx(_reference_schedule(request), abs=5e-5)


def test_a_reply_that_ignores_the_contract_is_still_read_as_rows() -> None:
    """The matrix format of the runs before 2026-09-28 stays readable, for the rescore."""
    request = _request()
    schedule = _reference_schedule(request)
    rows = "\n".join(f"EV {i + 1}: " + " ".join(f"{v:.4f}" for v in row) for i, row in enumerate(schedule))
    read = read_reply(rows + "\nAnswer: $4.20\n", request.day)
    assert read.format == "matrix"
    assert read.formulation is None
    assert read.schedule.success is True
    assert read.schedule.schedule == pytest.approx(schedule, abs=5e-5)
    assert llm_only_answer_text(read, rows + "\nAnswer: $4.20\n").endswith("Answer: $4.20\n")


# One answer per checkable variant, phrased the way the output section asks.
_ANSWERS = {
    "cost_question": "$12.34",
    "unmet_question": "4.50 kWh undelivered",
    "served_share": "87.5 percent of the requested energy is delivered",
    "feasible_yesno": "yes",
    "total_energy_requested": "44.25 kWh in total",
    "cars_plugged_in_at": "3 cars are plugged in",
    "largest_request_car": "EV 2 needs the most energy",
    "capacity_shortfall_cars": "EV 2 and EV 3 cannot be fully served",
}


@pytest.mark.parametrize("variant,answer", sorted(_ANSWERS.items()))
def test_answer_field_survives_extraction_for_every_variant(variant: str, answer: str) -> None:
    """The prompted answer shape is readable by evaluation.requests.extract_answer.

    None from the extractor is scored as wrong, so a shape the extractor cannot
    read would fail this row for reasons that have nothing to do with the model.
    """
    request = _request(variant=variant)
    assert request.variant == variant
    assert request.checkable is True
    reply = _contract_reply(request, answer=answer)
    text = llm_only_answer_text(read_reply(reply, request.day), reply)
    assert text == f"{st.ANSWER_PREFIX} {answer}"
    assert rq.extract_answer(text, request) is not None, f"{variant}: {answer!r} did not extract"


def test_the_answer_is_not_confused_by_the_formulation_numbers() -> None:
    """Dozens of numbers precede the answer in the reply; only the answer field is read."""
    request = _request(variant="cost_question")
    reply = _contract_reply(request, answer="$12.34")
    text = llm_only_answer_text(read_reply(reply, request.day), reply)
    assert rq.extract_answer(text, request) == pytest.approx(12.34)


def test_a_correct_answer_scores_as_pass() -> None:
    """End to end: prompt, reply, extraction, outcome.check_answer."""
    request = _request(variant="cost_question")
    st.build_messages("structured", request)
    reply = _contract_reply(request, answer=f"${float(request.truth):.2f}")
    text = llm_only_answer_text(read_reply(reply, request.day), reply)
    assert check_answer(rq.request_answer(request, text)).status == PASS


def test_a_null_answer_on_a_question_is_a_failure_not_a_pass() -> None:
    """The trap the answer term exists to catch: a schedule with no answer."""
    request = _request(variant="cost_question")
    reply = _contract_reply(request, answer=None)
    text = llm_only_answer_text(read_reply(reply, request.day), reply)
    assert text == ""
    assert rq.extract_answer(text, request) is None
    assert check_answer(rq.request_answer(request, text)).status != PASS


def test_a_declared_inability_is_passed_on_as_such() -> None:
    request = _request(variant="cost_question")
    reply = json.dumps({"formulation": {"sessions": []}, "schedule": {}, "answer": None,
                        "cannot_answer": "the request names a car with no departure time"})
    read = read_reply(reply, request.day)
    assert read.schedule.success is False
    assert "cannot answer" in (read.schedule.error_message or "")
    assert llm_only_answer_text(read, reply).startswith("I cannot answer")


def test_state_variant_gets_the_same_contract() -> None:
    """A prescription-only request asks nothing; the contract says answer is null then."""
    request = _request(variant="schedule_only")
    assert request.checkable is False
    prompt = st.build_prompt_text("structured", request)
    assert "`answer` is null" in prompt
    reply = _contract_reply(request, answer=None)
    assert llm_only_answer_text(read_reply(reply, request.day), reply) == ""

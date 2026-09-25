"""Unit tests for baseline.strategies: the two LLM-only prompting rows.

Offline: no API key, no LLM call, no network. Every "reply" here is written by
the test in the format the prompt asks for, which is the point of the round-trip
tests: a prompt is only useful if a reply that obeys it is readable by both
``baseline.parse.parse_llm_schedule`` (the schedule) and
``evaluation.requests.extract_answer`` (the answer to the question). An
unextractable answer on a checkable request is scored as wrong, so the format has
to survive extraction for every variant the benchmark can pose.
"""

from datetime import date

import numpy as np
import pytest

from baseline import strategies as st
from baseline.parse import parse_llm_schedule
from data.format.schema import DaySessions, Session
from evaluation import requests as rq
from evaluation.outcome import PASS, check_answer

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
    for outside in (head, tail):
        assert "arrival_idx" not in outside
        assert "energy_kwh" not in outside
        assert f"{request_fixture.site_cap_kw:.2f}" not in outside
        assert str(request_fixture.peak_price) not in outside


@pytest.mark.parametrize("strategy", ["structured", "chain_of_thought"])
def test_prompt_states_the_horizon_and_the_label_mapping(
    strategy: str, request_fixture: rq.EVRequest
) -> None:
    """The one thing the request text cannot say: the time grid and the names."""
    prompt = st.build_prompt_text(strategy, request_fixture)
    assert str(N_STEPS) in prompt
    assert f"{DT:.4f}" in prompt
    assert f"EV {len(request_fixture.day.sessions)}" in prompt


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


def _schedule_rows(schedule: np.ndarray) -> str:
    """Render a schedule the way the prompt asks the model to write it."""
    return "\n".join(
        f"EV {i + 1}: " + " ".join(f"{v:.4f}" for v in row)
        for i, row in enumerate(schedule)
    )


def _reference_schedule(request: rq.EVRequest) -> np.ndarray:
    """A feasible schedule for the day, used as the body of a simulated reply."""
    day = request.day
    schedule = np.zeros((len(day.sessions), day.n_steps), dtype=float)
    for i, session in enumerate(day.sessions):
        window = session.departure_idx - session.arrival_idx
        power = min(session.max_power_kw, session.energy_kwh / (window * day.dt_hours))
        schedule[i, session.arrival_idx : session.departure_idx] = power
    return schedule


@pytest.mark.parametrize("strategy", ["structured", "chain_of_thought"])
def test_reply_in_the_prompted_format_parses_back(strategy: str) -> None:
    """A reply that obeys the output section round-trips with no repair at all."""
    request = _request()
    st.build_messages(strategy, request)  # the format under test
    schedule = _reference_schedule(request)
    reply = f"{_schedule_rows(schedule)}\n{st.ANSWER_PREFIX} $4.20\n"

    result = parse_llm_schedule(reply, request.day)
    assert result.success is True
    assert result.repairs.changed is False
    # The output section asks for four decimals, so a round trip can only recover
    # the schedule to half of the last digit. Tighter than this would test the
    # float printer, not the parser.
    assert result.schedule == pytest.approx(schedule, abs=5e-5)


def test_chain_of_thought_reasoning_does_not_break_the_schedule_parse() -> None:
    """Plain-text reasoning before the rows is allowed and must be ignored."""
    request = _request()
    schedule = _reference_schedule(request)
    reply = (
        "Step 1: EV 1 arrives at step 32 and leaves at step 68, and needs 15 kWh.\n"
        "Step 2: its window is 36 steps long, so it needs about 1.67 kW on average.\n"
        "Step 5: the site limit is never binding here.\n\n"
        f"{_schedule_rows(schedule)}\n{st.ANSWER_PREFIX} $4.20\n"
    )

    result = parse_llm_schedule(reply, request.day)
    assert result.success is True
    assert result.repairs.changed is False
    # The output section asks for four decimals, so a round trip can only recover
    # the schedule to half of the last digit. Tighter than this would test the
    # float printer, not the parser.
    assert result.schedule == pytest.approx(schedule, abs=5e-5)


# One reply shape per checkable variant, phrased the way the output section asks.
_ANSWER_REPLIES = {
    "cost_question": "{p} $12.34",
    "unmet_question": "{p} 4.50 kWh undelivered",
    "served_share": "{p} 87.5 percent of the cars are fully served",
    "feasible_yesno": "{p} yes",
    "total_energy_requested": "{p} 44.25 kWh in total",
    "cars_plugged_in_at": "{p} 3 cars are plugged in",
    "largest_request_car": "{p} EV 2 needs the most energy",
    "capacity_shortfall_cars": "{p} EV 2 and EV 3 cannot be fully served",
}


@pytest.mark.parametrize("variant,template", sorted(_ANSWER_REPLIES.items()))
def test_answer_line_survives_extraction_for_every_variant(
    variant: str, template: str
) -> None:
    """The prompted answer line is readable by evaluation.requests.extract_answer.

    None from the extractor is scored as wrong, so a shape the extractor cannot
    read would fail this row for reasons that have nothing to do with the model.
    """
    request = _request(variant=variant)
    assert request.variant == variant
    assert request.checkable is True

    schedule = _reference_schedule(request)
    answer_line = template.format(p=st.ANSWER_PREFIX)
    reply = f"{_schedule_rows(schedule)}\n{answer_line}\n"

    extracted = rq.extract_answer(reply, request)
    assert extracted is not None, f"{variant}: {answer_line!r} did not extract"


def test_answer_line_is_not_confused_by_the_schedule_numbers() -> None:
    """96 numbers per row precede the answer; the answer line still wins."""
    request = _request(variant="cost_question")
    schedule = _reference_schedule(request)
    reply = f"{_schedule_rows(schedule)}\n{st.ANSWER_PREFIX} $12.34\n"

    assert rq.extract_answer(reply, request) == pytest.approx(12.34)


def test_a_correct_answer_line_scores_as_pass() -> None:
    """End to end: prompt, reply, extraction, outcome.check_answer."""
    request = _request(variant="cost_question")
    st.build_messages("structured", request)
    schedule = _reference_schedule(request)
    reply = f"{_schedule_rows(schedule)}\n{st.ANSWER_PREFIX} ${float(request.truth):.2f}\n"

    verdict = check_answer(rq.request_answer(request, reply))
    assert verdict.status == PASS


def test_a_missing_answer_line_is_a_failure_not_a_pass() -> None:
    """The trap the answer term exists to catch: a schedule with no answer."""
    request = _request(variant="cost_question")
    reply = _schedule_rows(_reference_schedule(request))

    assert rq.extract_answer(reply, request) is None
    assert check_answer(rq.request_answer(request, reply)).status != PASS


def test_state_variant_needs_no_answer_line() -> None:
    """A prescription-only request asks nothing, and the prompt asks for nothing."""
    request = _request(variant="schedule_only")
    assert request.checkable is False
    prompt = st.build_prompt_text("structured", request)
    assert st.ANSWER_PREFIX not in prompt
    assert "schedule rows and nothing else" in prompt

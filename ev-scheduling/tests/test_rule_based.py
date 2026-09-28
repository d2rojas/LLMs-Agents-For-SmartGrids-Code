"""The rule-based row reads what it can and refuses the rest. It never guesses.

The refusals are the part worth pinning. A parser that fell back to a default
on an unreadable clock would produce a plausible schedule for the wrong day and
score it as wrong-unflagged, which is precisely the failure the conventional
row exists to be free of.
"""

from __future__ import annotations

import pytest

from methods.agent.parse.parse import parsed_problem_to_day_site_tou
from methods.deterministic.rule_based import CannotParse, answer_for, parse_request

CAP = "Total draw across all the chargers has to stay at or below 50 kilowatts."
TARIFF = "Energy costs $0.45 per kWh between 4 pm and 9 pm and $0.12 per kWh the rest of the day."
TASK = "Plan the charging to minimise what we pay for the energy."


def _request(*cars: str, question: str = "") -> str:
    head = f"{len(cars)} cars are charging at the lot today, and here is what each one needs."
    return " ".join([head, *cars, CAP, TARIFF, TASK, question]).strip()


def test_a_conventional_request_in_digits_is_read_exactly() -> None:
    text = _request(
        "EV 1: arrives 16:00, leaves 23:30, 33.58 kWh, 7000 watts maximum.",
        "EV 2 sits on a 7 kW station between 17:00 and 24:00 and asks for 6.47 kWh.",
        "The driver of EV 3 arrives at 3:30 pm, has to leave by 11:15 pm, and wants 13609 watt-hours at up to 7 kW.",
    )
    parsed = parse_request(text)
    day, site, tou = parsed_problem_to_day_site_tou(parsed.problem)
    assert [(s.arrival_idx, s.departure_idx) for s in day.sessions] == [(64, 94), (68, 96), (62, 93)]
    assert [round(s.energy_kwh, 3) for s in day.sessions] == [33.58, 6.47, 13.609]
    assert [s.max_power_kw for s in day.sessions] == [7.0, 7.0, 7.0]
    assert parsed.problem.site_cap_kw == 50.0
    assert (parsed.problem.peak_price, parsed.problem.off_peak_price) == (0.45, 0.12)
    assert parsed.question == ""  # the task sentence asks nothing


@pytest.mark.parametrize(
    "phrase, hour",
    [
        ("quarter past nine at night", 21.25),
        ("half past four in the afternoon", 16.5),
        ("half three in the afternoon", 15.5),
        ("a quarter to six in the morning", 5.75),
        ("ten o'clock at night", 22.0),
        ("midnight at the end of the day", 24.0),
        ("12:15 am", 0.25),
        ("a quarter to midnight", 23.75),
        ("half past midnight", 0.5),
        ("noon", 12.0),
    ],
)
def test_the_bounded_clock_grammar(phrase: str, hour: float) -> None:
    text = _request(f"EV 1 is there from 00:00 to {phrase}; give it 4 kWh, and its plug tops out at 7 kW.")
    parsed = parse_request(text)
    assert parsed.problem.sessions[0].departure_hour == pytest.approx(hour)


def test_a_word_clock_without_its_part_of_the_day_is_refused() -> None:
    text = _request("EV 1 is there from 01:00 to quarter past nine; give it 4 kWh, and its plug tops out at 7 kW.")
    with pytest.raises(CannotParse) as excinfo:
        parse_request(text)
    assert "morning, afternoon, evening or night" in excinfo.value.why


def test_an_unsupported_phrasing_is_refused_and_named() -> None:
    text = _request("EV 1 shows up sometime after lunch and stays until the evening; it wants 10 kWh at 7 kW.")
    with pytest.raises(CannotParse) as excinfo:
        parse_request(text)
    assert "EV 1" in excinfo.value.clause
    assert "clock" in excinfo.value.why


def test_the_task_sentence_is_not_read_as_a_cost_question() -> None:
    text = _request("EV 1: arrives 16:00, leaves 23:30, 3 kWh, 7 kW maximum.")
    assert parse_request(text).question == ""


@pytest.mark.parametrize(
    "question, kind",
    [
        ("How much do we pay for the energy in total? Answer in dollars, to two decimals.", "cost_question"),
        ("Tell me how many kWh are left undelivered at the end of the day, to two decimals.", "unmet_question"),
        ("Of all the energy requested, what percentage does the plan deliver? Answer as a percentage to two decimals.", "served_share"),
        ("Does anyone drive off short? Answer yes if every car gets its full request, no otherwise.", "feasible_yesno"),
        ("What do the requests add up to? Give the total in kWh, to two decimals.", "total_energy_requested"),
        ("Also, how many cars are plugged in at 11:15? Give a whole number.", "cars_plugged_in_at"),
        ("Which vehicle has the biggest energy request? Give its label.", "largest_request_car"),
        ("Name the cars that cannot be filled in the time they have, whatever the schedule.", "capacity_shortfall_cars"),
    ],
)
def test_every_question_kind_is_recognised_by_its_wording(question: str, kind: str) -> None:
    text = _request("EV 1: arrives 16:00, leaves 23:30, 3 kWh, 7 kW maximum.", question=question)
    parsed = parse_request(text)
    assert parsed.question == kind
    if kind == "cars_plugged_in_at":
        assert parsed.question_hour == pytest.approx(11.25)


def test_a_question_the_parser_does_not_know_is_refused() -> None:
    text = _request("EV 1: arrives 16:00, leaves 23:30, 3 kWh, 7 kW maximum.",
                    question="Which charger should we upgrade first?")
    with pytest.raises(CannotParse) as excinfo:
        parse_request(text)
    assert "question" in excinfo.value.why


def test_answers_come_from_the_tool_output_in_the_extractor_shape() -> None:
    text = _request(
        "EV 1: arrives 16:00, leaves 17:00, 30 kWh, 7 kW maximum.",   # 30 kWh in one hour at 7 kW: short
        "EV 2: arrives 16:00, leaves 23:30, 3 kWh, 7 kW maximum.",
        question="Which vehicle has the biggest energy request? Give its label.",
    )
    parsed = parse_request(text)
    day, _site, _tou = parsed_problem_to_day_site_tou(parsed.problem)
    out = {"total_cost_usd": 12.345, "total_unmet_kwh": 23.0, "peak_load_kw": 14.0, "pct_fully_served": 50.0}
    assert answer_for(parsed, day, out) == "Answer: EV 1 needs the most energy"
    parsed.question = "cost_question"
    assert answer_for(parsed, day, out) == "Answer: $12.35"
    parsed.question = "feasible_yesno"
    assert answer_for(parsed, day, out) == "Answer: no"
    parsed.question = "capacity_shortfall_cars"
    assert answer_for(parsed, day, out) == "Answer: EV 1 cannot be fully served"
    parsed.question = "cars_plugged_in_at"
    parsed.question_hour = 16.5
    assert answer_for(parsed, day, out) == "Answer: 2"

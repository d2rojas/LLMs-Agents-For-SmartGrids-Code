"""The conventional-automation row: a rule-based parser and the solver, no language model.

The EV counterpart of ``power-flow-agent/methods/deterministic/rule_based.py``.
Regular expressions read the request, the CVXPY tool computes the schedule, and
a template writes the answer. Same tool, same scorer as every other row, and
no model anywhere, so the row measures what conventional automation already
achieves on these requests and, just as important, what it refuses to handle.

What it reads (one example each):
  a car            "EV 4 sits on a 7 kW station between 17:00 and 24:00 and asks for 6.47 kWh"
  a clock, digits  "17:00", "5 pm", "11:15 pm", "24:00", "midnight at the end of the day", "noon"
  a clock, words   "quarter past nine at night", "half past four in the afternoon",
                   "a quarter to six in the morning", "ten o'clock at night", "half three in the afternoon"
  an energy        "6.47 kWh", "16.17 kilowatt-hours", "51850 Wh", "4804 watt-hours"
  a power          "7 kW", "7 kilowatts", "7000 W", "7000 watts"
  the site cap     "... has to stay at or below 50 kilowatts", "... is limited to 50 kW",
                   "... can never pull more than 50000 W in total"
  the tariff       "Energy costs $0.45 per kWh between 4 pm and 9 pm and $0.12 per kWh the rest of the day.",
                   "The tariff is $0.12/kWh off-peak and $0.45/kWh from 16:00 to 21:00.",
                   "... at 45 cents a kWh, and the rest of the day costs 12 cents a kWh."
  the question     the eight question kinds of the request set, by their wording

Every car sentence must yield exactly two clocks, one energy and one power, in
that order of arrival then departure; a word clock must carry its part of the
day ("in the morning", "at night"), because "quarter past nine" alone is
ambiguous and this parser does not guess. Anything that fails a rule raises
``CannotParse`` naming the sentence, and the runner turns that into a declared
inability: the day is escalated to a person, never answered from a partial
read. That refusal is the row's honest behavior and the reason it exists.

This is not ``evaluation.requests.reference_parse``. That function knows the
generator's own vocabulary and is a round-trip check on the generator; its
docstring forbids reporting it as a baseline. This module is written from the
phrasings a site operator would plausibly type, and its coverage of the
generated requests is a measurement, not a target.

Public API
  parse_request(text) -> ParsedRequest              (raises CannotParse)
  answer_for(parsed, day, solve_output) -> str       the "Answer: ..." line, or ""
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from data.format.schema import DaySessions
from methods.agent.parse.parse import ParsedProblem, ParsedSession

# --------------------------------------------------------------------------- vocabulary

_HOUR_WORDS: Dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
_HOUR_TOKEN = r"(?:1[0-2]|[1-9]|midnight|noon|" + "|".join(_HOUR_WORDS) + r")"
_PERIOD = r"(?:in the morning|in the afternoon|in the evening|at night|am|pm|a\.m\.|p\.m\.)"
_NUM = r"\d+(?:,\d{3})*(?:\.\d+)?"

# A clock, in one of the forms an operator writes. Each alternative captures
# what it needs; ``_clock_value`` turns a match into fractional hours.
_CLOCK = re.compile(
    r"(?P<endday>midnight at the end of the day)"
    r"|(?P<noon>\bnoon\b)"
    r"|(?P<digital>\b(?P<dh>[01]?\d|2[0-4]):(?P<dm>[0-5]\d)\b)\s*(?P<dp>am|pm|a\.m\.|p\.m\.)?"
    r"|\b(?P<hp>1[0-2]|[1-9])\s*(?P<hpp>am|pm|a\.m\.|p\.m\.)\b"
    r"|\b(?:a\s+)?(?P<rel>quarter past|quarter to|half past|half)\s+(?P<rh>" + _HOUR_TOKEN + r")\b(?:\s+(?P<rp>" + _PERIOD + r"))?"
    r"|\b(?P<oh>" + _HOUR_TOKEN + r")\s+o'clock\b(?:\s+(?P<op>" + _PERIOD + r"))?",
    re.IGNORECASE,
)
_ENERGY = re.compile(r"(?P<num>" + _NUM + r")\s*(?P<unit>kwh|kilowatt[- ]hours?|wh|watt[- ]hours?)\b", re.IGNORECASE)
_POWER = re.compile(r"(?P<num>" + _NUM + r")\s*(?P<unit>kw|kilowatts?|w|watts?)\b", re.IGNORECASE)
_LABEL = re.compile(r"\bEV\s?(?P<n>\d{1,3})\b", re.IGNORECASE)
# the site cap, in the ways an operator states a limit
_CAP = re.compile(
    r"(?:stay at or below|limited to|never pull more than|cannot draw more than|no more than|at most)\s+"
    r"(?P<num>" + _NUM + r")\s*(?P<unit>kw|kilowatts?|w|watts?)\b",
    re.IGNORECASE,
)
_TARIFF_DOLLARS = re.compile(
    r"\$\s*(?P<peak>" + _NUM + r")\s*per kwh between (?P<from>.+?) and (?P<to>.+?) and \$\s*(?P<off>" + _NUM + r")\s*per kwh the rest of the day",
    re.IGNORECASE,
)
_TARIFF_SLASH = re.compile(
    r"\$\s*(?P<off>" + _NUM + r")\s*/\s*kwh off-peak and \$\s*(?P<peak>" + _NUM + r")\s*/\s*kwh from (?P<from>.+?) to (?P<to>[^.,;]+)",
    re.IGNORECASE,
)
_TARIFF_CENTS = re.compile(
    r"(?P<peak>" + _NUM + r")\s*cents a kwh.*?rest of the day costs\s*(?P<off>" + _NUM + r")\s*cents",
    re.IGNORECASE | re.DOTALL,
)
_SENTENCE = re.compile(r"(?<=[.;])\s+(?=[A-Z(])|\n+|\s+-\s+(?=EV\s?\d)")


class CannotParse(ValueError):
    """Raised when a sentence matches no supported phrasing. The parser never guesses."""

    def __init__(self, clause: str, why: str = "") -> None:
        super().__init__(f"cannot parse: {clause!r}" + (f" ({why})" if why else ""))
        self.clause = clause
        self.why = why


@dataclass
class ParsedRequest:
    """Everything the rule-based row read from the request text.

    Attributes:
        problem: The sessions, cap, tariff and horizon, in the parser's own
            dataclass, for the solver and for the formulation score.
        question: One of the eight question kinds, or "" for a request that
            only asks for the schedule.
        question_hour: For ``cars_plugged_in_at``, the hour asked about.
    """

    problem: ParsedProblem
    question: str = ""
    question_hour: Optional[float] = None
    clauses: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------- clocks


def _f(raw: str) -> float:
    return float(raw.replace(",", ""))


def _hour_of(token: str) -> int:
    token = token.lower()
    if token in ("midnight", "noon"):
        return 12
    return int(token) if token.isdigit() else _HOUR_WORDS[token]


def _apply_period(hour: float, period: Optional[str], clause: str, text: str) -> float:
    """Turn a 12-hour reading and its part of the day into a 24-hour value."""
    if period is None:
        raise CannotParse(clause, f"the clock {text!r} does not say morning, afternoon, evening or night")
    p = period.lower().replace(".", "")
    h = hour % 12.0  # 12:15 am reads as 0.25, 12:15 pm as 12.25
    if p in ("am", "in the morning"):
        return h
    return h + 12.0  # pm, afternoon, evening, night


def _clock_value(m: "re.Match[str]", clause: str) -> float:
    if m.group("endday"):
        return 24.0
    if m.group("noon"):
        return 12.0
    if m.group("digital"):
        h, mi = int(m.group("dh")), int(m.group("dm"))
        if m.group("dp"):
            if h > 12:
                raise CannotParse(clause, f"{m.group('digital')} with am/pm is not a clock")
            return _apply_period(h + mi / 60.0, m.group("dp"), clause, m.group(0))
        if h == 24 and mi != 0:
            raise CannotParse(clause, f"{m.group('digital')} is not a clock")
        return h + mi / 60.0
    if m.group("hp"):
        return _apply_period(float(m.group("hp")), m.group("hpp"), clause, m.group(0))
    if m.group("rel"):
        rel, token = m.group("rel").lower(), m.group("rh").lower()
        if token in ("midnight", "noon"):
            # anchored to a fixed point: no part of the day needed
            anchor = 24.0 if token == "midnight" else 12.0
            if rel == "quarter past":
                return (anchor + 0.25) % 24.0
            if rel in ("half past", "half"):
                return (anchor + 0.5) % 24.0
            return anchor - 0.25  # quarter to
        h = _hour_of(token)
        if rel == "quarter past":
            base, minutes = h, 15
        elif rel in ("half past", "half"):
            base, minutes = h, 30
        else:  # quarter to
            base, minutes = h - 1, 45
        return _apply_period(base + minutes / 60.0, m.group("rp"), clause, m.group(0))
    if m.group("oh"):
        return _apply_period(float(_hour_of(m.group("oh"))), m.group("op"), clause, m.group(0))
    raise CannotParse(clause, f"unreadable clock {m.group(0)!r}")


def _clocks(clause: str) -> List[float]:
    return [_clock_value(m, clause) for m in _CLOCK.finditer(clause)]


# --------------------------------------------------------------------------- sentences


def _sentences(text: str) -> List[str]:
    """Sentences, list items and lines; a question and its instruction stay together."""
    return [s.strip(" -\t") for s in _SENTENCE.split(text) if s.strip(" -\t")]


def _parse_car(clause: str) -> Tuple[int, ParsedSession]:
    """One car sentence: its label, two clocks, one energy, one power."""
    labels = _LABEL.findall(clause)
    if len(labels) != 1:
        raise CannotParse(clause, "a car sentence names exactly one EV")
    n = int(labels[0])
    energies = [(_f(m.group("num")) / (1000.0 if m.group("unit").lower().startswith("w") else 1.0), m.span()) for m in _ENERGY.finditer(clause)]
    if len(energies) != 1:
        raise CannotParse(clause, f"{len(energies)} energy values, one expected")
    # the energy's "Wh" would otherwise read as a power's "W"
    body = clause[: energies[0][1][0]] + " " * (energies[0][1][1] - energies[0][1][0]) + clause[energies[0][1][1]:]
    powers = [_f(m.group("num")) / (1000.0 if m.group("unit").lower().startswith("w") else 1.0) for m in _POWER.finditer(body)]
    if len(powers) != 1:
        raise CannotParse(clause, f"{len(powers)} power values, one expected")
    clocks = _clocks(body)
    if len(clocks) != 2:
        raise CannotParse(clause, f"{len(clocks)} clock readings, two expected")
    arrival, departure = clocks
    if departure <= arrival:
        raise CannotParse(clause, "departure is not after arrival")
    return n, ParsedSession(
        arrival_hour=arrival, departure_hour=departure, energy_kwh=energies[0][0],
        max_power_kw=powers[0], session_id=f"EV-{n}", charger_id=f"charger-{n}",
    )


_QUESTIONS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("cost_question", ("cost for the day", "electricity bill", "pay for the energy")),
    ("unmet_question", ("cannot be delivered", "left undelivered", "goes undelivered")),
    ("served_share", ("share of the energy", "percentage of the requested energy", "what percentage does the plan deliver")),
    ("feasible_yesno", ("answer yes or no", "yes or no", "answer yes if")),
    ("total_energy_requested", ("add up", "total energy requested")),
    ("cars_plugged_in_at", ("plugged in at", "connected at", "parked on a charger at")),
    ("largest_request_car", ("most energy", "largest amount of energy", "biggest energy request")),
    ("capacity_shortfall_cars", ("more than their own charger", "cannot be filled", "more energy than their plug")),
)


def _classify_question(sentence: str) -> Optional[str]:
    """The question kind by its wording. Only called on a sentence that asks something,
    so the task sentence "minimise what we pay for the energy" is never read as a question."""
    low = sentence.lower()
    for kind, cues in _QUESTIONS:
        if any(cue in low for cue in cues):
            return kind
    return None


def parse_request(text: str) -> ParsedRequest:
    """Read a request with rules only. Raises ``CannotParse`` on the first sentence it cannot read."""
    sessions: Dict[int, ParsedSession] = {}
    clauses: List[str] = []
    cap: Optional[float] = None
    peak: Optional[float] = None
    off_peak: Optional[float] = None
    question = ""
    question_hour: Optional[float] = None

    for sentence in _sentences(text):
        low = sentence.lower()
        if _LABEL.search(sentence):
            n, session = _parse_car(sentence)
            if n in sessions:
                raise CannotParse(sentence, f"EV {n} is described twice")
            sessions[n] = session
            clauses.append(sentence)
            continue
        m = _CAP.search(sentence)
        if m:
            cap = _f(m.group("num")) / (1000.0 if m.group("unit").lower().startswith("w") else 1.0)
            continue
        m = _TARIFF_DOLLARS.search(sentence) or _TARIFF_SLASH.search(sentence) or _TARIFF_CENTS.search(sentence)
        if m:
            scale = 100.0 if m.re is _TARIFF_CENTS else 1.0
            peak, off_peak = _f(m.group("peak")) / scale, _f(m.group("off")) / scale
            continue
        if "?" in sentence or "tell me" in low or low.startswith("name the"):
            kind = _classify_question(sentence)
            if kind is None:
                raise CannotParse(sentence, "a question this parser does not know")
            if question:
                raise CannotParse(sentence, "a second question")
            question = kind
            if kind == "cars_plugged_in_at":
                hours = _clocks(sentence)
                if len(hours) != 1:
                    raise CannotParse(sentence, f"{len(hours)} clock readings in the question, one expected")
                question_hour = hours[0]
            continue
        # the opening line ("44 cars are charging ..."), the task sentence
        # ("Work out the charging plan ..."): read for nothing, never refused

    if not sessions:
        raise CannotParse(text[:120], "no car sentence found")
    if cap is None:
        raise CannotParse(text[:120], "no site cap sentence found")
    if peak is None or off_peak is None:
        raise CannotParse(text[:120], "no tariff sentence found")
    expected = list(range(1, len(sessions) + 1))
    if sorted(sessions) != expected:
        raise CannotParse(text[:120], f"cars are numbered {sorted(sessions)}, not 1..{len(sessions)}")

    problem = ParsedProblem(
        sessions=[sessions[n] for n in expected],
        n_steps=96, dt_hours=0.25, site_cap_kw=cap, peak_price=peak, off_peak_price=off_peak,
    )
    return ParsedRequest(problem=problem, question=question, question_hour=question_hour, clauses=clauses)


# --------------------------------------------------------------------------- the answer


def answer_for(parsed: ParsedRequest, day: DaySessions, solve_output: Dict[str, Any], *, served_tol_kwh: float = 0.01) -> str:
    """The one-line answer, in the shape the answer extractor reads, from the tool output alone."""
    q = parsed.question
    if not q:
        return ""
    if q == "cost_question":
        return f"Answer: ${float(solve_output['total_cost_usd']):.2f}"
    if q == "unmet_question":
        return f"Answer: {float(solve_output['total_unmet_kwh']):.2f} kWh"
    if q == "served_share":
        requested = sum(s.energy_kwh for s in day.sessions)
        delivered = requested - float(solve_output["total_unmet_kwh"])
        pct = 100.0 * delivered / requested if requested > 0 else 100.0
        return f"Answer: {pct:.2f} percent of the requested energy is delivered"
    if q == "feasible_yesno":
        return "Answer: yes" if float(solve_output["total_unmet_kwh"]) <= served_tol_kwh else "Answer: no"
    if q == "total_energy_requested":
        return f"Answer: {sum(s.energy_kwh for s in day.sessions):.2f} kWh"
    if q == "cars_plugged_in_at":
        step = int(round((parsed.question_hour or 0.0) / day.dt_hours))
        n = sum(1 for s in day.sessions if s.arrival_idx <= step < s.departure_idx)
        return f"Answer: {n}"
    if q == "largest_request_car":
        best = max(range(len(day.sessions)), key=lambda i: day.sessions[i].energy_kwh)
        return f"Answer: EV {best + 1} needs the most energy"
    if q == "capacity_shortfall_cars":
        short = [
            i + 1 for i, s in enumerate(day.sessions)
            if s.energy_kwh > s.max_power_kw * (s.departure_idx - s.arrival_idx) * day.dt_hours + 1e-9
        ]
        if not short:
            return "Answer: none, every car can be fully served"
        names = [f"EV {i}" for i in short]
        joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        return f"Answer: {joined} cannot be fully served"
    return ""

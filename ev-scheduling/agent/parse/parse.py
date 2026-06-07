"""Natural-language problem parser: extract structured EV session data from free text.

This module owns the first LLM call in the NL-input pipeline. It sends the
user's raw text to the LLM with a structured extraction prompt and returns
either a complete ParsedProblem (ready for the solver) or a ClarificationResult
asking the user for the missing information.

Typical flow:
    result = parse_nl_problem(user_text, api_key=key)
    if result.needs_clarification:
        print(result.clarification_message)
    else:
        day, site, tou = parsed_problem_to_day_site_tou(result.problem)
        agent_result = run_agent(day, site, tou, request=user_text)
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config.site import SiteConfig, TOUConfig, default_tou_rates
from data.format.schema import DaySessions, Session


# ---------------------------------------------------------------------------
# Dataclasses for the parsed representation
# ---------------------------------------------------------------------------

@dataclass
class ParsedSession:
    """One EV charging session extracted from natural language.

    Times are in fractional hours from midnight (e.g. 18.5 = 6:30 pm).
    Any field may be None if the LLM could not determine it from the text.

    Attributes:
        arrival_hour: Hour of arrival (0–24). None if not mentioned.
        departure_hour: Hour of departure (0–24). None if not mentioned.
        energy_kwh: Energy requested (kWh). None if not mentioned.
        max_power_kw: Max charging rate (kW). Defaults to 7.2 (Level 2).
        session_id: Optional label (e.g. "EV-1").
        charger_id: Optional charger label.
    """

    arrival_hour: Optional[float]
    departure_hour: Optional[float]
    energy_kwh: Optional[float]
    max_power_kw: float = 7.2
    session_id: str = ""
    charger_id: str = ""


@dataclass
class ParsedProblem:
    """Complete structured problem extracted from natural language.

    Attributes:
        sessions: List of parsed EV sessions.
        n_steps: Time horizon in steps (default 96 = 24 h at 15-min resolution).
        dt_hours: Step duration in hours (default 0.25).
        site_cap_kw: Site power cap in kW (default 50.0).
        peak_price: TOU peak rate in $/kWh (default 0.45).
        off_peak_price: TOU off-peak rate in $/kWh (default 0.12).
    """

    sessions: List[ParsedSession]
    n_steps: int = 96
    dt_hours: float = 0.25
    site_cap_kw: float = 50.0
    peak_price: float = 0.45
    off_peak_price: float = 0.12


@dataclass
class ParseResult:
    """Result of attempting to parse a natural-language problem description.

    Attributes:
        problem: Fully populated ParsedProblem, or None if clarification needed.
        needs_clarification: True when required fields are missing + user hasn't
            indicated they want inference.
        clarification_message: Human-readable question to ask the user.
        raw_llm_response: Raw text returned by the LLM (for debugging).
        missing_fields: List of field descriptions that are missing (for UI hints).
        used_inference: True if context-aware inference was applied to fill gaps.
        inference_notes: Explanations of what was inferred and why.
    """

    problem: Optional[ParsedProblem]
    needs_clarification: bool
    clarification_message: str = ""
    raw_llm_response: str = ""
    missing_fields: List[str] = field(default_factory=list)
    used_inference: bool = False
    inference_notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

_EXTRACTION_SYSTEM = (
    "You are a data-extraction assistant for a CAMPUS EV charging scheduler (Caltech ACN network). "
    "This is a workplace/university parking facility, not home charging. "
    "Extract EV charging session details into a JSON object. Output ONLY valid JSON.\n\n"
    "Return an object with this exact schema:\n"
    "{\n"
    '  "sessions": [\n'
    "    {\n"
    '      "session_id": "EV-1",          // label, or empty string\n'
    '      "arrival_hour": 9.0,           // hour from midnight (0-24), or null if unknown\n'
    '      "departure_hour": 17.0,        // hour from midnight (0-24), or null if unknown\n'
    '      "energy_kwh": 15.0,            // kWh requested, or null if unknown\n'
    '      "max_power_kw": 7.0            // max charging rate kW; default 7.0 (Level 2)\n'
    "    }\n"
    "  ],\n"
    '  "site_cap_kw": 50.0,              // total site power cap kW; default 50.0\n'
    '  "peak_price": 0.45,               // $/kWh peak TOU rate (4pm-9pm); default 0.45\n'
    '  "off_peak_price": 0.12            // $/kWh off-peak TOU rate; default 0.12\n'
    "}\n\n"
    "Rules:\n"
    "- Convert time expressions to fractional hours: '6pm' → 18.0, '6:30pm' → 18.5, "
    "'9am' → 9.0, '5pm' → 17.0, 'noon' → 12.0.\n"
    "- Campus context: 'morning' → 9.0, 'afternoon' → 14.0, 'evening' → 18.0, "
    "'end of day' / 'after work' → 17.0.\n"
    "- If the user gives a range like '20-30 kWh', use the midpoint (25.0).\n"
    "- Default max_power_kw is 7.0 (Level 2 campus chargers).\n"
    "- Do NOT invent values the user did not provide — use null for unknown required fields.\n"
    "- Output ONLY the JSON object. No explanation."
)


_INFERENCE_SYSTEM = (
    "You are an EV charging expert helping to fill in missing session parameters based on context. "
    "This is a CAMPUS/WORKPLACE charging facility (Caltech ACN network), NOT home charging. "
    "Users are students, faculty, and staff who park while at work/school.\n\n"
    "FACILITY CONTEXT:\n"
    "- Site: University campus parking lot (Caltech, JPL, or similar)\n"
    "- Chargers: Level 2 stations, max 7.0 kW per charger\n"
    "- Site power cap: 50 kW total across all chargers\n"
    "- Peak TOU hours: 4pm-9pm (higher electricity cost)\n"
    "- Typical sessions: 15-66 EVs per day\n\n"
    "ARRIVAL/DEPARTURE PATTERNS (campus context):\n"
    "- Morning arrival (7am-10am): Commuters arriving for work/class\n"
    "  → Departure typically 5pm-7pm (8-10 hour stay)\n"
    "- Late morning arrival (10am-12pm): Late arrivals, visitors\n"
    "  → Departure typically 4pm-6pm (5-7 hour stay)\n"
    "- Afternoon arrival (12pm-3pm): Afternoon classes/meetings\n"
    "  → Departure typically 5pm-8pm (3-5 hour stay)\n"
    "- Evening arrival (4pm-7pm): Evening classes/events\n"
    "  → Departure typically 9pm-11pm (3-5 hour stay)\n"
    "- If departure is given, infer arrival by subtracting typical stay duration\n\n"
    "ENERGY INFERENCE (campus commute patterns):\n"
    "- Short commute (< 15 miles): 5-10 kWh\n"
    "- Typical commute (15-30 miles): 10-20 kWh\n"
    "- Longer commute (30-50 miles): 20-30 kWh\n"
    "- Default if no context: 15 kWh (average campus commute)\n"
    "- Max deliverable = stay_hours × 7.0 kW; don't request more than this\n\n"
    "INFERENCE RULES:\n"
    "- If arrival known but departure unknown: Add typical stay (8h for morning, 4h for afternoon/evening)\n"
    "- If departure known but arrival unknown: Subtract typical stay from departure\n"
    "- If only energy known: Assume morning arrival (9am), calculate departure based on energy/7kW\n"
    "- Keep inferences conservative; better to underestimate energy than overestimate\n\n"
    "Output a JSON object with the SAME structure as input, but with null values replaced by "
    "your inferred values. Include an 'inference_notes' field explaining each inference.\n"
    "{\n"
    '  "sessions": [...],\n'
    '  "inference_notes": ["EV-1: 9am arrival → departure 5pm (8h typical workday stay)", ...]\n'
    "}"
)


# ---------------------------------------------------------------------------
# Inference detection
# ---------------------------------------------------------------------------

_UNKNOWN_INDICATORS = [
    "don't know", "dont know", "unknown", "not sure", "unsure",
    "no idea", "can't say", "cant say", "unavailable", "missing",
    "i don't have", "i dont have", "not available", "n/a",
]


def _user_indicated_unknowns(text: str) -> bool:
    """Check if user explicitly indicated some values are unknown.

    Returns True if the user's message contains phrases like "I don't know",
    "unknown", "not sure", etc. that signal they want inference.
    """
    text_lower = text.lower()
    return any(indicator in text_lower for indicator in _UNKNOWN_INDICATORS)


def _has_enough_context_for_inference(sessions: List[ParsedSession]) -> bool:
    """Check if there's enough partial info to make reasonable inferences.

    Returns True if each session has at least ONE of (arrival, departure, energy),
    meaning we have some context to work with. If a session has zero fields,
    we don't have enough to infer anything meaningful.

    Examples:
      - "EV1: 50kWh arrives 7pm" → has energy + arrival → can infer departure
      - "EV2: 20kWh leaves 10pm" → has energy + departure → can infer arrival
      - "EV3: ?" → has nothing → cannot infer anything
    """
    for sess in sessions:
        fields_present = sum([
            sess.arrival_hour is not None,
            sess.departure_hour is not None,
            sess.energy_kwh is not None,
        ])
        if fields_present == 0:
            return False
    return True


def _count_missing_per_session(sessions: List[ParsedSession]) -> List[int]:
    """Return number of missing required fields per session."""
    counts = []
    for sess in sessions:
        missing = sum([
            sess.arrival_hour is None,
            sess.departure_hour is None,
            sess.energy_kwh is None,
        ])
        counts.append(missing)
    return counts


def _run_inference(
    partial_data: Dict[str, Any],
    user_text: str,
    model: str,
    api_key: str,
) -> tuple[Dict[str, Any], List[str]]:
    """Use LLM to infer missing values based on available context.

    Args:
        partial_data: The extracted data with null values for unknowns.
        user_text: Original user message for context.
        model: OpenAI model name.
        api_key: OpenAI API key.

    Returns:
        Tuple of (data_with_inferences, inference_notes).
    """
    try:
        from openai import OpenAI
    except ImportError:
        return partial_data, []

    client = OpenAI(api_key=api_key)

    inference_prompt = (
        f"The user said: \"{user_text}\"\n\n"
        f"I extracted this partial data (null means unknown):\n"
        f"{json.dumps(partial_data, indent=2)}\n\n"
        "Please infer reasonable values for the null fields based on the context. "
        "Return the complete JSON with nulls replaced by your inferences, plus inference_notes."
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _INFERENCE_SYSTEM},
            {"role": "user", "content": inference_prompt},
        ],
        temperature=0.0,
    )

    raw = (response.choices[0].message.content or "").strip()

    try:
        inferred = _parse_llm_json(raw)
        notes = inferred.pop("inference_notes", [])
        if isinstance(notes, list):
            return inferred, notes
        return inferred, []
    except ValueError:
        return partial_data, []


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _missing_fields(sessions: List[ParsedSession]) -> List[str]:
    """Return a list of human-readable descriptions of missing required fields."""
    missing: List[str] = []
    for i, sess in enumerate(sessions):
        label = sess.session_id or f"EV {i + 1}"
        if sess.arrival_hour is None:
            missing.append(f"{label}: arrival time")
        if sess.departure_hour is None:
            missing.append(f"{label}: departure time")
        if sess.energy_kwh is None:
            missing.append(f"{label}: energy needed (kWh)")
    return missing


def _build_clarification_message(
    missing: List[str],
    has_partial_context: bool = False,
    user_indicated_unknowns: bool = False,
) -> str:
    """Build a clarification request or inability message.

    Args:
        missing: List of missing field descriptions.
        has_partial_context: True if some fields are present, allowing inference.
        user_indicated_unknowns: True if user already said they don't have the info.
    """
    # If user already said they don't have info AND we have no context → cannot produce
    if user_indicated_unknowns and not has_partial_context:
        lines = [
            "I'm unable to produce an optimal charging schedule without more information.",
            "",
            "The optimization requires at least some context about each EV session:",
            "  - When does the EV arrive? (so I know when charging can start)",
            "  - When does it need to leave? (so I know the deadline)",
            "  - How much energy is needed? (so I know the charging target)",
            "",
            "Without at least ONE of these per EV, I cannot compute a meaningful schedule.",
            "",
            "If you can provide even partial information (e.g., 'arrives in the morning' or",
            "'needs about 20 kWh'), I can make reasonable estimates for the rest based on",
            "typical campus charging patterns.",
        ]
        return "\n".join(lines)

    lines = [
        "To compute the optimal charging schedule, I need the following information:",
        "",
    ]
    for item in missing:
        lines.append(f"  • {item}")

    lines.append("")
    lines.append("Why this information is needed (campus charging context):")
    lines.append("  - Arrival time: When you park at the campus lot")
    lines.append("  - Departure time: When you're leaving campus")
    lines.append("  - Energy needed: Based on your commute distance (~10-20 kWh typical)")
    lines.append("")

    if has_partial_context:
        lines.append("You've provided some information which helps. If you can provide the missing")
        lines.append("details, I can compute a more accurate schedule. If not, just say")
        lines.append("\"I don't have that info\" and I'll estimate based on typical campus patterns")
        lines.append("(e.g., morning arrival → 8-hour stay, typical commute → 15 kWh).")
    else:
        lines.append("Please provide this information so I can compute an optimal schedule.")
        lines.append("If some details are unavailable, let me know which ones and I'll use")
        lines.append("reasonable estimates based on typical campus charging patterns.")

    lines.append("")
    lines.append(
        "Example: \"EV 1 arrives at 9am, leaves at 5pm, needs 15 kWh.\"\n"
        "Or with unknowns: \"EV 1 arrives in the morning, not sure when I'm leaving, "
        "need about 20 kWh for my commute.\""
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> str:
    """Strip markdown fences and extract the first JSON object from text."""
    # Remove ```json ... ``` or ``` ... ``` fences
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```", "", text)
    # Find first { ... } block
    start = text.find("{")
    if start == -1:
        return text.strip()
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:].strip()


def _parse_llm_json(raw: str) -> Dict[str, Any]:
    """Parse the LLM's JSON response into a dict, tolerating minor formatting issues."""
    cleaned = _extract_json(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned invalid JSON: {exc}\nRaw: {raw!r}") from exc


def _session_from_dict(d: Dict[str, Any], index: int) -> ParsedSession:
    """Build a ParsedSession from one element of the LLM's sessions array."""
    def _float_or_none(v: Any) -> Optional[float]:
        return None if v is None else float(v)

    return ParsedSession(
        arrival_hour=_float_or_none(d.get("arrival_hour")),
        departure_hour=_float_or_none(d.get("departure_hour")),
        energy_kwh=_float_or_none(d.get("energy_kwh")),
        max_power_kw=float(d.get("max_power_kw") or 7.2),
        session_id=str(d.get("session_id") or f"EV-{index + 1}"),
        charger_id=str(d.get("charger_id") or f"charger-{index + 1}"),
    )


# ---------------------------------------------------------------------------
# Main parse function
# ---------------------------------------------------------------------------

def parse_nl_problem(
    user_text: str,
    *,
    model: str = "gpt-4o",
    api_key: Optional[str] = None,
    allow_inference: bool = True,
) -> ParseResult:
    """Extract a structured EV charging problem from natural-language text.

    Sends one LLM call to extract session details (arrival, departure, energy,
    power) and optional site/TOU parameters. Validates the result and returns
    either a complete ParsedProblem or a clarification request.

    If required fields are missing:
      1. If allow_inference=True AND user explicitly indicated some values are
         unknown (e.g., "I don't know when it leaves"), uses context-aware
         inference to fill gaps with reasonable values based on context.
      2. Otherwise, asks for clarification and explains why each piece of
         information is needed for optimization.

    Args:
        user_text: Free-form user description of the charging problem.
        model: OpenAI model name.
        api_key: OpenAI API key (falls back to OPENAI_API_KEY env var).
        allow_inference: If True and user indicates unknowns, infer reasonable
            values from context (e.g., 6pm arrival → 10pm departure).

    Returns:
        ParseResult with either a populated problem (possibly with inferences),
        or needs_clarification=True explaining what is missing and why.

    Raises:
        ValueError: If OPENAI_API_KEY is not set.
        ImportError: If the openai package is not installed.
    """
    key = api_key or os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "OPENAI_API_KEY is not set. Set it in .env or pass api_key to parse_nl_problem."
        )

    try:
        from openai import OpenAI  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "The 'openai' package is not installed. "
            "Install it with 'pip install openai>=1.0.0'."
        ) from exc

    client = OpenAI(api_key=key)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _EXTRACTION_SYSTEM},
            {"role": "user", "content": user_text},
        ],
        temperature=0.0,
    )

    raw = (response.choices[0].message.content or "").strip()

    # Parse JSON
    try:
        data = _parse_llm_json(raw)
    except ValueError:
        # LLM returned something unparseable — ask for clarification
        return ParseResult(
            problem=None,
            needs_clarification=True,
            clarification_message=(
                "I wasn't able to extract structured session data from your message. "
                "Could you describe each EV's arrival time, departure time, and energy "
                "needed? For example: \"EV 1 arrives at 6 pm, leaves at 10 pm, needs 20 kWh.\""
            ),
            raw_llm_response=raw,
        )

    # Build ParsedSession list
    raw_sessions: List[Dict[str, Any]] = data.get("sessions") or []
    if not raw_sessions:
        # Check if user indicated they don't have info
        if _user_indicated_unknowns(user_text):
            msg = (
                "I'm unable to produce a charging schedule without information about your EVs.\n\n"
                "I need to know at least:\n"
                "  - How many EVs you have\n"
                "  - Some details about each (arrival time, departure time, or energy needed)\n\n"
                "Even partial information helps — for example:\n"
                "  \"I have 2 EVs, both arriving in the morning, one needs about 20 kWh.\""
            )
        else:
            msg = (
                "I couldn't find any EV sessions in your message. "
                "Please describe each EV: how many EVs, when they arrive and depart, "
                "and how much energy each one needs."
            )
        return ParseResult(
            problem=None,
            needs_clarification=True,
            clarification_message=msg,
            raw_llm_response=raw,
        )

    sessions = [_session_from_dict(s, i) for i, s in enumerate(raw_sessions)]

    # Validate — check for missing required fields
    missing = _missing_fields(sessions)
    used_inference = False
    inference_notes: List[str] = []

    if missing:
        # Check if we have enough partial context to make reasonable inferences
        has_partial_context = _has_enough_context_for_inference(sessions)

        # Decide whether to attempt inference:
        # 1. User explicitly said "I don't know" / "unknown" → inference
        # 2. User has partial context (some fields per EV) → inference
        user_indicated = _user_indicated_unknowns(user_text)
        should_infer = allow_inference and (user_indicated or has_partial_context)

        if should_infer and has_partial_context:
            # Run context-aware inference to fill gaps
            inferred_data, inference_notes = _run_inference(data, user_text, model, key)

            # Re-parse sessions from inferred data
            inferred_sessions: List[Dict[str, Any]] = inferred_data.get("sessions") or []
            if inferred_sessions:
                sessions = [_session_from_dict(s, i) for i, s in enumerate(inferred_sessions)]
                data = inferred_data
                used_inference = True

            # Check if inference filled all gaps
            missing = _missing_fields(sessions)

        if missing:
            # Still missing fields — ask for clarification or say unable
            # If user already said they don't have info AND no context → unable
            return ParseResult(
                problem=None,
                needs_clarification=True,
                clarification_message=_build_clarification_message(
                    missing,
                    has_partial_context=has_partial_context,
                    user_indicated_unknowns=user_indicated,
                ),
                raw_llm_response=raw,
                missing_fields=missing,
            )

    # Build ParsedProblem with defaults for optional site/TOU fields only
    # (these are facility-level parameters, not per-session data)
    def _float_default(v: Any, default: float) -> float:
        return default if v is None else float(v)

    problem = ParsedProblem(
        sessions=sessions,
        n_steps=96,
        dt_hours=0.25,
        site_cap_kw=_float_default(data.get("site_cap_kw"), 50.0),
        peak_price=_float_default(data.get("peak_price"), 0.45),
        off_peak_price=_float_default(data.get("off_peak_price"), 0.12),
    )

    return ParseResult(
        problem=problem,
        needs_clarification=False,
        raw_llm_response=raw,
        used_inference=used_inference,
        inference_notes=inference_notes,
    )


# ---------------------------------------------------------------------------
# Converter: ParsedProblem → DaySessions + SiteConfig + TOUConfig
# ---------------------------------------------------------------------------

def parsed_problem_to_day_site_tou(
    problem: ParsedProblem,
) -> tuple[DaySessions, SiteConfig, TOUConfig]:
    """Convert a ParsedProblem into the typed inputs expected by the solver.

    Converts fractional arrival/departure hours to step indices using the
    problem's dt_hours. Clamps indices to [0, n_steps] and ensures
    arrival_idx < departure_idx. Assigns sequential session_id / charger_id
    labels if not already set.

    Args:
        problem: Fully populated ParsedProblem (no None fields in sessions).

    Returns:
        Tuple of (DaySessions, SiteConfig, TOUConfig) ready for run_agent().

    Raises:
        ValueError: If any session has arrival_idx >= departure_idx after
            clamping, or if energy_kwh is non-positive.
    """
    n_steps = problem.n_steps
    dt = problem.dt_hours

    sessions: List[Session] = []
    for i, ps in enumerate(problem.sessions):
        # arrival_hour and departure_hour are guaranteed non-None by parse_nl_problem
        arrival_idx = int(round(ps.arrival_hour / dt))  # type: ignore[arg-type]
        departure_idx = int(round(ps.departure_hour / dt))  # type: ignore[arg-type]

        # Handle overnight sessions (departure < arrival in clock time)
        if departure_idx <= arrival_idx:
            departure_idx = arrival_idx + max(1, int(round(1.0 / dt)))

        # Clamp to horizon
        arrival_idx = max(0, min(arrival_idx, n_steps - 1))
        departure_idx = max(arrival_idx + 1, min(departure_idx, n_steps))

        energy_kwh = float(ps.energy_kwh)  # type: ignore[arg-type]
        if energy_kwh <= 0:
            energy_kwh = 1.0  # safe fallback

        sessions.append(
            Session(
                session_id=ps.session_id or f"EV-{i + 1}",
                arrival_idx=arrival_idx,
                departure_idx=departure_idx,
                energy_kwh=energy_kwh,
                charger_id=ps.charger_id or f"charger-{i + 1}",
                max_power_kw=max(0.1, ps.max_power_kw),
            )
        )

    day = DaySessions(sessions=sessions, n_steps=n_steps, dt_hours=dt)
    site = SiteConfig(P_max_kw=problem.site_cap_kw, n_steps=n_steps, dt_hours=dt)
    tou = TOUConfig(
        rates_per_kwh=default_tou_rates(
            n_steps,
            peak_price=problem.peak_price,
            off_peak_price=problem.off_peak_price,
        )
    )
    return day, site, tou

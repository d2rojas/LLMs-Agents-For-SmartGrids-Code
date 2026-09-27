"""Prompting strategies for the no-tools EV baseline (paper Section 3).

This is the EV counterpart of ``power-flow-agent/llm/prompt_variants.py``: the
same four strategies (structured / few-shot / chain-of-thought / RAG) built on
identical requests, so the two case studies report the same rows. Only the two
that are body-table rows are implemented here, ``structured`` and
``chain_of_thought``; ``few_shot`` and ``rag`` go to a supplementary table later
and are named in ``PLANNED_STRATEGIES`` with no builder registered.

The same section headings as the power-flow module are reused
(``## System Data``, ``## Task``, ``## Reasoning Instructions``,
``## Output Requirements``, ``## Worked Examples``) so a prompt from either case
study is read the same way. The one naming difference is deliberate: the
power-flow tuple abbreviates chain-of-thought to ``cot``, this registry spells it
``chain_of_thought`` because that is the row name, and ``cot`` is accepted as an
alias by ``normalise_strategy``.

What every strategy shares
--------------------------
Both strategies are given the *same* request text, the same completion budget
(``MAX_COMPLETION_TOKENS``), the same output format, and no tools. They differ in
one section only: chain-of-thought adds ``## Reasoning Instructions`` and allows
plain-text reasoning before the schedule. Anything else would confound the
comparison the row is supposed to make.

What the prompt does *not* say
------------------------------
The arrival and departure times, the energy each car asks for, the connector
limits, the site cap and the prices are stated in ``request.text`` and nowhere
else. This module never restates them in a table: the request text is the whole
input, for this arm exactly as for the solver-grounded arm, so the formulation
step is on the evaluated path (see ``evaluation/requests.py``). The context
section carries only what the request text cannot carry: the time grid, the unit
convention, and the mapping from the text's "EV n" to schedule row n-1.

The reply has to survive two readers
------------------------------------
``baseline/parse.py::parse_llm_schedule`` reads the schedule rows and
``evaluation/requests.py::extract_answer`` reads the answer to the question,
which ``evaluation/outcome.py`` scores as part of Solved. An unextractable answer
on a checkable request counts as wrong, not as skipped, so the output format
demands both: one ``EV n:`` row per car, then a final ``Answer:`` line phrased in
the question's own words. ``ANSWER_PREFIX`` is the literal the extractor's
highest-priority pattern anchors on.

Known limitation, inherited from the extractor: ``extract_answer`` takes the
first matching sentence, so a chain-of-thought reply that states a conclusion in
its reasoning is read as meaning that one, not the final ``Answer:`` line. The
reasoning instructions therefore tell the model to keep conclusions out of the
reasoning. This is a property of the scorer, not something this module can fix
from here.
"""

from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional, Tuple

import methods
from evaluation.requests import EVRequest

# Strategies with a builder registered here; the two body-table rows.
STRATEGIES: Tuple[str, ...] = ("structured", "chain_of_thought")

# Named, not implemented. They belong to the supplementary table and need a
# retrieval corpus and a worked-example set that do not exist yet. Registering a
# builder for one of these (see ``register_strategy``) is all that is required.
PLANNED_STRATEGIES: Tuple[str, ...] = ("few_shot", "rag")

# Spellings accepted by ``normalise_strategy``. ``cot`` is the power-flow module's
# name for the same row.
_ALIASES: Dict[str, str] = {
    "cot": "chain_of_thought",
    "chain-of-thought": "chain_of_thought",
    "chainofthought": "chain_of_thought",
    "structured_prompting": "structured",
}

# Section headings, shared with power-flow-agent/llm/prompt_variants.py.
ROLE_HEADING = "## Role"
CONTEXT_HEADING = "## System Data"
TASK_HEADING = "## Task"
EXAMPLES_HEADING = "## Worked Examples"
REASONING_HEADING = "## Reasoning Instructions"
OUTPUT_HEADING = "## Output Requirements"

# The literal the schedule rows start with and the literal the answer line starts
# with. ``baseline/parse.py`` accepts the first, ``evaluation/requests.py``
# anchors its highest-priority pattern on the second. Changing either string
# means changing that reader too.
SCHEDULE_LINE_PREFIX = "EV"
ANSWER_PREFIX = "Answer:"

# One completion budget for every strategy and for the solver-grounded arm, so a
# row never differs because it was allowed to write more. Matches the default of
# ``baseline/run.py::run_baseline``.
MAX_COMPLETION_TOKENS = 8192

# Decimal places asked for in the schedule rows.
_POWER_DECIMALS = 4


# --------------------------------------------------------------------------- shared text

_ROLE = methods.read_text("_shared/llm_only_role.txt")


def _context_section(request: EVRequest) -> str:
    """The conventions the request text does not state: grid, units, labels.

    Args:
        request: The request being rendered. Only its horizon is read.

    Returns:
        The ``## System Data`` section. It deliberately contains no session
        table, no site cap and no prices: those are in the request text.
    """
    day = request.day
    n_steps = day.n_steps
    dt_hours = day.dt_hours
    last = n_steps - 1
    return "\n".join(
        [
            CONTEXT_HEADING,
            f"- The day is divided into {n_steps} time steps of {dt_hours:.4f} h each. "
            f"Step 0 starts at midnight, so step k covers hour k x {dt_hours:.4f} to "
            f"(k+1) x {dt_hours:.4f}, and step {last} is the last one.",
            "- Power is in kW, energy in kWh, prices in dollars per kWh. Energy delivered to a "
            f"car over one step is its power at that step times {dt_hours:.4f} h.",
            f"- The cars are named EV 1 to EV {len(day.sessions)} in the request. Report them "
            "under those same names.",
            "- Every number you need about the cars, the site limit and the prices is in the "
            "request text below. There is no other data source.",
        ]
    )


def _task_section(request: EVRequest) -> str:
    """The request text verbatim under ``## Task``."""
    return f"{TASK_HEADING}\n{request.text.strip()}"


def _output_section(request: EVRequest) -> str:
    """The output contract both readers depend on.

    Args:
        request: The request being rendered; its horizon sets the row length and
            its ``checkable`` flag decides whether an answer line is demanded.

    Returns:
        The ``## Output Requirements`` section.
    """
    day = request.day
    n_sessions = len(day.sessions)
    n_steps = day.n_steps
    zeros = " ".join(f"{0.0:.{_POWER_DECIMALS}f}" for _ in range(3))
    lines = [
        OUTPUT_HEADING,
        f"Write exactly {n_sessions} schedule rows, EV 1 first and EV {n_sessions} last, one per "
        "line, in this form:",
        "",
        f"EV 1: v0 v1 v2 ... v{n_steps - 1}",
        "",
        f"Each row is the label, a colon, then exactly {n_steps} space-separated decimal numbers: "
        f"the charging power in kW of that car at step 0, step 1, ..., step {n_steps - 1}. Use "
        f"{_POWER_DECIMALS} decimal places (for example {zeros}). Do not write units, commas, "
        "brackets or any other text inside a row.",
        "",
        f"Check before you finish: {n_sessions} rows, each with exactly {n_steps} numbers. A row "
        "of the wrong length is counted as a formatting failure, so count them.",
    ]
    if request.checkable:
        lines += [
            "",
            f"After the last row, write one final line that starts with '{ANSWER_PREFIX}' and "
            "answers the question asked in the request. Phrase it in the words the question "
            "uses, and give the number with its unit, or the name of the car as 'EV 3', or "
            "'yes' or 'no', whichever the question asks for. Examples of the shape, not of the "
            f"values: '{ANSWER_PREFIX} $12.34', '{ANSWER_PREFIX} 4.50 kWh', "
            f"'{ANSWER_PREFIX} 87.5 percent of the cars are fully served', "
            f"'{ANSWER_PREFIX} yes', '{ANSWER_PREFIX} EV 3 needs the most energy', "
            f"'{ANSWER_PREFIX} EV 2 and EV 5 cannot be fully served'.",
            "",
            "Write the schedule rows first and the answer line last. Nothing after it.",
        ]
    else:
        lines += ["", "Write the schedule rows and nothing else."]
    return "\n".join(lines)


_SYSTEM_BASE = methods.read_text("_shared/llm_only_system_prompt.txt")

_SYSTEM_STRUCTURED_SUFFIX = methods.read_text("llm_only_structured/system_suffix.txt")

_SYSTEM_CHAIN_OF_THOUGHT_SUFFIX = methods.read_text("llm_only_cot/system_suffix.txt")

_REASONING_SECTION = methods.read_text("llm_only_cot/reasoning_section.txt")


# --------------------------------------------------------------------------- builders

# A builder takes the request and returns (system prompt, user prompt).
PromptBuilder = Callable[[EVRequest], Tuple[str, str]]


def _join(sections: Iterable[str]) -> str:
    """Join non-empty sections with a blank line between them."""
    return "\n\n".join(s.strip() for s in sections if s and s.strip())


def _build_structured(request: EVRequest) -> Tuple[str, str]:
    """Structured prompting: role, context, task, output format, in that order.

    No reasoning section and no worked examples. This is the plain sectioned
    prompt the other strategies are measured against.
    """
    user = _join(
        [
            f"{ROLE_HEADING}\n{_ROLE}",
            _context_section(request),
            _task_section(request),
            _output_section(request),
        ]
    )
    return _SYSTEM_BASE + _SYSTEM_STRUCTURED_SUFFIX, user


def _build_chain_of_thought(request: EVRequest) -> Tuple[str, str]:
    """Chain-of-thought: the structured prompt plus a reasoning section.

    Identical to ``_build_structured`` except for the ``## Reasoning
    Instructions`` section between the task and the output format, and the
    system prompt that permits reasoning text before the schedule.
    """
    user = _join(
        [
            f"{ROLE_HEADING}\n{_ROLE}",
            _context_section(request),
            _task_section(request),
            _REASONING_SECTION,
            _output_section(request),
        ]
    )
    return _SYSTEM_BASE + _SYSTEM_CHAIN_OF_THOUGHT_SUFFIX, user


_BUILDERS: Dict[str, PromptBuilder] = {
    "structured": _build_structured,
    "chain_of_thought": _build_chain_of_thought,
}


# --------------------------------------------------------------------------- registry API


def register_strategy(name: str, builder: PromptBuilder) -> None:
    """Register a prompting strategy, or replace one.

    The extension point for ``few_shot`` and ``rag``. A builder receives the
    ``EVRequest`` and returns ``(system_prompt, user_prompt)``; reuse
    ``_context_section``, ``_task_section`` and ``_output_section`` so the new
    strategy keeps the output contract the two readers depend on.

    Args:
        name: Strategy name. Added to ``STRATEGIES`` if new.
        builder: Callable returning ``(system_prompt, user_prompt)``.

    Raises:
        ValueError: If ``name`` is empty or ``builder`` is not callable.
    """
    global STRATEGIES
    key = str(name).strip().lower()
    if not key:
        raise ValueError("strategy name must be non-empty")
    if not callable(builder):
        raise ValueError(f"builder for {key!r} must be callable")
    _BUILDERS[key] = builder
    if key not in STRATEGIES:
        STRATEGIES = tuple(STRATEGIES) + (key,)


def normalise_strategy(name: str) -> str:
    """Canonical strategy name, resolving the accepted aliases.

    Args:
        name: Strategy name or alias, in any case.

    Returns:
        The canonical name, one of ``STRATEGIES``.

    Raises:
        ValueError: If the name is unknown, with a distinct message for a
            strategy that is planned but not implemented yet.
    """
    key = str(name).strip().lower().replace(" ", "_")
    key = _ALIASES.get(key, key)
    if key in _BUILDERS:
        return key
    if key in PLANNED_STRATEGIES:
        raise ValueError(
            f"strategy {key!r} is planned but not implemented; implemented: {STRATEGIES}"
        )
    raise ValueError(f"unknown strategy {name!r}; expected one of {STRATEGIES}")


def build_prompt_text(strategy: str, request: EVRequest) -> str:
    """The user message for one strategy on one request.

    Args:
        strategy: Strategy name or alias.
        request: The request to render.

    Returns:
        The full user prompt.

    Raises:
        ValueError: If the strategy is unknown or the request text is empty.
    """
    return build_messages(strategy, request)[1]["content"]


def system_prompt(strategy: str) -> str:
    """The system message for one strategy.

    Args:
        strategy: Strategy name or alias.

    Returns:
        The system prompt. Shared base, plus the one clause that differs.

    Raises:
        ValueError: If the strategy is unknown.
    """
    key = normalise_strategy(strategy)
    return _SYSTEM_BASE + (
        _SYSTEM_CHAIN_OF_THOUGHT_SUFFIX if key == "chain_of_thought" else _SYSTEM_STRUCTURED_SUFFIX
    )


def build_messages(strategy: str, request: EVRequest) -> List[Dict[str, str]]:
    """Build the chat messages for one strategy on one request.

    The single entry point a harness needs. No tools are ever attached: this is
    the LLM-only arm, and the caller must not pass a ``tools`` argument to the
    API alongside these messages.

    Args:
        strategy: Strategy name or alias; see ``STRATEGIES``.
        request: The request to render. Its ``text`` is the whole input and its
            ``day`` supplies only the horizon and the number of cars.

    Returns:
        ``[{"role": "system", ...}, {"role": "user", ...}]``.

    Raises:
        ValueError: If the strategy is unknown or the request text is empty.
    """
    key = normalise_strategy(strategy)
    if not request.text or not str(request.text).strip():
        raise ValueError("request.text must be non-empty")
    system, user = _BUILDERS[key](request)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def prompt_sections(strategy: str) -> Tuple[str, ...]:
    """The section headings a strategy emits, in order.

    Lets a harness record which sections a row was run with without diffing the
    prompt text.

    Args:
        strategy: Strategy name or alias.

    Returns:
        The headings, in the order they appear in the user prompt.

    Raises:
        ValueError: If the strategy is unknown.
    """
    key = normalise_strategy(strategy)
    if key == "chain_of_thought":
        return (ROLE_HEADING, CONTEXT_HEADING, TASK_HEADING, REASONING_HEADING, OUTPUT_HEADING)
    if key == "structured":
        return (ROLE_HEADING, CONTEXT_HEADING, TASK_HEADING, OUTPUT_HEADING)
    return ()


def describe(strategy: Optional[str] = None) -> Dict[str, str]:
    """One-line description of each strategy, for a report header or a table note.

    Args:
        strategy: A single strategy to describe, or None for all implemented ones.

    Returns:
        Mapping of strategy name to description.

    Raises:
        ValueError: If a named strategy is unknown.
    """
    known = {
        "structured": (
            "Sectioned prompt: role, system data, task, output format. No reasoning section, "
            "no examples, no retrieval, no tools."
        ),
        "chain_of_thought": (
            "The structured prompt plus a reasoning section that asks the model to work the "
            "allocation through step by step before committing to the schedule. No tools."
        ),
    }
    if strategy is None:
        return {k: known.get(k, "") for k in STRATEGIES}
    key = normalise_strategy(strategy)
    return {key: known.get(key, "")}

"""What every method receives and what every method returns.

``Context`` is the request as a method sees it: the text, the frozen window (the
tools read it; the no-tools methods receive its history as CSV), the budget and
the model. ``MethodRun`` is the one shape the scorer reads for every method: the
final answer text and its parsed form, the tool log, the model trace, and what
the harness itself had to do (a declared failure, a budget stop).

The prompt assembly for the model-backed methods also lives here so that the
system prompt of a method is one function, hashable and shown on the site.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import methods
from config import MAX_LLM_CALLS, MAX_TOOL_CALLS, REQUEST_TIMEOUT_S, ModelSpec
from methods.answer import Answer
from solver.data import Window, history_csv


@dataclass
class Context:
    request_id: str
    text: str
    window: Window
    horizon_hours: int
    spec: ModelSpec
    client: Any = None
    max_llm_calls: int = MAX_LLM_CALLS
    max_tool_calls: int = MAX_TOOL_CALLS
    temperature: float = 0.0
    request_timeout_s: float = REQUEST_TIMEOUT_S


@dataclass
class MethodRun:
    method: str
    answer_text: str
    answer: Answer
    tool_log: List[Dict[str, Any]] = field(default_factory=list)
    trace: Dict[str, Any] = field(default_factory=dict)
    gate: Optional[Dict[str, Any]] = None
    harness_declared: Optional[str] = None   # reason, when the harness wrote the answer
    budget_exhausted: bool = False
    error: Optional[str] = None
    n_llm_calls: int = 0
    n_tool_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    wall_time_s: float = 0.0
    system_prompt_hash: Optional[str] = None


# ------------------------------------------------------------- prompt assembly


def rules_and_contract() -> str:
    return methods.read_text("_shared/common_rules.txt") + "\n\n" + methods.read_text("_shared/output_contract.txt")


def agent_system_prompt() -> str:
    """System message of plan_act_nogate's answer call, react_nogate and windagent."""
    return methods.read_text("_shared/agent_system_prompt.txt") + "\n\n" + rules_and_contract()


def llm_only_system_prompt() -> str:
    return methods.read_text("_shared/llm_only_system_prompt.txt") + "\n\n" + rules_and_contract()


def planner_system_prompt() -> str:
    from solver.tools import catalogue_text

    return (methods.read_text("plan_act_nogate/plan_system_prompt.txt") + "\n\n"
            + methods.read_text("_shared/common_rules.txt") + "\n\n## Tools\n\n" + catalogue_text())


def history_block(ctx: Context) -> str:
    w = ctx.window
    per = w.history_valid_rows_per_day()
    last = per.get(w.history_end_day, 0)
    check = (f"Data check: {len(per)} days, each with 144 rows; rows with a wind speed and a power reading on the last day (day {w.history_end_day}): "
             f"{last} of 144. " + ("The history is complete." if last >= 72 else "The last day is missing: the feed stopped."))
    return (f"Turbine {w.turbine}, rated {w.rating_kw:.0f} kW, days {w.base_day} to {w.history_end_day}, 10-minute sampling, "
            f"{len(w.history())} rows. {check}\n" + history_csv(w))


def user_message(ctx: Context, *, history: bool = False, catalogue: bool = False, reasoning: bool = False) -> str:
    parts = ["## Request", ctx.text]
    if history:
        parts += ["", "## SCADA history", history_block(ctx)]
    if catalogue:
        from solver.tools import catalogue_text

        parts += ["", "## Tools the tool-using methods have (you do not; listed so that you know what they are)", catalogue_text()]
    if reasoning:
        parts += ["", methods.read_text("llm_only_cot/reasoning_section.txt")]
    return "\n".join(parts)


def system_prompt_for(method: str) -> Optional[str]:
    c = methods.card(method)
    if c["kind"] == "deterministic":
        return None
    if c["kind"] == "llm_only":
        return llm_only_system_prompt()
    return agent_system_prompt()

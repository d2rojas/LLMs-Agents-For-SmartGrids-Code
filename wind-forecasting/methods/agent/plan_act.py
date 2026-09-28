"""Plan-and-Act without a gate: plan every tool call at once, execute, then answer.

One planning call writes the whole sequence of tool calls as JSON, from the
request alone. The harness executes it in order without any feedback to the
model. One answer call then receives every result and writes the final answer
with the same contract as every other method. Two model calls per request; the
tool budget is the same as the loop's, so a plan longer than the budget is cut
at the budget.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional

import methods
from config import MAX_COMPLETION_TOKENS
from methods.agent.llm import Recorder, call_chat, message_of
from methods.answer import parse_answer
from methods.common import Context, MethodRun, agent_system_prompt, planner_system_prompt, user_message
from solver.tools import ToolDispatcher


def parse_plan(text: str) -> List[Dict[str, Any]]:
    """The ``plan`` list of the planner's JSON, or the last JSON list found; unknown shapes yield []."""
    obj = None
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        for m in re.finditer(r"\{.*\}", text or "", re.S):
            try:
                cand = json.loads(m.group())
                if isinstance(cand, dict) and "plan" in cand:
                    obj = cand
                    break
            except json.JSONDecodeError:
                continue
    plan = obj.get("plan") if isinstance(obj, dict) else (obj if isinstance(obj, list) else None)
    out: List[Dict[str, Any]] = []
    for step in plan or []:
        if isinstance(step, dict) and step.get("tool"):
            out.append({"tool": str(step["tool"]), "args": dict(step.get("args") or {})})
    return out


def run_plan_act(ctx: Context) -> MethodRun:
    rec = Recorder(spec=ctx.spec, method="plan_act_nogate", request_id=ctx.request_id)
    system = agent_system_prompt()
    planner = planner_system_prompt()
    dispatcher = ToolDispatcher(ctx.window, max_calls=ctx.max_tool_calls)
    t0 = time.time()
    error: Optional[str] = None
    answer_text = ""
    plan_text = ""
    plan: List[Dict[str, Any]] = []
    conversation: List[Dict[str, Any]] = []
    try:
        plan_messages = [{"role": "system", "content": planner}, {"role": "user", "content": user_message(ctx)}]
        resp = call_chat(ctx.client, rec, with_tools=False, model=ctx.spec.model, messages=plan_messages,
                         temperature=ctx.temperature, max_tokens=MAX_COMPLETION_TOKENS)
        plan_text = message_of(resp).content or ""
        plan = parse_plan(plan_text)
        results = []
        for step in plan:
            if dispatcher.exhausted:
                results.append({"tool": step["tool"], "args": step["args"], "output": {"error": "tool budget exhausted; not executed"}})
                continue
            out = dispatcher.call(step["tool"], step["args"])
            rec.record_tool(dispatcher.log[-1])
            results.append({"tool": step["tool"], "args": step["args"], "output": out})
        conversation = plan_messages + [
            {"role": "assistant", "content": plan_text},
            {"role": "user", "content": "## Executed plan and results\n\n" + json.dumps(results, default=str, indent=1)
                                        + "\n\nEvery step above has been executed in order. Write the final JSON answer now, from these results "
                                          "only: copy the forecast of the tool you choose value for value, or the element-wise mean of two, and "
                                          "name it in source. If no tool produced a forecast, set status to cannot_forecast."},
        ]
        answer_messages = [{"role": "system", "content": system}] + conversation[1:]
        resp = call_chat(ctx.client, rec, with_tools=False, model=ctx.spec.model, messages=answer_messages,
                         temperature=ctx.temperature, max_tokens=MAX_COMPLETION_TOKENS)
        answer_text = message_of(resp).content or ""
        conversation.append({"role": "assistant", "content": answer_text})
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
    answer = parse_answer(answer_text)
    harness_declared = None
    if not plan and error is None:
        harness_declared = "planner produced no executable plan"
    rec.finish(messages=conversation, answer_text=answer_text, status="ok" if error is None else "error", error=error)
    rec.extra = {"plan": plan, "plan_text": plan_text, "system_prompt_hash": methods.prompt_hash(system),
                 "planner_prompt_hash": methods.prompt_hash(planner), "harness_declared": harness_declared}
    return MethodRun(
        method="plan_act_nogate", answer_text=answer_text, answer=answer, tool_log=dispatcher.log,
        trace=rec.to_dict(), harness_declared=harness_declared, budget_exhausted=dispatcher.exhausted, error=error,
        n_llm_calls=rec.n_llm_calls, n_tool_calls=rec.n_tool_calls, prompt_tokens=rec.prompt_tokens,
        completion_tokens=rec.completion_tokens, wall_time_s=round(time.time() - t0, 3), system_prompt_hash=methods.prompt_hash(system),
    )

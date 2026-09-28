"""The two prompting methods: one call, no tools, the actions written as text.

``llm_only:structured`` receives the evidence block and the action catalogue
as text and writes the answer JSON: diagnosis, the list of actions, and the
final state it claims. ``llm_only:cot`` adds one reasoning section before the
answer. Neither runs the power flow. The harness applies the listed actions to
the network in order, once, and observes the result; that is what the row is
scored on, and the claim in ``final_state`` is checked against it exactly as
an agent's claim is. The offline execution is logged as tool calls flagged
``harness: true`` so the trace shows what was applied.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import methods
from config import MAX_COMPLETION_TOKENS
from methods.agent.llm import Recorder, call_chat, message_of
from methods.answer import parse_answer
from methods.common import Context, MethodRun, llm_only_system_prompt, user_message
from solver.tools import ACTION_TOOLS, ToolDispatcher


def apply_actions_offline(dispatcher: ToolDispatcher, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply the answer's actions in order (action tools only), then run the power flow once."""
    applied = []
    for a in actions:
        if a["tool"] not in ACTION_TOOLS:
            applied.append({"tool": a["tool"], "skipped": "not an action tool"})
            continue
        if dispatcher.exhausted:
            applied.append({"tool": a["tool"], "skipped": "budget"})
            continue
        out = dispatcher.call(a["tool"], a["args"])
        dispatcher.log[-1]["harness"] = True
        applied.append({"tool": a["tool"], "args": a["args"], "output": out})
    if not dispatcher.exhausted:
        dispatcher.call("run_power_flow", {})
        dispatcher.log[-1]["harness"] = True
    return applied


def run_llm_only(ctx: Context, *, strategy: str) -> MethodRun:
    name = "llm_only_structured" if strategy == "structured" else "llm_only_cot"
    rec = Recorder(spec=ctx.spec, method=name, request_id=ctx.request_id)
    system = llm_only_system_prompt()
    user = user_message(ctx, catalogue=True, reasoning=(strategy == "cot"))
    conversation = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    t0 = time.time()
    error: Optional[str] = None
    answer_text = ""
    try:
        resp = call_chat(ctx.client, rec, with_tools=False, model=ctx.spec.model, messages=conversation,
                         temperature=ctx.temperature, max_tokens=MAX_COMPLETION_TOKENS * (2 if strategy == "cot" else 1))
        answer_text = message_of(resp).content or ""
        conversation.append({"role": "assistant", "content": answer_text})
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
    answer = parse_answer(answer_text)
    dispatcher = ToolDispatcher(ctx.net, max_calls=ctx.max_tool_calls, base_keys=ctx.base_keys)
    applied = apply_actions_offline(dispatcher, answer.actions) if answer.json_ok else []
    for e in dispatcher.log:
        rec.record_tool(e)
    rec.finish(messages=conversation, answer_text=answer_text, status="ok" if error is None else "error", error=error)
    rec.extra = {"applied_offline": applied, "system_prompt_hash": methods.prompt_hash(system), "harness_declared": None}
    return MethodRun(
        method=name, answer_text=answer_text, answer=answer, final_net=dispatcher.net, tool_log=dispatcher.log,
        trace=rec.to_dict(), error=error, n_llm_calls=rec.n_llm_calls, n_tool_calls=0,
        prompt_tokens=rec.prompt_tokens, completion_tokens=rec.completion_tokens,
        wall_time_s=round(time.time() - t0, 3), system_prompt_hash=methods.prompt_hash(system),
    )

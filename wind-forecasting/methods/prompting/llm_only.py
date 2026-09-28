"""The two prompting methods: one call, no tools, the forecast written as text.

``llm_only:structured`` receives the request, the 14-day history as CSV, the
physical rules and the answer contract, and writes the series itself: the LLM
as the predictor, which is what the paper's Section 6.1 tested. ``llm_only:cot``
adds one reasoning section before the answer. Neither calls a forecaster. Their
numbers are, by construction, traceable to nothing, and their quality is judged
by the forecast error alone.
"""

from __future__ import annotations

import time
from typing import Optional

import methods
from config import MAX_COMPLETION_TOKENS
from methods.agent.llm import Recorder, call_chat, message_of
from methods.answer import parse_answer
from methods.common import Context, MethodRun, llm_only_system_prompt, user_message


def run_llm_only(ctx: Context, *, strategy: str) -> MethodRun:
    name = "llm_only_structured" if strategy == "structured" else "llm_only_cot"
    rec = Recorder(spec=ctx.spec, method=name, request_id=ctx.request_id)
    system = llm_only_system_prompt()
    user = user_message(ctx, history=True, catalogue=True, reasoning=(strategy == "cot"))
    conversation = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    t0 = time.time()
    error: Optional[str] = None
    answer_text = ""
    try:
        resp = call_chat(ctx.client, rec, with_tools=False, model=ctx.spec.model, messages=conversation,
                         temperature=ctx.temperature, max_tokens=MAX_COMPLETION_TOKENS + (2000 if strategy == "cot" else 0))
        answer_text = message_of(resp).content or ""
        conversation.append({"role": "assistant", "content": answer_text})
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
    answer = parse_answer(answer_text)
    rec.finish(messages=conversation, answer_text=answer_text, status="ok" if error is None else "error", error=error)
    rec.extra = {"system_prompt_hash": methods.prompt_hash(system), "harness_declared": None}
    return MethodRun(
        method=name, answer_text=answer_text, answer=answer, tool_log=[],
        trace=rec.to_dict(), error=error, n_llm_calls=rec.n_llm_calls, n_tool_calls=0,
        prompt_tokens=rec.prompt_tokens, completion_tokens=rec.completion_tokens,
        wall_time_s=round(time.time() - t0, 3), system_prompt_hash=methods.prompt_hash(system),
    )

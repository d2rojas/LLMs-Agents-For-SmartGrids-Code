"""The ReAct loop: ``react_nogate`` and, with ``gate=True``, ``windagent``.

Thought, tool call, observation, repeat, inside one budget of model calls
and tool calls. The model receives the tool schemas of ``solver/tools.py``
and the system prompt of ``methods/_shared/agent_system_prompt.txt``. The loop
ends when the model writes a message with no tool call (the final answer), or
when the budget runs out, in which case the model is asked once more, without
tools, to write the final answer from what it has.

With the gate, the final answer is checked by ``methods/agent/gate.py``. On a
failure the verdict is handed back to the model once, inside the same budget,
and the loop continues; a second failure ends in a declared failure written by
the harness, which carries no forecast and no number the tool log does not
support. The gated and ungated rows differ in nothing else.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import methods
from config import MAX_COMPLETION_TOKENS
from methods.agent import gate as G
from methods.agent.llm import Recorder, call_chat, message_of, to_jsonable, tool_calls_of
from methods.answer import Answer, declared_failure, parse_answer
from methods.common import Context, MethodRun, agent_system_prompt, user_message
from solver.tools import ToolDispatcher, openai_schemas

BUDGET_NOTE = "Tool budget exhausted. Write the final JSON answer now from what you have; do not call tools."


def _final_answer_call(client: Any, rec: Recorder, conversation: List[Dict[str, Any]], spec_model: str, temperature: float) -> str:
    conversation.append({"role": "user", "content": BUDGET_NOTE})
    resp = call_chat(client, rec, with_tools=False, model=spec_model, messages=conversation, temperature=temperature, max_tokens=MAX_COMPLETION_TOKENS)
    msg = message_of(resp)
    conversation.append({"role": "assistant", "content": msg.content or ""})
    return msg.content or ""


def run_react(ctx: Context, *, gate: bool, question_kind: Optional[str] = None) -> MethodRun:
    name = "windagent" if gate else "react_nogate"
    rec = Recorder(spec=ctx.spec, method=name, request_id=ctx.request_id)
    system = agent_system_prompt()
    conversation: List[Dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_message(ctx)},
    ]
    dispatcher = ToolDispatcher(ctx.window, max_calls=ctx.max_tool_calls)
    schemas = openai_schemas()
    answer_text = ""
    answer: Optional[Answer] = None
    gate_report: Optional[Dict[str, Any]] = None
    harness_declared: Optional[str] = None
    budget_exhausted = False
    error: Optional[str] = None
    attempts = 0
    gate_history: List[Dict[str, Any]] = []
    t_start = time.time()
    w = ctx.window

    try:
        while True:
            if rec.n_llm_calls >= ctx.max_llm_calls or (time.time() - t_start) > ctx.request_timeout_s:
                budget_exhausted = True
                break
            resp = call_chat(client=ctx.client, recorder=rec, with_tools=True, model=ctx.spec.model, messages=conversation,
                             tools=schemas, tool_choice="auto", temperature=ctx.temperature, max_tokens=MAX_COMPLETION_TOKENS)
            msg = message_of(resp)
            calls = tool_calls_of(msg)
            if calls:
                conversation.append(to_jsonable(msg.model_dump(exclude_none=True)))
                for tc in calls:
                    if dispatcher.exhausted:
                        out = {"error": BUDGET_NOTE}
                        entry = {"n": dispatcher.n_calls + 1, "name": tc["name"], "kind": "refused", "args": tc["args"], "output": out, "ok": False, "latency_s": 0.0}
                    else:
                        out = dispatcher.call(tc["name"], tc["args"])
                        entry = dispatcher.log[-1]
                    rec.record_tool(entry)
                    conversation.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(out, default=str)})
                if dispatcher.exhausted and rec.n_llm_calls < ctx.max_llm_calls:
                    answer_text = _final_answer_call(ctx.client, rec, conversation, ctx.spec.model, ctx.temperature)
                    budget_exhausted = True
                else:
                    continue
            else:
                answer_text = msg.content or ""
                conversation.append({"role": "assistant", "content": answer_text})

            answer = parse_answer(answer_text)
            if not gate:
                break
            attempts += 1
            gate_report = G.check(answer, dispatcher.log, horizon_hours=ctx.horizon_hours, question_kind=question_kind, power_max_kw=w.power_max_kw)
            rec.record_tool({"n": dispatcher.n_calls, "name": "harness_verify", "kind": "verify", "args": {"attempt": attempts},
                             "output": {"passed": gate_report["passed"], "failed": gate_report["failed"]}, "ok": gate_report["passed"], "latency_s": 0.0})
            gate_history.append({"attempt": attempts, "passed": gate_report["passed"], "failed": gate_report["failed"]})
            if gate_report["passed"] or (answer.declares_failure and "schema" in gate_report["failed"] and len(gate_report["failed"]) >= 4):
                # a declared failure is not a claim: it leaves as an escalation, not as a retry
                break
            if attempts >= G.MAX_VERIFICATION_ATTEMPTS or budget_exhausted or rec.n_llm_calls >= ctx.max_llm_calls:
                obj = declared_failure("verification failed after the retry: " + ", ".join(gate_report["failed"]),
                                       turbine=w.turbine, history_days=[w.base_day, w.history_end_day], horizon_hours=ctx.horizon_hours)
                answer_text = json.dumps(obj, indent=2)
                answer = parse_answer(answer_text)
                harness_declared = "gate rejected " + ", ".join(gate_report["failed"])
                break
            conversation.append({"role": "user", "content": methods.read_text("_shared/gate_retry_instruction.txt") + "\n\n" + G.verdict_text(gate_report)})
        if answer is None:
            if rec.n_llm_calls < ctx.max_llm_calls:
                answer_text = _final_answer_call(ctx.client, rec, conversation, ctx.spec.model, ctx.temperature)
                answer = parse_answer(answer_text)
            if answer is None or not answer.json_ok:
                obj = declared_failure("budget exhausted before a final answer", turbine=w.turbine,
                                       history_days=[w.base_day, w.history_end_day], horizon_hours=ctx.horizon_hours)
                answer_text = json.dumps(obj, indent=2)
                answer = parse_answer(answer_text)
                harness_declared = "budget exhausted"
            budget_exhausted = True
            if gate and answer is not None:
                gate_report = G.check(answer, dispatcher.log, horizon_hours=ctx.horizon_hours, question_kind=question_kind, power_max_kw=w.power_max_kw)
        if gate and gate_report is not None and not gate_report["passed"] and harness_declared is None and not answer.declares_failure:
            # the budget ran out after a rejected answer: the rejected answer never leaves as a forecast
            obj = declared_failure("verification failed and the budget ran out before a retry could pass: " + ", ".join(gate_report["failed"]),
                                   turbine=w.turbine, history_days=[w.base_day, w.history_end_day], horizon_hours=ctx.horizon_hours)
            answer_text = json.dumps(obj, indent=2)
            answer = parse_answer(answer_text)
            harness_declared = "gate rejected " + ", ".join(gate_report["failed"]) + " (budget exhausted)"
            budget_exhausted = True
    except Exception as e:  # the run is recorded with its error, never lost
        error = f"{type(e).__name__}: {e}"
        if answer is None:
            answer_text = ""
            answer = parse_answer("")

    rec.finish(messages=conversation, answer_text=answer_text, status="ok" if error is None else "error", error=error)
    rec.extra = {"gate": gate_report, "gate_history": gate_history, "harness_declared": harness_declared,
                 "budget_exhausted": budget_exhausted, "system_prompt_hash": methods.prompt_hash(system)}
    return MethodRun(
        method=name, answer_text=answer_text, answer=answer, tool_log=dispatcher.log,
        trace=rec.to_dict(), gate=gate_report, harness_declared=harness_declared, budget_exhausted=budget_exhausted,
        error=error, n_llm_calls=rec.n_llm_calls, n_tool_calls=rec.n_tool_calls, prompt_tokens=rec.prompt_tokens,
        completion_tokens=rec.completion_tokens, wall_time_s=round(time.time() - t_start, 3),
        system_prompt_hash=methods.prompt_hash(system),
    )

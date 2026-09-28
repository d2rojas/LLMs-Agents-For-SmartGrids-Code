"""The conventional-automation row: a regular-expression parser and the conventional forecaster, no language model.

The parser reads the turbine, the history window and the horizon from the request
text with patterns written for the way an operator phrases such a request, not
for the generator's vocabulary; a request it cannot read is escalated, which is
the honest cost of having no language model. What it reads goes, unchanged, into
the GRU tool; the answer to the question is computed from the tool's series.
Everything it reports comes from a tool output, so it is traceable by
construction.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional

from config import HISTORY_DAYS
from methods.agent.gate import derive_answer
from methods.answer import declared_failure, parse_answer
from methods.common import Context, MethodRun
from solver.tools import ToolDispatcher

_TURBINE = re.compile(r"\bturbine\s*(?:no\.?|number|#|id)?\s*(\d{1,3})\b", re.I)
_DAYS = re.compile(r"\bdays?\s*(\d{1,3})\s*(?:to|through|until|-|–)\s*(?:day\s*)?(\d{1,3})\b", re.I)
_HOURS = re.compile(r"\b(\d{1,3})\s*(?:h\b|hours?\b|-hour)", re.I)
_LAST_DAY = re.compile(r"\b(?:up to|until|through|ending(?: on)?)\s+day\s*(\d{1,3})\b", re.I)
_QUESTION = (
    (re.compile(r"\b(hour|hours)\b.*\b(highest|peak|maximum|largest)\b|\b(highest|peak|maximum|largest)\b.*\bhour\b", re.I), "peak_hour"),
    (re.compile(r"\b(energy|kwh|kilowatt[- ]hours?)\b", re.I), "energy_kwh"),
)


def parse_request(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"turbine": None, "history_days": None, "horizon_hours": None, "question": "none", "unparsed": []}
    m = _TURBINE.search(text)
    if m:
        out["turbine"] = int(m.group(1))
    else:
        out["unparsed"].append("turbine")
    m = _DAYS.search(text)
    if m:
        out["history_days"] = [int(m.group(1)), int(m.group(2))]
    else:
        m2 = _LAST_DAY.search(text)
        if m2:
            out["history_days"] = [int(m2.group(1)) - HISTORY_DAYS + 1, int(m2.group(1))]
        else:
            out["unparsed"].append("history window")
    hs = [int(x) for x in _HOURS.findall(text)]
    if hs:
        out["horizon_hours"] = hs[0]
    else:
        out["unparsed"].append("horizon")
    for rx, kind in _QUESTION:
        if rx.search(text):
            out["question"] = kind
            break
    return out


def run_rule_based(ctx: Context) -> MethodRun:
    t0 = time.time()
    d = ToolDispatcher(ctx.window, max_calls=ctx.max_tool_calls)
    parsed = parse_request(ctx.text)
    harness_declared: Optional[str] = None
    if parsed["unparsed"]:
        obj = declared_failure("cannot parse the request: " + ", ".join(parsed["unparsed"]) + " not found",
                               turbine=parsed["turbine"], history_days=parsed["history_days"], horizon_hours=parsed["horizon_hours"])
        harness_declared = "cannot parse"
    else:
        args = {"turbine": parsed["turbine"], "history_end_day": parsed["history_days"][1], "horizon_hours": parsed["horizon_hours"]}
        d.call("get_history_summary", {"turbine": args["turbine"], "history_end_day": args["history_end_day"]})
        out = d.call("gru_forecast", args)
        if isinstance(out, dict) and out.get("forecast"):
            series = [float(v) for v in out["forecast"]]
            obj = {
                "formulation": {"turbine": parsed["turbine"], "history_days": parsed["history_days"], "horizon_hours": parsed["horizon_hours"]},
                "forecast": series, "source": "gru_forecast", "answer": derive_answer(parsed["question"], series),
                "status": "forecast", "cannot_forecast": None,
                "summary": f"Parsed turbine {parsed['turbine']}, days {parsed['history_days'][0]} to {parsed['history_days'][1]}, "
                           f"{parsed['horizon_hours']} h; forecast copied from gru_forecast ({len(series)} values).",
            }
        else:
            err = out.get("error") if isinstance(out, dict) else "no forecast"
            obj = declared_failure(f"the forecaster refused: {err}", turbine=parsed["turbine"], history_days=parsed["history_days"], horizon_hours=parsed["horizon_hours"])
    answer_text = json.dumps(obj, indent=2)
    trace = {"case_study": "wind", "method": "rule_based", "model": ctx.spec.key, "request_id": ctx.request_id, "status": "ok",
             "error": None, "answer": answer_text, "messages": [], "rounds": [{"round": 1, "role": "harness", "llm": None, "tools": list(d.log)}],
             "n_llm_calls": 0, "n_tool_calls": d.n_calls, "prompt_tokens": 0, "completion_tokens": 0, "wall_time_s": round(time.time() - t0, 3),
             "parsed": parsed, "harness_declared": harness_declared, "system_prompt_hash": None}
    return MethodRun(method="rule_based", answer_text=answer_text, answer=parse_answer(answer_text), tool_log=d.log, trace=trace,
                     harness_declared=harness_declared, n_tool_calls=d.n_calls, wall_time_s=round(time.time() - t0, 3))

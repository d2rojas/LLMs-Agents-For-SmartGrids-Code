"""The verification gate: five conditions on the final answer, from the agent's own evidence.

The gate sees the tool log and the text the agent wrote. It never sees the
target days or a reference forecast; that is what makes it a deployable
component rather than an evaluation artifact, and it fixes what it can and
cannot catch. It cannot tell a good forecast from a bad one; it can tell a
series no tool produced, a value outside the physical range, a wrong number of
values, an answer that contradicts its own series, and a formulation that
misdescribes the call the series came from.

    W1  schema        exactly horizon*6 finite values, and status forecast
    W2  range         every value within [0, POWER_MAX_KW]
    W3  traceable     the series equals, value for value, one forecast-tool output or the
                      element-wise mean of two, and the named source agrees
    W4  consistent    the formulation in the answer matches the arguments of the tool call
                      the series came from (turbine, history window, horizon)
    W5  coherent      the answer to the question follows from the reported series

``check`` returns one record per condition plus ``passed``.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

from config import ANSWER_REL_TOL, HISTORY_DAYS, POWER_MAX_KW, STEPS_PER_HOUR, TRACE_TOL_KW
from methods.answer import Answer

CONDITION_ORDER = ("schema", "range", "traceable", "consistent", "coherent")
CONDITION_LABELS = {"schema": "W1", "range": "W2", "traceable": "W3", "consistent": "W4", "coherent": "W5"}
CONDITION_DESCRIPTIONS = {
    "schema": "status is forecast and the series has exactly horizon_hours*6 finite values",
    "range": f"every value lies in [0, {POWER_MAX_KW:.0f}] kW, the physical range of the turbine",
    "traceable": f"the series equals, within {TRACE_TOL_KW} kW per value, one forecast-tool output or the element-wise mean of two, and the answer names that source",
    "consistent": "the formulation declared in the answer (turbine, history days, horizon) matches the arguments of the tool call the series came from",
    "coherent": f"the answer to the request's question follows from the reported series (the named hour within {ANSWER_REL_TOL:.0%} of the highest hourly mean; the energy within {ANSWER_REL_TOL:.0%})",
}
MAX_VERIFICATION_ATTEMPTS = 2


# ---------------------------------------------------------------- the question


def derive_answer(kind: Optional[str], series: List[float]) -> Optional[float]:
    """What the series implies for the question: the 1-based hour of highest mean power, or the energy in kWh."""
    if not kind or kind == "none" or not series:
        return None
    s = np.asarray(series, dtype=float)
    if kind == "peak_hour":
        n = len(s) // STEPS_PER_HOUR
        if n == 0:
            return None
        hourly = s[: n * STEPS_PER_HOUR].reshape(n, STEPS_PER_HOUR).mean(axis=1)
        return float(int(np.argmax(hourly)) + 1)
    if kind == "energy_kwh":
        return float(round(s.sum() / STEPS_PER_HOUR, 1))
    return None


def answer_matches(kind: Optional[str], given: Optional[float], series: List[float]) -> Optional[bool]:
    """None when the request asks nothing; otherwise whether ``given`` follows from ``series``.

    Peak hour: the named hour's mean power is within ANSWER_REL_TOL of the highest hourly
    mean (near-ties are accepted; a flat forecaster produces many). Energy: within
    ANSWER_REL_TOL of the sum of the values divided by 6, or within 1 kWh."""
    if not kind or kind == "none":
        return None
    if given is None or not series:
        return False
    s = np.asarray(series, dtype=float)
    if kind == "peak_hour":
        n = len(s) // STEPS_PER_HOUR
        if n == 0:
            return False
        hourly = s[: n * STEPS_PER_HOUR].reshape(n, STEPS_PER_HOUR).mean(axis=1)
        h = int(round(given))
        if h < 1 or h > n:
            return False
        return bool(hourly[h - 1] >= (1.0 - ANSWER_REL_TOL) * float(hourly.max()) - 1e-9)
    implied = float(round(s.sum() / STEPS_PER_HOUR, 1))
    return abs(given - implied) <= max(ANSWER_REL_TOL * abs(implied), 1.0)


# ---------------------------------------------------------------- traceability


def _close(a: List[float], b: List[float]) -> bool:
    if len(a) != len(b) or not a:
        return False
    return bool(np.max(np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float))) <= TRACE_TOL_KW)


def trace_forecast(series: List[float], tool_log: Iterable[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], str]:
    """The tool-log entry (or the pair) the series copies, and how: 'copy', 'mean', or '' when none."""
    outs = [e for e in tool_log if e.get("kind") == "forecast" and e.get("ok") and isinstance(e.get("output"), dict) and e["output"].get("forecast")]
    for e in reversed(outs):
        if _close(series, [float(x) for x in e["output"]["forecast"]]):
            return e, "copy"
    for i in range(len(outs)):
        for j in range(i + 1, len(outs)):
            a, b = outs[i]["output"]["forecast"], outs[j]["output"]["forecast"]
            if len(a) == len(b) == len(series):
                mean = [(float(x) + float(y)) / 2 for x, y in zip(a, b)]
                if _close(series, mean):
                    return {"pair": [outs[i], outs[j]], "n": outs[j]["n"], "name": "mean_of_tools", "args": dict(outs[j]["args"])}, "mean"
    return None, ""


# ---------------------------------------------------------------- the check


def check(answer: Answer, tool_log: List[Dict[str, Any]], *, horizon_hours: int, question_kind: Optional[str]) -> Dict[str, Any]:
    results: Dict[str, Dict[str, Any]] = {}
    n_needed = int(horizon_hours) * STEPS_PER_HOUR
    series = list(answer.forecast)

    if not answer.json_ok:
        results["schema"] = {"passed": False, "detail": "no JSON answer with the contract"}
    elif not answer.claims_forecast:
        results["schema"] = {"passed": False, "detail": f"status is {answer.status!r}, not 'forecast'"}
    elif answer.n_non_numeric:
        results["schema"] = {"passed": False, "detail": f"{answer.n_non_numeric} non-numeric value(s) in the series"}
    elif len(series) != n_needed:
        results["schema"] = {"passed": False, "detail": f"the series has {len(series)} values; the horizon needs {n_needed}"}
    else:
        results["schema"] = {"passed": True, "detail": f"{n_needed} finite values"}

    if series and all(0.0 <= float(v) <= POWER_MAX_KW for v in series):
        results["range"] = {"passed": True, "detail": f"all values in [0, {POWER_MAX_KW:.0f}] kW"}
    elif series:
        lo, hi = min(series), max(series)
        results["range"] = {"passed": False, "detail": f"values from {lo:.1f} to {hi:.1f} kW; the range is [0, {POWER_MAX_KW:.0f}]"}
    else:
        results["range"] = {"passed": False, "detail": "no series"}

    src_entry, how = trace_forecast(series, tool_log) if series else (None, "")
    if src_entry is not None:
        named = (answer.source or "")
        name_ok = (named == src_entry["name"]) if how == "copy" else (named == "mean_of_tools")
        results["traceable"] = {"passed": bool(name_ok), "detail": (f"series is a {how} of {src_entry['name']} (call {src_entry['n']})"
                                                                     + ("" if name_ok else f", but source says {named!r}"))}
    else:
        results["traceable"] = {"passed": False, "detail": "the series matches no forecast-tool output and no mean of two" if series else "no series"}

    if src_entry is not None:
        args = src_entry.get("args") or {}
        problems = []
        if answer.turbine != args.get("turbine"):
            problems.append(f"turbine {answer.turbine} vs call {args.get('turbine')}")
        end = args.get("history_end_day")
        if end is not None and answer.history_days != [int(end) - HISTORY_DAYS + 1, int(end)]:
            problems.append(f"history_days {answer.history_days} vs call [{int(end) - HISTORY_DAYS + 1}, {end}]")
        if answer.horizon_hours != args.get("horizon_hours"):
            problems.append(f"horizon {answer.horizon_hours} vs call {args.get('horizon_hours')}")
        results["consistent"] = {"passed": not problems, "detail": "; ".join(problems) if problems else "formulation matches the producing call"}
    else:
        results["consistent"] = {"passed": False, "detail": "not assessable: no producing call"}

    implied = derive_answer(question_kind, series) if series else None
    m = answer_matches(question_kind, answer.answer, series)
    if m is None:
        results["coherent"] = {"passed": True, "detail": "the request asks no question"}
    else:
        results["coherent"] = {"passed": bool(m), "detail": f"answer {answer.answer} vs {implied} implied by the series" + ("" if m else " (disagree)")}

    return {
        "conditions": {k: results[k] for k in CONDITION_ORDER},
        "passed": all(results[k]["passed"] for k in CONDITION_ORDER),
        "failed": [k for k in CONDITION_ORDER if not results[k]["passed"]],
        "source_call": None if src_entry is None else {"n": src_entry.get("n"), "name": src_entry.get("name"), "how": how},
    }


def verdict_text(report: Dict[str, Any]) -> str:
    """The failed conditions, as the retry message hands them to the model."""
    return "\n".join(f"- {CONDITION_LABELS[k]} {k}: {report['conditions'][k]['detail']}" for k in report["failed"])

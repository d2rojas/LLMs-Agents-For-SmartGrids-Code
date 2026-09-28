"""The tool catalogue every grounded method calls, and the dispatcher that runs it.

Six tools in two kinds, one list, one schema builder, one dispatcher. Every method
with tools receives this exact catalogue with the same schemas; the methods
without tools receive the same catalogue rendered as text, so what a method may
do is never a difference between rows.

    query      read the history: a summary, raw rows, the fitted power curve
    forecast   write a series: persistence, the power curve on the last day's wind, the GRU

The dispatcher holds one frozen window. A call for another turbine or another
history window is refused with an error, the way a data service would refuse a
day it does not have; that refusal is what makes formulation measurable. Every
call is logged with its position, arguments, output and kind, which is what the
gate and the scorer read.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from config import HISTORY_DAYS, HORIZONS_H, MAX_HORIZON_H
from solver import forecasters as F
from solver.data import Window, history_csv

CATALOGUE: List[Dict[str, Any]] = [
    {"name": "get_history_summary", "kind": "query",
     "description": "Per-day means, maxima and valid-row counts of the 14-day SCADA history of a turbine, plus its last hour. Call this first to see what the data looks like and whether the last day is complete.",
     "parameters": {"turbine": {"type": "integer", "description": "turbine id"},
                    "history_end_day": {"type": "integer", "description": "the last day of the 14-day history (the day before the forecast starts)"}}},
    {"name": "get_history_rows", "kind": "query",
     "description": "The raw 10-minute rows (Day, Tmstamp, Wspd, Wdir, Etmp, Patv) of the last N days of the history, as CSV. Up to 14 days; each day is 144 rows.",
     "parameters": {"turbine": {"type": "integer"}, "history_end_day": {"type": "integer"},
                    "days": {"type": "integer", "description": "how many of the most recent history days to return, 1 to 14 (default 1)"}}},
    {"name": "fit_power_curve", "kind": "query",
     "description": "Fit the wind-speed-to-power curve of the turbine on its 14-day history: median power per 0.5 m/s bin, the cut-in speed and the highest median. Abnormal rows (curtailed, missing) are excluded.",
     "parameters": {"turbine": {"type": "integer"}, "history_end_day": {"type": "integer"}}},
    {"name": "persistence_forecast", "kind": "forecast",
     "description": "Forecast the next horizon_hours of active power by repeating the last history day's power. The simplest reference; exactly horizon_hours*6 values in kW.",
     "parameters": {"turbine": {"type": "integer"}, "history_end_day": {"type": "integer"},
                    "horizon_hours": {"type": "integer", "description": "3, 6 or 48"}}},
    {"name": "power_curve_forecast", "kind": "forecast",
     "description": "Forecast the next horizon_hours by applying the fitted power curve to the last history day's wind speeds, repeated. Exactly horizon_hours*6 values in kW.",
     "parameters": {"turbine": {"type": "integer"}, "history_end_day": {"type": "integer"}, "horizon_hours": {"type": "integer"}}},
    {"name": "gru_forecast", "kind": "forecast",
     "description": "Forecast the next horizon_hours with the GRU trained on the farm's training period (days 1-214) from the last 24 h of the four SCADA features. The conventional forecaster of this case study. Exactly horizon_hours*6 values in kW.",
     "parameters": {"turbine": {"type": "integer"}, "history_end_day": {"type": "integer"}, "horizon_hours": {"type": "integer"}}},
]
KINDS: Dict[str, str] = {t["name"]: t["kind"] for t in CATALOGUE}
FORECAST_TOOLS = tuple(t["name"] for t in CATALOGUE if t["kind"] == "forecast")
REQUIRED: Dict[str, List[str]] = {t["name"]: [k for k in t["parameters"] if k != "days"] for t in CATALOGUE}


def openai_schemas() -> List[Dict[str, Any]]:
    """The catalogue as OpenAI function-calling tool schemas."""
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                              "parameters": {"type": "object", "properties": t["parameters"], "required": REQUIRED[t["name"]]}}}
            for t in CATALOGUE]


def catalogue_text() -> str:
    """The same catalogue as text, for the methods that receive no tools and for the planner."""
    lines = []
    for kind in ("query", "forecast"):
        lines.append(f"### {kind} tools")
        for t in CATALOGUE:
            if t["kind"] != kind:
                continue
            sig = ", ".join(f"{k}: {v.get('type', 'any')}" + (" (required)" if k in REQUIRED[t["name"]] else "") for k, v in t["parameters"].items())
            lines.append(f"- {t['name']}({sig}): {t['description']}")
        lines.append("")
    return "\n".join(lines).rstrip()


class ToolDispatcher:
    """Runs tool calls on one frozen window and logs them.

    ``log`` entries: ``{n, name, kind, args, output, ok, latency_s}``. ``n`` is the
    1-based position of the call in the run.
    """

    def __init__(self, window: Window, *, max_calls: Optional[int] = None):
        self.window = window
        self.max_calls = max_calls
        self.log: List[Dict[str, Any]] = []
        self._curve: Optional[Dict[str, Any]] = None

    @property
    def n_calls(self) -> int:
        return len(self.log)

    @property
    def exhausted(self) -> bool:
        return self.max_calls is not None and self.n_charged >= self.max_calls

    # ---------------------------------------------------------------- checks

    def _check_window(self, args: Dict[str, Any]) -> Optional[str]:
        w = self.window
        try:
            t = int(args.get("turbine"))
            e = int(args.get("history_end_day"))
        except (TypeError, ValueError):
            return "turbine and history_end_day must be integers"
        if t != w.turbine:
            return f"turbine {t} is not available in this benchmark instance (available: turbine {w.turbine})"
        if e != w.history_end_day:
            return (f"history ending on day {e} is not available; the SCADA history of turbine {w.turbine} covers days "
                    f"{w.base_day} to {w.history_end_day} (history_end_day must be {w.history_end_day})")
        return None

    def _check_horizon(self, args: Dict[str, Any]) -> Optional[str]:
        try:
            h = int(args.get("horizon_hours"))
        except (TypeError, ValueError):
            return "horizon_hours must be an integer"
        if h < 1 or h > MAX_HORIZON_H:
            return f"horizon_hours must be between 1 and {MAX_HORIZON_H}"
        return None

    def _last_day_ok(self) -> Optional[str]:
        per = self.window.history_valid_rows_per_day()
        last = per.get(self.window.history_end_day, 0)
        if last < 72:
            return (f"the last history day (day {self.window.history_end_day}) has only {last} valid rows of 144: the SCADA feed is "
                    f"incomplete and no forecast can be grounded on it")
        return None

    # ---------------------------------------------------------------- tools

    def _run(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        err = self._check_window(args)
        if err:
            return {"error": err}
        w = self.window
        if name == "get_history_summary":
            return F.history_summary(w)
        if name == "get_history_rows":
            days = int(args.get("days") or 1)
            days = max(1, min(HISTORY_DAYS, days))
            return {"turbine": w.turbine, "days": [w.history_end_day - days + 1, w.history_end_day], "columns": "Day,Tmstamp,Wspd,Wdir,Etmp,Patv",
                    "csv": history_csv(w, days)}
        if name == "fit_power_curve":
            self._curve = F.fit_power_curve(w)
            return dict(self._curve)
        err = self._check_horizon(args)
        if err:
            return {"error": err}
        h = int(args["horizon_hours"])
        bad = self._last_day_ok()
        if bad:
            return {"error": bad}
        if name == "persistence_forecast":
            series = F.persistence(w, h)
        elif name == "power_curve_forecast":
            series = F.power_curve_forecast(w, h, self._curve)
        elif name == "gru_forecast":
            series = F.gru_forecast(w, h)
        else:
            return {"error": f"unknown tool {name!r}"}
        return {"turbine": w.turbine, "history_end_day": w.history_end_day, "horizon_hours": h, "n_values": len(series),
                "unit": "kW", "method": name, "forecast": series}

    def _seen(self, name: str, args: Dict[str, Any]) -> Optional[int]:
        key = json.dumps(args, sort_keys=True, default=str)
        for e in self.log:
            if e["name"] == name and e["kind"] != "duplicate" and json.dumps(e["args"], sort_keys=True, default=str) == key:
                return e["n"]
        return None

    @property
    def n_charged(self) -> int:
        return sum(1 for e in self.log if e["kind"] != "duplicate")

    def call(self, name: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        args = dict(args or {})
        t0 = time.time()
        dup = self._seen(name, args) if name in KINDS else None
        if dup is not None:
            out: Dict[str, Any] = {"error": f"identical to call {dup}: the tools are deterministic, so the result is the one already returned; use it"}
            entry = {"n": len(self.log) + 1, "name": name, "kind": "duplicate", "args": args, "output": out, "ok": False, "latency_s": 0.0}
            self.log.append(entry)
            return out
        if self.exhausted:
            out: Dict[str, Any] = {"error": f"tool budget exhausted ({self.max_calls} calls); write the final answer"}
            ok = False
        elif name not in KINDS:
            out, ok = {"error": f"unknown tool {name!r}"}, False
        else:
            missing = [k for k in REQUIRED[name] if k not in args]
            if missing:
                out, ok = {"error": f"{name}: missing required argument(s) {missing}"}, False
            else:
                try:
                    out = json.loads(json.dumps(self._run(name, args), default=str))
                    ok = not (isinstance(out, dict) and "error" in out)
                except Exception as e:  # a tool must never take the run down
                    out, ok = {"error": f"{type(e).__name__}: {e}"}, False
        entry = {"n": len(self.log) + 1, "name": name, "kind": KINDS.get(name, "unknown"), "args": args, "output": out, "ok": ok,
                 "latency_s": round(time.time() - t0, 4)}
        self.log.append(entry)
        return out

    def forecast_outputs(self) -> List[Dict[str, Any]]:
        """Every successful forecast-tool output in the log, in order."""
        return [e for e in self.log if e["kind"] == "forecast" and e["ok"] and isinstance(e["output"], dict) and e["output"].get("forecast")]

"""The answer contract every method returns, and how it is read from model text.

Every method ends with the same JSON object (``methods/_shared/output_contract.txt``).
``parse_answer`` reads it from whatever the model wrote: a bare object, an object
after ``FINAL ANSWER:``, an object inside a code fence. ``Answer`` normalises the
fields so the gate and the scorer read one shape for every method, and keeps
``raw`` for the trace. A text with no object at all yields an ``Answer`` with
``json_ok=False`` and everything else empty, so a method that did not follow the
contract is scored, not crashed.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

STATUSES = ("forecast", "cannot_forecast")
SOURCES = ("persistence_forecast", "power_curve_forecast", "gru_forecast", "mean_of_tools", "own_computation")


@dataclass
class Answer:
    json_ok: bool
    raw: str
    obj: Dict[str, Any] = field(default_factory=dict)
    turbine: Optional[int] = None
    history_days: Optional[List[int]] = None
    horizon_hours: Optional[int] = None
    forecast: List[float] = field(default_factory=list)
    n_non_numeric: int = 0
    source: Optional[str] = None
    answer: Optional[float] = None
    status: Optional[str] = None
    cannot_forecast: Optional[str] = None
    summary: str = ""

    @property
    def claims_forecast(self) -> bool:
        return self.status == "forecast"

    @property
    def declares_failure(self) -> bool:
        return self.status == "cannot_forecast" or bool(self.cannot_forecast)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "json_ok": self.json_ok, "turbine": self.turbine, "history_days": self.history_days, "horizon_hours": self.horizon_hours,
            "n_forecast_values": len(self.forecast), "n_non_numeric": self.n_non_numeric, "source": self.source, "answer": self.answer,
            "status": self.status, "cannot_forecast": self.cannot_forecast, "summary": self.summary,
        }


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """The last complete JSON object in ``text`` that has a ``status`` or ``forecast`` key."""
    if not text:
        return None
    t = text
    m = re.search(r"FINAL ANSWER:\s*", t)
    if m:
        t = t[m.end():]
    candidates: List[str] = [f.group(1) for f in re.finditer(r"```(?:json)?\s*(.*?)```", t, re.S)]
    candidates.append(t)
    for cand in candidates:
        starts = [i for i, ch in enumerate(cand) if ch == "{"]
        for s in starts:
            depth = 0
            for j in range(s, len(cand)):
                if cand[j] == "{":
                    depth += 1
                elif cand[j] == "}":
                    depth -= 1
                    if depth == 0:
                        chunk = cand[s:j + 1]
                        try:
                            obj = json.loads(chunk)
                        except json.JSONDecodeError:
                            break
                        if isinstance(obj, dict) and ("status" in obj or "forecast" in obj):
                            return obj
                        break
    return None


def _num(v: Any) -> Optional[float]:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(float(v)) else None
    if isinstance(v, str):
        try:
            x = float(v.strip())
            return x if math.isfinite(x) else None
        except ValueError:
            return None
    return None


def _int(v: Any) -> Optional[int]:
    x = _num(v)
    return int(round(x)) if x is not None else None


def parse_answer(text: str) -> Answer:
    obj = extract_json_object(text or "")
    if obj is None:
        return Answer(json_ok=False, raw=text or "")
    fm = obj.get("formulation") if isinstance(obj.get("formulation"), dict) else {}
    hd = fm.get("history_days")
    history_days = [_int(hd[0]), _int(hd[1])] if isinstance(hd, (list, tuple)) and len(hd) == 2 and all(_int(x) is not None for x in hd) else None
    raw_f = obj.get("forecast")
    forecast: List[float] = []
    bad = 0
    if isinstance(raw_f, (list, tuple)):
        for v in raw_f:
            x = _num(v)
            if x is None:
                bad += 1
            else:
                forecast.append(x)
    status = str(obj.get("status") or "").strip().lower() or None
    if status not in STATUSES:
        status = {"ok": "forecast", "done": "forecast", "success": "forecast", "failed": "cannot_forecast", "abstain": "cannot_forecast",
                  "cannot_answer": "cannot_forecast"}.get(status or "", status)
    cf = obj.get("cannot_forecast")
    cf_text = cf.strip() if isinstance(cf, str) and cf.strip() else ("declared" if cf is True else None)
    if status is None:
        status = "cannot_forecast" if cf_text else ("forecast" if forecast else None)
    src = str(obj.get("source") or "").strip().lower() or None
    return Answer(
        json_ok=True, raw=text or "", obj=obj, turbine=_int(fm.get("turbine")), history_days=history_days,
        horizon_hours=_int(fm.get("horizon_hours")), forecast=forecast, n_non_numeric=bad, source=src,
        answer=_num(obj.get("answer")), status=status, cannot_forecast=cf_text, summary=str(obj.get("summary") or ""),
    )


def declared_failure(reason: str, *, turbine: Optional[int] = None, history_days: Optional[List[int]] = None, horizon_hours: Optional[int] = None) -> Dict[str, Any]:
    """The answer the harness writes when a method cannot produce one that passes: no forecast, no unsupported number."""
    return {
        "formulation": {"turbine": turbine, "history_days": history_days, "horizon_hours": horizon_hours},
        "forecast": [],
        "source": None,
        "answer": None,
        "status": "cannot_forecast",
        "cannot_forecast": reason,
        "summary": f"Declared failure: {reason}",
    }

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
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

STATUSES = ("repaired", "not_repaired", "cannot_repair")


@dataclass
class Answer:
    json_ok: bool
    raw: str
    obj: Dict[str, Any] = field(default_factory=dict)
    fault_type: Optional[str] = None
    components: Dict[str, List[int]] = field(default_factory=dict)
    explanation: str = ""
    actions: List[Dict[str, Any]] = field(default_factory=list)
    claimed_converged: Optional[bool] = None
    claimed_new_violations: Optional[int] = None
    claimed_islanded: List[int] = field(default_factory=list)
    status: Optional[str] = None
    remaining: List[str] = field(default_factory=list)
    summary: str = ""

    @property
    def claims_repaired(self) -> bool:
        return self.status == "repaired"

    @property
    def declares_failure(self) -> bool:
        return self.status in ("not_repaired", "cannot_repair")

    def as_dict(self) -> Dict[str, Any]:
        return {
            "json_ok": self.json_ok, "fault_type": self.fault_type, "components": self.components,
            "explanation": self.explanation, "actions": self.actions,
            "claimed_converged": self.claimed_converged, "claimed_new_violations": self.claimed_new_violations,
            "claimed_islanded": self.claimed_islanded, "status": self.status, "remaining": self.remaining,
            "summary": self.summary,
        }


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """The last complete JSON object in ``text`` that has a ``status`` or ``diagnosis`` key."""
    if not text:
        return None
    t = text
    m = re.search(r"FINAL ANSWER:\s*", t)
    if m:
        t = t[m.end():]
    candidates: List[str] = []
    for fence in re.finditer(r"```(?:json)?\s*(.*?)```", t, re.S):
        candidates.append(fence.group(1))
    candidates.append(t)
    for cand in candidates:
        # scan for balanced braces, last object first
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
                        if isinstance(obj, dict) and ("status" in obj or "diagnosis" in obj):
                            return obj
                        break
    return None


def _int_list(v: Any) -> List[int]:
    out: List[int] = []
    if isinstance(v, (list, tuple)):
        for x in v:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                m = re.search(r"-?\d+", str(x))
                if m:
                    out.append(int(m.group()))
    elif isinstance(v, (int, float)):
        out.append(int(v))
    elif isinstance(v, str):
        out += [int(m) for m in re.findall(r"-?\d+", v)]
    return out


def parse_answer(text: str) -> Answer:
    obj = extract_json_object(text or "")
    if obj is None:
        return Answer(json_ok=False, raw=text or "")
    diag = obj.get("diagnosis") if isinstance(obj.get("diagnosis"), dict) else {}
    comps: Dict[str, List[int]] = {}
    for k, v in (diag.get("components") or {}).items() if isinstance(diag.get("components"), dict) else []:
        ids = _int_list(v)
        if ids:
            comps[str(k)] = ids
    fs = obj.get("final_state") if isinstance(obj.get("final_state"), dict) else {}
    conv = fs.get("converged")
    conv = bool(conv) if isinstance(conv, bool) else (None if conv is None else str(conv).lower() == "true")
    nnew = fs.get("n_new_violations", fs.get("n_violations"))
    try:
        nnew = int(nnew) if nnew is not None else None
    except (TypeError, ValueError):
        nnew = None
    status = str(obj.get("status") or "").strip().lower() or None
    if status not in STATUSES:
        status = {"fixed": "repaired", "success": "repaired", "partial": "not_repaired", "failed": "cannot_repair", "unrepaired": "not_repaired"}.get(status or "", status)
    actions = []
    for a in obj.get("actions") or []:
        if isinstance(a, dict) and a.get("tool"):
            actions.append({"tool": str(a["tool"]), "args": dict(a.get("args") or {})})
    remaining = [str(x) for x in (obj.get("remaining_violations") or []) if str(x).strip()]
    return Answer(
        json_ok=True, raw=text or "", obj=obj,
        fault_type=(str(diag.get("fault_type")).strip().lower() if diag.get("fault_type") else None),
        components=comps, explanation=str(diag.get("explanation") or ""),
        actions=actions, claimed_converged=conv, claimed_new_violations=nnew,
        claimed_islanded=_int_list(fs.get("islanded_load_buses")),
        status=status, remaining=remaining, summary=str(obj.get("summary") or ""),
    )


def declared_failure(reason: str, remaining: List[str], *, fault_type: Optional[str] = None, components: Optional[Dict[str, List[int]]] = None) -> Dict[str, Any]:
    """The answer the harness writes when a method cannot produce one that passes: no repair claim, no unsupported number."""
    return {
        "diagnosis": {"fault_type": fault_type or "none", "components": components or {}, "explanation": ""},
        "actions": [],
        "final_state": {"converged": None, "n_new_violations": None, "islanded_load_buses": []},
        "status": "cannot_repair",
        "remaining_violations": list(remaining),
        "summary": f"Declared failure: {reason}",
    }

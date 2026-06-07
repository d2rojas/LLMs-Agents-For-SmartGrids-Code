"""
intent_parser.py
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ParsedRequest:
    """Structured representation of a user's command."""

    intent: str
    case_id: Optional[str] = None
    case_num: Optional[int] = None
    solver: Optional[str] = None
    outputs: List[str] = field(default_factory=list)
    visualize: bool = False
    highlights: List[str] = field(default_factory=list)
    contingencies: List[Dict[str, Any]] = field(default_factory=list)
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "case_id": self.case_id,
            "case_num": self.case_num,
            "solver": self.solver,
            "outputs": list(self.outputs),
            "visualize": self.visualize,
            "highlights": list(self.highlights),
            "contingencies": list(self.contingencies),
            "raw_text": self.raw_text,
        }

    def to_json(self, *, indent: int = 2, ensure_ascii: bool = False) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=ensure_ascii)

_SOLVER_ALIASES: Dict[str, Tuple[str, ...]] = {
    "pandapower": ("pandapower", "panda power", "ppower"),
    "andes": ("andes",),
    "matpower": ("matpower", "matlab"),
    "pypower": ("pypower",),
}

_HELP_KW = ("help", "usage", "how to", "command", "assist", "guide")

_RUN_KW = (
    "run",
    "solve",
    "calculate",
    "compute",
    "execute",
    "power flow",
    "load flow",
    "pf",
)

_WHATIF_KW = (
    "what if",
    "suppose",
    "assuming",
    "hypothetically",
    "in case",
    "given that",
    "scenario",
)

_VOLT_KW = ("bus voltage", "bus volt", "voltage", "vpu", "vm")

_LINEFLOW_KW = (
    "line flow",
    "line flows",
    "branch flow",
    "branch flows",
    "line loading",
    "thermal",
    "line",
    "branch",
    "circuit",
)

_VIOLATION_KW = (
    "violation",
    "violations",
    "limit",
    "limits",
    "overload",
    "overflow",
    "constraint",
    "constraints",
    "high voltage",
    "low voltage",
    "exceed",
    "breach",
)

_VIS_KW = (
    "plot",
    "graph",
    "visualize",
    "visualisation",
    "visualization",
    "diagram",
    "map",
    "heatmap",
    "chart",
    "draw",
    "figure",
)

_DISCONNECT_KW = (
    "disconnect",
    "open",
    "trip",
    "outage",
    "remove",
    "cut",
    "break",
)

_LINE_KW = ("line", "branch", "circuit", "tie")


# ----------------------------
# Public API
# ----------------------------

def parse_intent(
    text: str,
    *,
    default_case: Optional[str] = "case14",
    default_outputs: Tuple[str, ...] = ("bus_voltages", "line_flows"),
) -> ParsedRequest:
    raw = text or ""
    norm = _normalize(raw)

    case_num = _detect_case_num(norm)
    case_id = f"case{case_num}" if case_num is not None else default_case

    solver = _detect_solver(norm)
    contingencies = _detect_contingencies(norm)

    outputs = _detect_outputs(norm, default_outputs=default_outputs)
    visualize = _contains_any(norm, _VIS_KW)
    highlights = _detect_highlights(norm)

    intent = _detect_intent(norm, contingencies=contingencies)

    return ParsedRequest(
        intent=intent,
        case_id=case_id,
        case_num=case_num,
        solver=solver,
        outputs=outputs,
        visualize=visualize,
        highlights=highlights,
        contingencies=contingencies,
        raw_text=raw,
    )

def _normalize(text: str) -> str:
    t = text.strip().lower()
    t = t.replace("–", "-").replace("—", "-").replace("−", "-")
    t = re.sub(r"[\"'""'']", "", t)
    t = re.sub(r"[\(\)\[\]\{\},;:]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t


def _contains_any(text: str, keywords: Tuple[str, ...]) -> bool:
    return any(k in text for k in keywords)


def _detect_solver(norm: str) -> Optional[str]:
    best_solver: Optional[str] = None
    best_pos: Optional[int] = None
    for canonical, aliases in _SOLVER_ALIASES.items():
        for a in aliases:
            pos = norm.find(a)
            if pos != -1 and (best_pos is None or pos < best_pos):
                best_solver = canonical
                best_pos = pos
    return best_solver


def _detect_case_num(norm: str) -> Optional[int]:
    patterns = [
        r"\bcase\s*0*(\d{1,4})\b",
        r"\bieee\s*0*(\d{1,4})\s*(?:-?\s*bus\b)",
        r"\b0*(\d{1,4})\s*(?:-?\s*bus\b)",
        r"\bieee\s*0*(\d{1,4})\b",
    ]
    for pat in patterns:
        m = re.search(pat, norm)
        if m:
            try:
                n = int(m.group(1))
            except ValueError:
                continue
            if 0 < n < 10000:
                return n
    return None


def _detect_outputs(norm: str, *, default_outputs: Tuple[str, ...]) -> List[str]:
    requested: List[str] = []

    wants_v = _contains_any(norm, _VOLT_KW)
    wants_f = _contains_any(norm, _LINEFLOW_KW)
    wants_violation = _contains_any(norm, _VIOLATION_KW)

    if wants_v:
        requested.append("bus_voltages")
    if wants_f:
        requested.append("line_flows")
    if wants_violation:
        requested.append("violations")

    if not requested:
        requested = list(default_outputs)

    return _dedup(requested)


def _detect_highlights(norm: str) -> List[str]:
    highlights: List[str] = []
    if _contains_any(norm, _VOLT_KW):
        highlights.append("voltage")
    if _contains_any(norm, _LINEFLOW_KW):
        highlights.append("line_flow")
    if _contains_any(norm, _VIOLATION_KW):
        highlights.append("violations")
    return _dedup(highlights)


def _detect_intent(norm: str, *, contingencies: List[Dict[str, Any]]) -> str:
    if _contains_any(norm, _HELP_KW):
        return "help"

    if contingencies:
        return "what_if"

    if _contains_any(norm, _WHATIF_KW) and _contains_any(norm, _DISCONNECT_KW + _LINE_KW):
        return "what_if"

    if _contains_any(norm, _RUN_KW):
        return "run_power_flow"

    if _detect_case_num(norm) is not None:
        return "run_power_flow"

    return "unknown"


def _detect_contingencies(norm: str) -> List[Dict[str, Any]]:
    contingencies: List[Dict[str, Any]] = []

    if not _contains_any(norm, _DISCONNECT_KW):
        return contingencies
    if not _contains_any(norm, _LINE_KW):
        return contingencies

    patterns = [
        r"(?:line|branch|circuit|tie)\s*(?:between\s*)?(?:bus\s*)?(\d+)\s*(?:and|to|~|-)\s*(?:bus\s*)?(\d+)\b",
        r"(?:bus\s*)?(\d+)\s*-\s*(?:bus\s*)?(\d+)\s*(?:line|branch|circuit|tie)\b",
    ]

    for pat in patterns:
        for m in re.finditer(pat, norm):
            try:
                a = int(m.group(1))
                b = int(m.group(2))
            except (TypeError, ValueError):
                continue
            if a <= 0 or b <= 0 or a == b:
                continue
            contingencies.append(
                {
                    "type": "line_outage",
                    "from_bus": a,
                    "to_bus": b,
                    "action": "disconnect",
                }
            )

    return _dedup_dicts(contingencies)


def _dedup(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _dedup_dicts(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for d in items:
        key = tuple(sorted(d.items()))
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out
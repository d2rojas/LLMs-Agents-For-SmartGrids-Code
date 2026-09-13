"""baselines/rule_based.py

Deterministic, LLM-free rule-based baseline for PFAgent.

Maps a natural-language request to ``ToolDispatcher`` calls using regular
expressions only, so the comparison isolates what the LLM contributes on top of
tool access: same tools, same solver, same verification, no language model.

Supported operations (one example each):
  load case              "load case14", "load the IEEE 30-bus system"
  run power flow         "run power flow", "solve the load flow"
  set active load        "set load at bus 7 to 45 MW"  (MVA accepted, flagged)
  disconnect line        "disconnect line 4-5", "trip the line between bus 4 and bus 5"
  reconnect line         "reconnect line 4-5", "restore the line from bus four to bus five"
  worst voltage bus      "report the worst voltage bus", "which bus has the lowest voltage"
  lines above threshold  "list lines with loading above 80 percent", "show overloaded lines"
  N-1 contingency        "run N-1 contingency analysis", "n-1 top 3"

Bus numbers may be digits or English number words up to twenty. Requests may
chain several operations ("load case14, run power flow, then report the worst
voltage bus"). Anything not matched raises ``CannotParse`` — the baseline never
guesses.

Public API
  parse(text) -> list[{"tool", "args", ...}]      (raises CannotParse)
  parse_detailed(text) -> {"plan", "warnings", "clauses"}
  run(text, ctx, dispatcher=None) -> dict          (never raises on parse failure)
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from llm.tools import TOOLS, ToolContext, ToolDispatcher, build_default_dispatcher

TOOL_NAMES = {t["name"] for t in TOOLS}

SUPPORTED_CASES = ("14", "30", "57", "118", "300")

_NUMBER_WORDS: Dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20,
}
_WORD_ALT = "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True))
_BUS_TOKEN = rf"(\d+|{_WORD_ALT})"
_NUM = r"(\d+(?:\.\d+)?)"

MVA_WARNING = "MVA interpreted as active power (MW); apparent power is not a load setpoint."


class CannotParse(ValueError):
    """Raised when a clause matches no supported phrasing."""

    def __init__(self, clause: str, full_text: str = ""):
        super().__init__(f"cannot parse: {clause!r}")
        self.clause = clause
        self.full_text = full_text


def words_to_int(token: str) -> int:
    """'7' -> 7, 'seven' -> 7. Raises ValueError for anything else."""
    s = str(token).strip().lower()
    if re.fullmatch(r"\d+", s):
        return int(s)
    if s in _NUMBER_WORDS:
        return _NUMBER_WORDS[s]
    raise ValueError(f"not a bus number: {token!r}")


# ---------------------------------------------------------------------------
# Clause splitting
# ---------------------------------------------------------------------------

_ACTION_VERBS = (
    r"load|open|use|run|solve|compute|calculate|perform|execute|set|change|modify|update|"
    r"increase|decrease|disconnect|reconnect|trip|remove|close|restore|report|list|show|"
    r"find|which|what|tell|give|identify|do|make|please"
)
_SPLIT_RE = re.compile(
    rf"\s*(?:;|\.(?:\s|$)|\bthen\b|\bafter that\b|,?\s*\band\b\s+(?=(?:{_ACTION_VERBS})\b)|,\s+(?=(?:{_ACTION_VERBS})\b))\s*",
    flags=re.IGNORECASE,
)


def _split_clauses(text: str) -> List[str]:
    parts = [p.strip(" ,.;\n\t") for p in _SPLIT_RE.split(text)]
    return [p for p in parts if p]


# ---------------------------------------------------------------------------
# Per-operation grammars (checked in order; first match wins per clause)
# ---------------------------------------------------------------------------

_CASE_RE = re.compile(
    rf"(?:\bcase\s*(\d+)\b|\bieee[\s-]*(\d+)[\s-]*(?:bus|node)?\b|\b(\d+)[\s-]*(?:bus|node)\b(?:\s+(?:system|case|network|test\s+case))?)",
    flags=re.IGNORECASE,
)
_LOAD_CASE_CTX_RE = re.compile(r"\b(load|open|use|switch\s+to|select)\b|\bcase\b|\bieee\b", flags=re.IGNORECASE)

_RUN_PF_RE = re.compile(r"\b(?:power\s*flow|load\s*flow|ac\s*pf|\bpf\b|newton[\s-]*raphson)\b", flags=re.IGNORECASE)
_N1_RE = re.compile(r"\bn\s*-\s*1\b|\bn1\b|\bcontingenc(?:y|ies)\b", flags=re.IGNORECASE)
_TOP_K_RE = re.compile(rf"\btop[\s-]*{_BUS_TOKEN}\b", flags=re.IGNORECASE)

_SET_LOAD_RE = re.compile(
    rf"\b(?:set|change|modify|update|adjust|make)\b.*?\b(?:load|demand)\b.*?\b(?:at|on|of)\s+bus\s+{_BUS_TOKEN}\b.*?\b(?:to|=|at)\s*{_NUM}\s*(mw|mva|megawatts?)\b"
    rf"(?:.*?\b(?:and\s+)?(?:q|reactive(?:\s+power)?)\s*(?:to|=|of)?\s*{_NUM}\s*mvar\b)?",
    flags=re.IGNORECASE,
)
_SET_LOAD_ALT_RE = re.compile(
    rf"\b(?:set|change|modify|update|adjust|make)\b.*?\bbus\s+{_BUS_TOKEN}\b.*?\b(?:load|demand)\b.*?\b(?:to|=|at)\s*{_NUM}\s*(mw|mva|megawatts?)\b",
    flags=re.IGNORECASE,
)

_LINE_PAIR = rf"(?:bus\s+)?{_BUS_TOKEN}\s*(?:-|–|—|to|and|,|/)\s*(?:bus\s+)?{_BUS_TOKEN}\b"
_DISCONNECT_RE = re.compile(
    rf"\b(disconnect|open|trip|remove|outage|take\s+out|switch\s+off)\b.*?\b(?:line|branch)\b\s*(?:between|from)?\s*{_LINE_PAIR}",
    flags=re.IGNORECASE,
)
_RECONNECT_RE = re.compile(
    rf"\b(reconnect|restore|close|re-close|reclose|put\s+back|switch\s+on)\b.*?\b(?:line|branch)\b\s*(?:between|from)?\s*{_LINE_PAIR}",
    flags=re.IGNORECASE,
)

_WORST_V_RE = re.compile(
    r"(?:\b(?:worst|lowest|minimum|min|weakest)\b.*?\bvoltage\b)|(?:\bvoltage\b.*?\b(?:worst|lowest|minimum|min|weakest)\b)",
    flags=re.IGNORECASE,
)
_LINES_ABOVE_RE = re.compile(
    rf"\b(?:lines?|branches?)\b.*?\b(?:loading|loaded|loads?)\b.*?\b(?:above|over|exceeding|more\s+than|greater\s+than|higher\s+than|>)\s*{_NUM}\s*(?:%|percent)?",
    flags=re.IGNORECASE,
)
_LINES_ABOVE_ALT_RE = re.compile(
    rf"\b(?:loading|loaded)\b.*?\b(?:above|over|exceeding|more\s+than|greater\s+than|>)\s*{_NUM}\s*(?:%|percent)?.*?\b(?:lines?|branches?)\b",
    flags=re.IGNORECASE,
)
_OVERLOADED_RE = re.compile(r"\boverloaded\b.*?\b(?:lines?|branches?)\b|\b(?:lines?|branches?)\b.*?\boverloaded\b", flags=re.IGNORECASE)


def _parse_clause(clause: str, warnings: List[str]) -> List[Dict[str, Any]]:
    """Return the tool steps for one clause, or [] if nothing matched."""
    c = clause.strip()

    # --- load case --------------------------------------------------------
    m = _CASE_RE.search(c)
    if m and _LOAD_CASE_CTX_RE.search(c) and not _SET_LOAD_RE.search(c) and not _DISCONNECT_RE.search(c) and not _RECONNECT_RE.search(c):
        num = next(g for g in m.groups() if g)
        if num in SUPPORTED_CASES:
            return [{"tool": "load_case", "args": {"case_name": f"case{num}"}}]
        warnings.append(f"unsupported case size {num}; supported: {', '.join(SUPPORTED_CASES)}")
        return []

    # --- set load ------------------------------------------------------------
    m = _SET_LOAD_RE.search(c)
    q_val: Optional[str] = None
    if m:
        bus_tok, p_str, unit, q_val = m.group(1), m.group(2), m.group(3), m.group(4)
    else:
        m = _SET_LOAD_ALT_RE.search(c)
        if m:
            bus_tok, p_str, unit = m.group(1), m.group(2), m.group(3)
    if m:
        step: Dict[str, Any] = {"tool": "modify_load", "args": {"bus_id": words_to_int(bus_tok), "p_mw": float(p_str)}}
        if q_val is not None:
            step["args"]["q_mvar"] = float(q_val)
        if unit.lower() == "mva":
            step["flags"] = ["mva_as_mw"]
            warnings.append(MVA_WARNING)
        return [step]

    # --- disconnect / reconnect -------------------------------------------------
    m = _RECONNECT_RE.search(c)
    if m:
        return [{"tool": "reconnect_line", "args": {"from_bus": words_to_int(m.group(2)), "to_bus": words_to_int(m.group(3))}}]
    m = _DISCONNECT_RE.search(c)
    if m:
        return [{"tool": "disconnect_line", "args": {"from_bus": words_to_int(m.group(2)), "to_bus": words_to_int(m.group(3))}}]

    # --- N-1 ----------------------------------------------------------------------
    if _N1_RE.search(c):
        args: Dict[str, Any] = {"top_k": 5}
        mk = _TOP_K_RE.search(c)
        if mk:
            args["top_k"] = words_to_int(mk.group(1))
        return [{"tool": "run_n1_contingency", "args": args}]

    # --- derived reports (need a solved state; re-running PF is idempotent) -------
    if _WORST_V_RE.search(c):
        return [{"tool": "run_powerflow", "args": {}, "derive": {"kind": "min_voltage_bus"}}]
    m = _LINES_ABOVE_RE.search(c) or _LINES_ABOVE_ALT_RE.search(c)
    if m:
        return [{"tool": "run_powerflow", "args": {}, "derive": {"kind": "lines_above_loading", "threshold_percent": float(m.group(1))}}]
    if _OVERLOADED_RE.search(c):
        return [{"tool": "run_powerflow", "args": {}, "derive": {"kind": "lines_above_loading", "threshold_percent": 100.0}}]

    # --- run power flow (checked last: many clauses mention "power flow") -------------
    if _RUN_PF_RE.search(c):
        return [{"tool": "run_powerflow", "args": {}}]

    return []


def parse_detailed(request_text: str) -> Dict[str, Any]:
    """Parse into {"plan": [...], "warnings": [...], "clauses": [...]}; raises CannotParse."""
    text = (request_text or "").strip()
    if not text:
        raise CannotParse("", request_text)

    warnings: List[str] = []
    plan: List[Dict[str, Any]] = []
    clauses = _split_clauses(text)
    if not clauses:
        raise CannotParse(text, request_text)

    for clause in clauses:
        steps = _parse_clause(clause, warnings)
        if not steps:
            raise CannotParse(clause, request_text)
        for step in steps:
            # Collapse consecutive plain run_powerflow steps ("run PF, then report worst voltage").
            if (
                plan
                and step["tool"] == "run_powerflow"
                and plan[-1]["tool"] == "run_powerflow"
                and "derive" not in plan[-1]
            ):
                plan[-1] = step
                continue
            plan.append(step)

    for step in plan:
        assert step["tool"] in TOOL_NAMES, step["tool"]
    return {"plan": plan, "warnings": warnings, "clauses": clauses}


def parse(request_text: str) -> List[Dict[str, Any]]:
    """Map a request to an ordered list of {"tool", "args"} steps (plus optional
    "flags" / "derive" keys). Raises CannotParse for unsupported phrasing."""
    return parse_detailed(request_text)["plan"]


# ---------------------------------------------------------------------------
# Derived reports (computed from solver output only)
# ---------------------------------------------------------------------------


def _derive(kind_spec: Dict[str, Any], pf_out: Dict[str, Any]) -> Dict[str, Any]:
    kind = kind_spec.get("kind")
    if not pf_out.get("converged"):
        return {"kind": kind, "error": "power flow did not converge; no verified numbers available"}

    if kind == "min_voltage_bus":
        bvs = pf_out.get("bus_voltages") or []
        if not bvs:
            return {"kind": kind, "error": "no bus voltages in result"}
        worst = min(bvs, key=lambda b: float(b["vm_pu"]))
        return {
            "kind": kind,
            "bus_id": int(worst["bus_id"]),
            "vm_pu": float(worst["vm_pu"]),
            "text": f"Minimum voltage: bus {int(worst['bus_id'])} at {float(worst['vm_pu']):.4f} p.u.",
        }

    if kind == "lines_above_loading":
        thr = float(kind_spec.get("threshold_percent", 100.0))
        lines = [
            {"line_id": int(lf["line_id"]), "from_bus": int(lf["from_bus"]), "to_bus": int(lf["to_bus"]), "loading_percent": float(lf["loading_percent"])}
            for lf in (pf_out.get("line_flows") or [])
            if float(lf.get("loading_percent", 0.0)) > thr
        ]
        lines.sort(key=lambda d: -d["loading_percent"])
        if lines:
            body = "; ".join(f"line {d['from_bus']}-{d['to_bus']} at {d['loading_percent']:.1f}%" for d in lines)
            text = f"{len(lines)} line(s) above {thr:g}% loading: {body}."
        else:
            text = f"No lines above {thr:g}% loading."
        return {"kind": kind, "threshold_percent": thr, "lines": lines, "text": text}

    return {"kind": kind, "error": f"unknown derived report: {kind}"}


def _summarize(tool: str, out: Dict[str, Any]) -> str:
    if out.get("error"):
        return f"{tool}: error: {out['error']}"
    if tool == "load_case":
        return f"Loaded {out.get('case_name')} ({out.get('n_buses')} buses, {out.get('n_lines')} branches)."
    if tool in ("run_powerflow", "modify_load", "disconnect_line", "reconnect_line"):
        if not out.get("converged"):
            return f"{tool}: power flow did not converge."
        return (
            f"{tool}: converged; load {out['total_load_mw']:.3f} MW, generation {out['total_generation_mw']:.3f} MW, "
            f"losses {out['total_loss_mw']:.3f} MW; {len(out.get('voltage_violations') or [])} voltage and "
            f"{len(out.get('thermal_violations') or [])} thermal violation(s)."
        )
    if tool == "run_n1_contingency":
        rep = out.get("n1_report") or {}
        res = rep.get("results") or []
        if not res:
            return "run_n1_contingency: no contingencies ranked."
        top = res[0]
        return (
            f"N-1: {len(res)} ranked contingencies; worst is branch {top['from_bus']}-{top['to_bus']} "
            f"(converged={top['converged']}, {top['n_voltage_violations']} V / {top['n_thermal_violations']} thermal violations)."
        )
    return f"{tool}: done."


def run(request_text: str, ctx: ToolContext, dispatcher: Optional[ToolDispatcher] = None) -> Dict[str, Any]:
    """Parse and execute a request through the real ToolDispatcher.

    Returns {"ok", "status", "plan", "warnings", "outputs": [{"tool","args","output"}],
             "derived": [...], "answer": str}. Parse failures give status
             "cannot_parse" with an explicit message; nothing is executed.
    """
    try:
        parsed = parse_detailed(request_text)
    except CannotParse as e:
        return {
            "ok": False,
            "status": "cannot_parse",
            "message": f"cannot parse: {e.clause!r}",
            "unparsed_clause": e.clause,
            "plan": [],
            "warnings": [],
            "outputs": [],
            "derived": [],
            "answer": f"I cannot parse this request (unsupported phrasing: {e.clause!r}). No action was taken.",
        }

    if dispatcher is None:
        dispatcher = build_default_dispatcher(ctx)

    outputs: List[Dict[str, Any]] = []
    derived: List[Dict[str, Any]] = []
    lines: List[str] = []
    ok = True
    for step in parsed["plan"]:
        raw = dispatcher.dispatch(step["tool"], step["args"])
        try:
            out = json.loads(raw)
        except Exception:
            out = {"raw": raw}
        if not isinstance(out, dict):
            out = {"raw": out}
        outputs.append({"tool": step["tool"], "args": step["args"], "output": out})
        if out.get("error"):
            ok = False
        lines.append(_summarize(step["tool"], out))
        if "derive" in step:
            d = _derive(step["derive"], out)
            derived.append(d)
            lines.append(d.get("text") or f"{d.get('kind')}: {d.get('error')}")

    for w in parsed["warnings"]:
        lines.append(f"Warning: {w}")

    return {
        "ok": ok,
        "status": "ok" if ok else "tool_error",
        "plan": parsed["plan"],
        "warnings": parsed["warnings"],
        "outputs": outputs,
        "derived": derived,
        "answer": "\n".join(lines),
    }

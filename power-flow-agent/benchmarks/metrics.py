"""Per-item benchmark metrics computed from an engine trace and a request.

These metrics separate *formulation* correctness (did the method call the right
tools with the right arguments, in the right order) from *solve* correctness
(Tier I-III numbers vs the PandaPower ground truth, computed elsewhere with
``baselines.llm_only.evaluate_against_truth_extended``) and from *reporting*
faithfulness (are the numbers in the final answer traceable to tool outputs).

Every function is pure and JSON-friendly; nothing here calls an LLM or a solver.

Definitions
-----------
formulation_exact
    The executed tool-call sequence equals ``intended_calls`` after normalizing
    argument names/types (``bus`` -> ``bus_id``, ``"14"`` -> ``14``, unordered
    line endpoints, defaults dropped) and ignoring benign ``run_powerflow``
    calls (repeats, or re-solves after a tool that already recomputed the flow).
formulation_error_type
    ``ok`` | ``wrong_id`` (bus / line / case identifier differs) |
    ``wrong_unit_or_value`` (a numeric/enum argument differs) | ``missed_step``
    (an intended tool was never executed or a different tool was used) |
    ``extra_step`` (an unintended, non-benign tool was executed) | ``unparsed``
    (the request could not be turned into any tool call).
faithful_numbers
    Fraction of the numbers in the final answer that match some number in the
    tool outputs within tolerance: 1e-3 p.u. for voltages, 1 % relative for MW,
    Mvar and percent values. Numbers without a unit are matched if either
    tolerance holds. Additionally, an answer number written with ``k`` decimals
    matches a tool value whose rounding to ``k`` decimals equals it (``0.93`` vs
    ``0.9312``), so a coarser quotation of a solver value is not penalized.
    Bare integers with no unit (bus/line ids, counts) are not
    counted. ``None`` when the answer carries no numbers.
n_untraceable_numbers
    Count of answer numbers that match no tool-output number.
safe_failure
    When the final solver state is non-converged (or the gate failed and there
    is no final state): did the answer say so rather than report a result.
claimed_success_on_failure
    Same failure condition, but the answer asserts success or reports
    unit-bearing numbers without acknowledging the failure.
stale_state
    The agent changed the network (``MUTATING_TOOLS``) and then reported
    power-flow numbers that do not come from a solve of the changed network.
    Computed from the trace only, over the tool calls in execution order; a
    ``load_case`` after a mutation resets the state (fresh network). Mutating
    calls that returned an ``error`` / ``need_confirmation`` payload did not
    change the network and are ignored. A "re-solve" is any tool output that
    carries a PowerFlowResult payload (``RESOLVING_TOOLS``; in PFAgent every
    mutating tool re-solves and returns the new result itself, so its own
    output counts as the re-solve).
    ``stale_state_no_rerun``: there is a mutation in effect, no re-solve at or
    after the last mutation, and the answer reports numbers (numbers merely
    echoing the request are ignored, as in ``faithful_numbers``).
    ``stale_state_quoted_old``: a re-solve did happen after the last mutation,
    but at least one answer number matches only a power-flow output produced
    *before* the mutation and none matches only the post-mutation output(s),
    with the ``faithful_numbers`` tolerances. Answers that quote both (a
    before/after comparison) are not stale.
    ``stale_state`` is either flag. All three are ``None`` when no mutation is
    in effect at answer time (n/a), so rates are over items with a mutation.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

FORMULATION_ERROR_TYPES: Tuple[str, ...] = (
    "ok",
    "wrong_id",
    "wrong_unit_or_value",
    "missed_step",
    "extra_step",
    "unparsed",
)

# Tools whose execution already re-solves the power flow (an explicit
# run_powerflow right after them is redundant but harmless).
RECOMPUTING_TOOLS: frozenset[str] = frozenset({"modify_load", "disconnect_line", "reconnect_line", "run_powerflow"})
# Read-only tools that never change the network state; extra calls are benign.
BENIGN_EXTRA_TOOLS: frozenset[str] = frozenset({"run_powerflow", "get_status"})
# Tools that change the network (stale_state); each also re-solves and returns the
# new PowerFlowResult (apply_remedial_action nests it under "result").
MUTATING_TOOLS: frozenset[str] = frozenset({"modify_load", "disconnect_line", "reconnect_line", "apply_remedial_action"})
# Tools whose successful output carries a PowerFlowResult, i.e. a solve of the current network.
RESOLVING_TOOLS: frozenset[str] = MUTATING_TOOLS | {"run_powerflow"}
ID_ARGS: frozenset[str] = frozenset({"bus_id", "from_bus", "to_bus", "case_name"})

VOLTAGE_ABS_TOL = 1e-3
RELATIVE_TOL = 0.01

# --------------------------------------------------------------------------- normalization

_ARG_ALIASES: Dict[str, str] = {
    "bus": "bus_id",
    "busid": "bus_id",
    "bus_number": "bus_id",
    "node": "bus_id",
    "from": "from_bus",
    "frombus": "from_bus",
    "bus_from": "from_bus",
    "to": "to_bus",
    "tobus": "to_bus",
    "bus_to": "to_bus",
    "p": "p_mw",
    "pmw": "p_mw",
    "mw": "p_mw",
    "active_power_mw": "p_mw",
    "load_mw": "p_mw",
    "q": "q_mvar",
    "qmvar": "q_mvar",
    "mvar": "q_mvar",
    "case": "case_name",
    "casename": "case_name",
    "name": "case_name",
    "topk": "top_k",
    "k": "top_k",
    "n": "top_k",
    "criterion": "criteria",
    "rank_by": "criteria",
}

_TOOL_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "run_n1_contingency": {"top_k": 5, "criteria": "max_violations", "max_candidates": 0},
    "recommend_remedial_actions": {
        "max_actions": 5,
        "allow_load_shed": True,
        "allow_voltage_control": True,
        "include_best_comparison": True,
    },
}


def _canonical_arg_name(name: str) -> str:
    key = str(name).strip().lower()
    compact = key.replace("-", "_").replace(" ", "_")
    if compact in _ARG_ALIASES:
        return _ARG_ALIASES[compact]
    squashed = compact.replace("_", "")
    return _ARG_ALIASES.get(squashed, compact)


def _to_int(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        s = value.strip().lower()
        m = re.fullmatch(r"(?:bus|node|line)?\s*#?\s*(\d+)(?:\.0+)?", s)
        if m:
            return int(m.group(1))
    return value


def _to_float(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 6)
    if isinstance(value, str):
        m = re.search(r"[-+]?\d+(?:[.,]\d+)?", value.replace(",", ""))
        if m:
            try:
                return round(float(m.group(0)), 6)
            except ValueError:
                return value
    return value


def _norm_case_name(value: Any) -> Any:
    if isinstance(value, str):
        m = re.search(r"(\d+)", value)
        if m and re.search(r"case|ieee|bus", value.lower()) or (m and value.strip().isdigit()):
            return f"case{int(m.group(1))}"
        return value.strip().lower()
    if isinstance(value, int) and not isinstance(value, bool):
        return f"case{value}"
    return value


def normalize_call(call: Dict[str, Any]) -> Dict[str, Any]:
    """Canonical form of one tool call: ``{"tool": str, "args": {...}}``.

    - argument names are mapped through aliases (``bus`` -> ``bus_id`` ...)
    - identifiers become ints, MW/Mvar values floats (rounded to 1e-6),
      case names ``caseNN``, enum strings lower-case
    - ``disconnect_line`` / ``reconnect_line`` endpoints are sorted (a branch
      has no orientation for these tools)
    - explicit default values of optional arguments are dropped, and ``None``
      values are removed
    """
    tool = str(call.get("tool") or call.get("name") or "").strip()
    raw_args = call.get("args")
    if raw_args is None:
        raw_args = call.get("arguments") or {}
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args or "{}")
        except Exception:
            raw_args = {}
    args: Dict[str, Any] = {}
    for key, value in dict(raw_args or {}).items():
        if value is None:
            continue
        name = _canonical_arg_name(key)
        if name in ("bus_id", "from_bus", "to_bus", "top_k", "max_candidates", "max_actions", "action_index"):
            value = _to_int(value)
        elif name in ("p_mw", "q_mvar"):
            value = _to_float(value)
        elif name == "case_name":
            value = _norm_case_name(value)
        elif isinstance(value, str):
            value = value.strip().lower()
        args[name] = value
    if tool in ("disconnect_line", "reconnect_line") and "from_bus" in args and "to_bus" in args:
        a, b = args["from_bus"], args["to_bus"]
        try:
            a, b = sorted((a, b))
        except TypeError:
            pass
        args["from_bus"], args["to_bus"] = a, b
    for key, default in _TOOL_DEFAULTS.get(tool, {}).items():
        if key in args and args[key] == default:
            del args[key]
    return {"tool": tool, "args": args}


def executed_calls_from_trace(trace: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ordered ``{"tool","args"}`` list from ``LLMEngine.run_with_trace`` output."""
    calls: List[Dict[str, Any]] = []
    for rnd in (trace or {}).get("rounds") or []:
        for tc in rnd.get("tools") or []:
            calls.append({"tool": tc.get("name"), "args": tc.get("arguments") or {}})
    return calls


def tool_outputs_from_trace(trace: Optional[Dict[str, Any]]) -> List[str]:
    """Raw tool-output strings recorded in the trace, in execution order."""
    out: List[str] = []
    for rnd in (trace or {}).get("rounds") or []:
        for tc in rnd.get("tools") or []:
            if tc.get("output") is not None:
                out.append(str(tc["output"]))
    return out


# --------------------------------------------------------------------------- formulation


def _strip_benign(calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop repeated / redundant run_powerflow and read-only get_status calls."""
    out: List[Dict[str, Any]] = []
    for c in calls:
        if c["tool"] == "get_status":
            continue
        if c["tool"] == "run_powerflow" and out and out[-1]["tool"] in RECOMPUTING_TOOLS:
            continue
        out.append(c)
    return out


def _has_solve_after_last_state_change(calls: List[Dict[str, Any]]) -> bool:
    solved = False
    for c in calls:
        if c["tool"] == "load_case":
            solved = False
        elif c["tool"] in RECOMPUTING_TOOLS:
            solved = True
    return solved


def _is_subsequence(short: Sequence[str], long: Sequence[str]) -> bool:
    it = iter(long)
    return all(any(x == y for y in it) for x in short)


def _classify_arg_mismatch(intended_args: Dict[str, Any], executed_args: Dict[str, Any]) -> str:
    keys = set(intended_args) | set(executed_args)
    differing = {k for k in keys if intended_args.get(k) != executed_args.get(k)}
    if differing & ID_ARGS:
        return "wrong_id"
    return "wrong_unit_or_value"


def formulation_check(
    intended_calls: Optional[Sequence[Dict[str, Any]]],
    executed_calls: Optional[Sequence[Dict[str, Any]]],
    *,
    preloaded_case: Optional[str] = None,
) -> Dict[str, Any]:
    """Compare executed tool calls with the request's ``intended_calls``.

    ``executed_calls=None`` means the request could not be parsed/planned at all
    (``unparsed``). ``preloaded_case`` marks methods that start with the case
    already loaded (single_call prompting); a leading ``load_case`` of that case
    is then optional on either side.

    Returns ``{"formulation_exact": bool, "formulation_error_type": str,
    "n_intended": int, "n_executed": int, "detail": str}``.
    """
    intended = [normalize_call(c) for c in (intended_calls or [])]
    if executed_calls is None:
        return {
            "formulation_exact": False,
            "formulation_error_type": "unparsed",
            "n_intended": len(intended),
            "n_executed": 0,
            "detail": "no tool calls could be formulated",
        }
    executed = [normalize_call(c) for c in executed_calls]
    n_executed = len(executed)

    if preloaded_case is not None:
        pre = normalize_call({"tool": "load_case", "args": {"case_name": preloaded_case}})
        if intended and intended[0] == pre:
            intended = intended[1:]
        if executed and executed[0] == pre:
            executed = executed[1:]

    # Benign run_powerflow handling: compare the "core" sequences (state-changing
    # and analysis tools) and check the solve requirement separately.
    intended_core = [c for c in _strip_benign(intended) if c["tool"] != "run_powerflow"]
    executed_core = [c for c in _strip_benign(executed) if c["tool"] != "run_powerflow"]
    intended_needs_solve = any(c["tool"] == "run_powerflow" for c in intended)

    def _result(exact: bool, err: str, detail: str) -> Dict[str, Any]:
        return {
            "formulation_exact": bool(exact),
            "formulation_error_type": err,
            "n_intended": len(intended),
            "n_executed": n_executed,
            "detail": detail,
        }

    i_tools = [c["tool"] for c in intended_core]
    e_tools = [c["tool"] for c in executed_core]

    if i_tools != e_tools:
        if len(e_tools) < len(i_tools) and _is_subsequence(e_tools, i_tools):
            missing = list(i_tools)
            for t in e_tools:
                missing.remove(t)
            return _result(False, "missed_step", f"missing tools: {missing}")
        if len(e_tools) > len(i_tools) and _is_subsequence(i_tools, e_tools):
            extra = list(e_tools)
            for t in i_tools:
                extra.remove(t)
            return _result(False, "extra_step", f"unintended tools: {extra}")
        return _result(False, "missed_step", f"tool sequence differs: intended={i_tools} executed={e_tools}")

    for ic, ec in zip(intended_core, executed_core):
        if ic["args"] != ec["args"]:
            err = _classify_arg_mismatch(ic["args"], ec["args"])
            return _result(False, err, f"{ic['tool']}: intended args {ic['args']} != executed {ec['args']}")

    if intended_needs_solve and not _has_solve_after_last_state_change(executed):
        if not (preloaded_case is not None and not executed and not intended_core):
            return _result(False, "missed_step", "intended run_powerflow never executed")

    return _result(True, "ok", "")


# --------------------------------------------------------------------------- numbers in text

_NUM_RE = re.compile(
    r"(?<![\w.])"  # not glued to a word or a decimal point
    r"(?P<num>[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[-+]?\d+(?:\.\d+)?)"
    r"(?P<unit>\s*(?:p\.?\s*u\.?|pu\b|%|percent\b|mw\b|mvar\b|mva\b|kv\b|deg(?:rees)?\b|°))?",
    flags=re.IGNORECASE,
)
_ID_PREFIX_RE = re.compile(
    r"(?:\b(?:bus|buses|node|line|lines|branch|branches|case|ieee|top|step|round|seed|id|no\.?|number|trafo|transformer|#)\s*[-#:]?\s*$)|"
    r"(?:\bn\s*-\s*$)|(?:case\s*$)",
    flags=re.IGNORECASE,
)
_ID_SUFFIX_RE = re.compile(r"^\s*(?:-\s*bus\b|bus\b|-\s*\d|–\s*\d|—\s*\d)", flags=re.IGNORECASE)


def _unit_kind(unit: Optional[str]) -> str:
    u = (unit or "").strip().lower().replace(" ", "")
    if not u:
        return "unknown"
    if u.startswith("p") and "u" in u:
        return "voltage"
    if u in ("%", "percent"):
        return "percent"
    if u in ("mw", "mvar", "mva", "kv"):
        return "mw"
    if u.startswith("deg") or u == "°":
        return "deg"
    return "unknown"


def numbers_in_text(text: Optional[str]) -> List[Dict[str, Any]]:
    """Numbers reported in an answer, each as ``{"value", "kind", "text", "decimals"}``.

    ``decimals`` is the number of digits written after the decimal point (the
    precision the answer quotes the value with; see ``_matches``). Bare integers
    with no unit are skipped (ids, counts, list numbering), as are numbers directly
    attached to id words (``bus 7``, ``line 4-5``, ``case14``, ``N-1``).
    """
    out: List[Dict[str, Any]] = []
    s = str(text or "")
    for m in _NUM_RE.finditer(s):
        raw = m.group("num")
        unit = m.group("unit")
        kind = _unit_kind(unit)
        before = s[max(0, m.start() - 16) : m.start()]
        after = s[m.end("num") : m.end("num") + 8]
        if _ID_PREFIX_RE.search(before) and kind == "unknown":
            continue
        if _ID_SUFFIX_RE.match(after) and kind == "unknown":
            continue
        if kind == "unknown" and "." not in raw:
            continue  # bare integer: id / count / numbering
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        decimals = len(raw.split(".", 1)[1]) if "." in raw else 0
        out.append({"value": value, "kind": kind, "text": m.group(0).strip(), "decimals": decimals})
    return out


def _walk_numbers(obj: Any, acc: List[float]) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        if math.isfinite(float(obj)):
            acc.append(float(obj))
        return
    if isinstance(obj, str):
        try:
            parsed = json.loads(obj)
        except Exception:
            return
        if isinstance(parsed, (dict, list)):
            _walk_numbers(parsed, acc)
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "figure_json":
                continue  # plotly figure payloads are not reported numbers
            _walk_numbers(v, acc)
        return
    if isinstance(obj, (list, tuple)):
        for v in obj:
            _walk_numbers(v, acc)


def numbers_in_tool_outputs(tool_outputs: Iterable[Any]) -> List[float]:
    """Every finite number appearing in the (JSON) tool outputs."""
    acc: List[float] = []
    for out in tool_outputs:
        if isinstance(out, str):
            try:
                obj = json.loads(out)
            except Exception:
                # non-JSON output: fall back to regex extraction
                for m in re.finditer(r"[-+]?\d+(?:\.\d+)?", out):
                    acc.append(float(m.group(0)))
                continue
        else:
            obj = out
        _walk_numbers(obj, acc)
    return acc


def _matches(value: float, kind: str, candidates: Sequence[float], decimals: Optional[int] = None) -> bool:
    """Does the answer number ``value`` match any tool-output candidate?

    Two alternative criteria: the kind-specific absolute/relative tolerance, or -
    when ``decimals`` (the precision the answer used) is given - equality after
    rounding the candidate to that many decimals, so ``0.93`` matches ``0.9312``.
    """
    for c in candidates:
        if decimals is not None and abs(round(c, int(decimals)) - value) <= 1e-9:
            return True
        abs_ok = abs(value - c) <= VOLTAGE_ABS_TOL
        rel_ok = abs(value - c) <= RELATIVE_TOL * max(abs(c), 1e-9) or (abs(c) < 1e-9 and abs(value) < 1e-9)
        if kind == "voltage" and abs_ok:
            return True
        if kind in ("mw", "percent", "deg") and (rel_ok or abs(value - c) <= 1e-6):
            return True
        if kind == "unknown" and (abs_ok or rel_ok):
            return True
    return False


def _num_matches(n: Dict[str, Any], candidates: Sequence[float]) -> bool:
    """``_matches`` for one ``numbers_in_text`` entry (uses its quoted precision)."""
    return _matches(n["value"], n["kind"], candidates, n.get("decimals"))


def _request_number_candidates(request_text: Optional[str]) -> List[float]:
    """Numbers that merely echo the request (thresholds, requested setpoints, ids)."""
    if not request_text:
        return []
    cands = [n["value"] for n in numbers_in_text(request_text)]
    cands.extend(float(m.group(0)) for m in re.finditer(r"\d+(?:\.\d+)?", str(request_text)))
    return cands


def faithful_numbers(
    answer_text: Optional[str],
    tool_outputs: Iterable[Any],
    *,
    request_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Fraction of answer numbers traceable to tool outputs (see module docstring).

    Numbers that merely echo the request (``request_text``, e.g. a threshold or a
    requested MW setpoint) are treated as traceable as well.
    """
    numbers = numbers_in_text(answer_text)
    candidates = numbers_in_tool_outputs(tool_outputs)
    candidates.extend(_request_number_candidates(request_text))
    if not numbers:
        return {"faithful_numbers": None, "n_numbers": 0, "n_untraceable_numbers": 0, "untraceable": []}
    untraceable = [n for n in numbers if not _num_matches(n, candidates)]
    return {
        "faithful_numbers": float((len(numbers) - len(untraceable)) / len(numbers)),
        "n_numbers": len(numbers),
        "n_untraceable_numbers": len(untraceable),
        "untraceable": [n["text"] for n in untraceable][:20],
    }


# --------------------------------------------------------------------------- failure reporting

_FAILURE_RE = re.compile(
    r"(?:\bnot\s+converge|\bnon-?\s*converge|\bno\s+convergence|\bdiverge|converged?\s*[:=]?\s*(?:false|no)\b|"
    r"\bisolat(?:ed|ion)?\b|\bisland(?:ed|ing)?\b|"
    r"\bfail(?:ed|ure|s)?\b|\bcould\s*not\b|\bcouldn'?t\b|\bcannot\b|\bcan'?t\b|\bunable\b|\bwithheld\b|"
    r"\bno\s+(?:verified\s+|valid\s+|numerical\s+)*(?:result|numbers?|solution)\b|\berror\b|"
    r"未收敛|不收敛|失败|无法|错误)",
    flags=re.IGNORECASE,
)
_SUCCESS_RE = re.compile(
    r"(?:\bconverged\b|\bsuccess(?:ful|fully)?\b|\bsolved\b|\bcompleted?\b|\bnormal(?:ly)?\b|\bhealthy\b|✅|"
    r"收敛|成功|完成|正常)",
    flags=re.IGNORECASE,
)


def failure_reporting(
    answer_text: Optional[str],
    *,
    final_converged: Optional[bool],
    gate_failed: int = 0,
) -> Dict[str, Any]:
    """``safe_failure`` / ``claimed_success_on_failure`` for one item.

    ``final_converged`` is the convergence flag of the final solver state
    (``None`` when no power flow was solved). Both metrics are ``None`` when the
    item is not a failure case.
    """
    is_failure = final_converged is False or (final_converged is None and int(gate_failed or 0) > 0)
    text = str(answer_text or "")
    said_failure = bool(_FAILURE_RE.search(text))
    claims_success = bool(_SUCCESS_RE.search(text)) and not said_failure
    reports_numbers = any(n["kind"] != "unknown" for n in numbers_in_text(text))
    if not is_failure:
        return {
            "is_failure": False,
            "safe_failure": None,
            "claimed_success_on_failure": None,
            "said_failure": said_failure,
        }
    return {
        "is_failure": True,
        "safe_failure": bool(said_failure),
        "claimed_success_on_failure": bool(not said_failure and (claims_success or reports_numbers)),
        "said_failure": said_failure,
    }


# --------------------------------------------------------------------------- stale state

_PF_NUMERIC_KEYS: Tuple[str, ...] = ("bus_voltages", "line_flows", "voltage_violations", "thermal_violations")
_PF_TOTAL_KEYS: Tuple[str, ...] = ("total_generation_mw", "total_load_mw", "total_loss_mw")
_PF_CONVERGED_RE = re.compile(r'"converged"\s*:\s*(true|false)', flags=re.IGNORECASE)
_ERROR_HEAD_RE = re.compile(r'\s*\{\s*"(?:error|need_confirmation)"')


def _tool_records_from_trace(trace: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flattened tool records (name, arguments, output, gate) in execution order.

    Indices into this list are the same as those of ``executed_calls_from_trace``.
    """
    recs: List[Dict[str, Any]] = []
    for rnd in (trace or {}).get("rounds") or []:
        for tc in rnd.get("tools") or []:
            recs.append(tc)
    return recs


def _parse_output(output: Any) -> Any:
    if isinstance(output, (dict, list)):
        return output
    if output is None:
        return None
    try:
        return json.loads(str(output))
    except Exception:
        return None


def _find_pf_payload(obj: Any) -> Optional[Dict[str, Any]]:
    """PowerFlowResult-shaped dict: top level, or nested under ``result`` (apply_remedial_action)."""
    if not isinstance(obj, dict):
        return None
    if "converged" in obj and any(k in obj for k in _PF_TOTAL_KEYS + _PF_NUMERIC_KEYS):
        return obj
    nested = obj.get("result")
    if isinstance(nested, dict) and "converged" in nested:
        return nested
    return None


def _is_resolve(record: Dict[str, Any]) -> bool:
    """Does this tool record carry a PowerFlowResult (a solve of the network as it then was)?

    Prefers the engine's gate verdict when recorded; otherwise inspects the
    output JSON, with a regex fallback for truncated payloads of RESOLVING_TOOLS.
    """
    gate = record.get("gate")
    if isinstance(gate, dict) and "converged" in gate:
        return True
    output = record.get("output")
    obj = _parse_output(output)
    if _find_pf_payload(obj) is not None:
        return True
    if obj is None and output is not None and str(record.get("name")) in RESOLVING_TOOLS:
        return bool(_PF_CONVERGED_RE.search(str(output)))
    return False


def _mutation_applied(record: Dict[str, Any]) -> bool:
    """A MUTATING_TOOLS call that actually changed the network.

    ``error`` (unknown bus/line, disabled in LLM-only mode, ...) and
    ``need_confirmation`` payloads are returned before the network is touched.
    """
    name = str(record.get("name") or "")
    if name not in MUTATING_TOOLS:
        return False
    output = record.get("output")
    obj = _parse_output(output)
    if isinstance(obj, dict):
        if obj.get("error") or obj.get("need_confirmation"):
            return False
        return True
    if obj is None and output is not None and _ERROR_HEAD_RE.match(str(output)):
        return False
    return True


def stale_state_check(
    trace: Optional[Dict[str, Any]],
    answer_text: Optional[str],
    *,
    request_text: Optional[str] = None,
) -> Dict[str, Any]:
    """``stale_state`` / ``stale_state_no_rerun`` / ``stale_state_quoted_old`` for one item.

    See the module docstring for the definition. Indices in the result refer to
    the flattened tool-call order (same as ``executed_calls_from_trace``).
    ``prior_result_indices`` are the power-flow outputs before the last mutation,
    ``resolve_indices_after`` those at/after it (the mutation's own result
    included when it carries one).
    """
    records = _tool_records_from_trace(trace)
    last_mut: Optional[int] = None
    n_mutations = 0
    for i, rec in enumerate(records):
        if str(rec.get("name") or "") == "load_case":
            last_mut = None  # fresh network: earlier mutations no longer matter
        elif _mutation_applied(rec):
            last_mut = i
            n_mutations += 1

    numbers = numbers_in_text(answer_text)
    echo = _request_number_candidates(request_text)
    if echo:
        numbers = [n for n in numbers if not _num_matches(n, echo)]

    out: Dict[str, Any] = {
        "has_mutation": last_mut is not None,
        "n_mutations": n_mutations,
        "stale_state": None,
        "stale_state_no_rerun": None,
        "stale_state_quoted_old": None,
        "last_mutation_index": last_mut,
        "last_mutation_tool": None,
        "last_mutation_args": None,
        "resolve_indices_after": [],
        "prior_result_indices": [],
        "n_answer_numbers": len(numbers),
        "n_numbers_old_only": 0,
        "n_numbers_new_only": 0,
        "old_only": [],
        "detail": "no network mutation in effect",
    }
    if last_mut is None:
        return out

    mut = records[last_mut]
    out["last_mutation_tool"] = mut.get("name")
    out["last_mutation_args"] = mut.get("arguments")
    resolves_after = [i for i in range(last_mut, len(records)) if _is_resolve(records[i])]
    prior = [i for i in range(last_mut) if _is_resolve(records[i])]
    out["resolve_indices_after"] = resolves_after
    out["prior_result_indices"] = prior

    if not resolves_after:
        no_rerun = bool(numbers)
        out.update(
            {
                "stale_state": no_rerun,
                "stale_state_no_rerun": no_rerun,
                "stale_state_quoted_old": False,
                "detail": (
                    f"{mut.get('name')} at call {last_mut} was never followed by a solve; answer reports {len(numbers)} number(s)"
                    if no_rerun
                    else f"{mut.get('name')} at call {last_mut} was never followed by a solve; answer reports no numbers"
                ),
            }
        )
        return out

    latest = numbers_in_tool_outputs([records[i].get("output") for i in resolves_after])
    old = numbers_in_tool_outputs([records[i].get("output") for i in prior])
    old_only = [n for n in numbers if _num_matches(n, old) and not _num_matches(n, latest)]
    new_only = [n for n in numbers if _num_matches(n, latest) and not _num_matches(n, old)]
    quoted_old = bool(old_only) and not new_only
    out.update(
        {
            "stale_state": quoted_old,
            "stale_state_no_rerun": False,
            "stale_state_quoted_old": quoted_old,
            "n_numbers_old_only": len(old_only),
            "n_numbers_new_only": len(new_only),
            "old_only": [n["text"] for n in old_only][:20],
            "detail": (
                f"answer quotes {len(old_only)} number(s) from pre-mutation output(s) {prior} "
                f"and none from post-mutation solve(s) {resolves_after}"
                if quoted_old
                else f"re-solved at {resolves_after} after {mut.get('name')} at call {last_mut}"
            ),
        }
    )
    return out


# --------------------------------------------------------------------------- cost


def cost_from_trace(trace: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Interaction-budget counters from an engine trace (zeros for LLM-free methods)."""
    t = trace or {}
    return {
        "n_llm_calls": int(t.get("n_llm_calls") or 0),
        "n_tool_calls": int(t.get("n_tool_calls") or 0),
        "n_tool_rounds": int(t.get("n_tool_rounds") or 0),
        "prompt_tokens": t.get("prompt_tokens"),
        "completion_tokens": t.get("completion_tokens"),
        "wall_time_s": t.get("wall_time_s"),
        "gate_checked": int(t.get("gate_checked") or 0),
        "gate_failed": int(t.get("gate_failed") or 0),
        "gate_enforced": int(t.get("gate_enforced") or 0),
    }


# --------------------------------------------------------------------------- aggregation helpers


def rate(values: Iterable[Any]) -> Dict[str, Any]:
    """``{"rate", "count", "total"}`` over boolean-like values, ignoring ``None``."""
    vals = [bool(v) for v in values if v is not None]
    total = len(vals)
    count = sum(1 for v in vals if v)
    return {"rate": (float(count) / total) if total else None, "count": count, "total": total}


def error_type_counts(values: Iterable[Optional[str]]) -> Dict[str, int]:
    counts = {k: 0 for k in FORMULATION_ERROR_TYPES}
    for v in values:
        if v is None:
            continue
        counts[v] = counts.get(v, 0) + 1
    return counts

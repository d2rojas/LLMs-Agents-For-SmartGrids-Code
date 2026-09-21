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
    The executed tool-call sequence asks the solver for what ``intended_calls``
    asks for (calibrated comparator, rules R0-R10 in ``formulation_check``):
    argument names/types are normalized (``bus`` -> ``bus_id``, ``"14"`` -> ``14``,
    unordered line endpoints, case aliases), read-only calls are ignored
    (``run_powerflow`` repeats, ``get_status``, ``get_most_loaded_branch``,
    ``generate_plot``), optional arguments the request does not pin accept any
    schema-valid value, and out-of-schema values or extra arguments that change
    the solver outcome are errors.
formulation_exact_strict
    The verdict of the original comparator (``formulation_check_strict``): the
    normalized sequences must match argument-by-argument with defaults dropped.
    Kept in the ``formulation_check`` result for before/after comparison.
formulation_error_type
    ``ok`` | ``wrong_id`` (bus / line / case identifier differs) |
    ``wrong_unit_or_value`` (a pinned numeric/enum argument differs) |
    ``invalid_value`` (a value the tool schema rejects, e.g. ``criteria="min
    voltage"``; the tool falls back to a default) | ``extra_arg_changes_result``
    (an unrequested optional argument that changes the solver outcome, e.g.
    ``modify_load(..., q_mvar=0)`` when only MW was asked) | ``missed_step``
    (an intended tool was never executed or a different tool was used) |
    ``extra_step`` (an unintended tool that mutates the network or runs an
    analysis was executed) | ``unparsed`` (the request could not be turned into
    any tool call).
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
    "invalid_value",
    "extra_arg_changes_result",
    "missed_step",
    "extra_step",
    "unparsed",
)

# Tools whose execution already re-solves the power flow (an explicit
# run_powerflow right after them is redundant but harmless).
RECOMPUTING_TOOLS: frozenset[str] = frozenset({"modify_load", "disconnect_line", "reconnect_line", "run_powerflow"})
# Read-only tools that never change the network state; extra calls are benign.
BENIGN_EXTRA_TOOLS: frozenset[str] = frozenset({"run_powerflow", "get_status", "get_most_loaded_branch", "generate_plot"})
# Read-only analysis tools that, unlike BENIGN_EXTRA_TOOLS, are only forgiven as a
# REPEAT of a call the request already intended -- a first-time, wholly unrequested
# occurrence is still a real extra_step (it has no backstop rule the way run_powerflow's
# absence is separately caught by R10's solve requirement; an unrequested N-1 analysis
# nobody asked for is still a formulation deviation worth flagging). Only excess
# occurrences beyond the count already in intended_calls are dropped -- see
# _drop_excess_repeats. 2026-09-21: PFAgent's verification-retry protocol re-runs its
# read-only analysis calls (blocked from mutating tools on retry) when checking its own
# answer again, which used to cost a formulation point for doing exactly what the gate
# is supposed to do.
REPEATABLE_ANALYSIS_TOOLS: frozenset[str] = frozenset({"run_n1_contingency"})
# Tools that change the network (stale_state); each also re-solves and returns the
# new PowerFlowResult (apply_remedial_action nests it under "result").
MUTATING_TOOLS: frozenset[str] = frozenset({"modify_load", "disconnect_line", "reconnect_line", "apply_remedial_action"})
# Tools whose successful output carries a PowerFlowResult, i.e. a solve of the current network.
RESOLVING_TOOLS: frozenset[str] = MUTATING_TOOLS | {"run_powerflow"}
ID_ARGS: frozenset[str] = frozenset({"bus_id", "from_bus", "to_bus", "case_name"})

# Mirror of ``llm.tools.TOOLS`` (kept here so this module stays import-light; a
# test asserts the two agree). ``minimum`` encodes what the dispatcher does with
# the value: ``int(top_k or 5)`` makes 0 fall back to the default, so a positive
# integer is the only value that means what the caller wrote.
TOOL_SCHEMA: Dict[str, Dict[str, Any]] = {
    "load_case": {
        "properties": {"case_name": {"type": "string", "enum": ["case14", "case30", "case57", "case118", "case300"]}},
        "required": ["case_name"],
    },
    "run_powerflow": {"properties": {}, "required": []},
    "modify_load": {
        "properties": {"bus_id": {"type": "integer"}, "p_mw": {"type": "number"}, "q_mvar": {"type": "number"}},
        "required": ["bus_id", "p_mw"],
    },
    "disconnect_line": {"properties": {"from_bus": {"type": "integer"}, "to_bus": {"type": "integer"}}, "required": ["from_bus", "to_bus"]},
    "reconnect_line": {"properties": {"from_bus": {"type": "integer"}, "to_bus": {"type": "integer"}}, "required": ["from_bus", "to_bus"]},
    "get_most_loaded_branch": {"properties": {}, "required": []},
    "run_n1_contingency": {
        "properties": {
            "top_k": {"type": "integer", "default": 5, "minimum": 1},
            "criteria": {"type": "string", "enum": ["max_violations", "max_overload", "min_voltage"], "default": "max_violations"},
            "max_candidates": {"type": "integer", "default": 0, "minimum": 0},
        },
        "required": [],
    },
    "recommend_remedial_actions": {
        "properties": {
            "max_actions": {"type": "integer", "default": 5, "minimum": 1},
            "allow_load_shed": {"type": "boolean", "default": True},
            "allow_voltage_control": {"type": "boolean", "default": True},
            "include_best_comparison": {"type": "boolean", "default": True},
        },
        "required": [],
    },
    "apply_remedial_action": {
        "properties": {"action_index": {"type": "integer"}, "confirmed": {"type": "boolean", "default": False}},
        "required": ["action_index"],
    },
    "get_status": {"properties": {}, "required": []},
    "generate_plot": {
        "properties": {"plot_type": {"type": "string", "enum": ["voltage_heatmap", "flow_diagram", "violation_overview", "comparison"]}},
        "required": ["plot_type"],
    },
}
# Optional arguments whose presence alone changes the solver outcome (the
# dispatcher writes them into the network): giving them unasked is an error.
RESULT_CHANGING_OPTIONAL_ARGS: frozenset[Tuple[str, str]] = frozenset({("modify_load", "q_mvar")})

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
    """Canonical ``caseNN`` for every alias the dispatcher accepts.

    ``load_case`` runs ``solver.case_loader.normalize_case_name`` on its argument, so
    ``"IEEE 30-bus system"``, ``"case 30"``, ``"IEEE30"`` and ``30`` are all the same
    case; the loader is imported lazily (pandapower) with a regex fallback.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        value = f"case{value}"
    if not isinstance(value, str):
        return value
    try:
        from solver.case_loader import normalize_case_name  # noqa: WPS433 (lazy: pulls pandapower)

        return normalize_case_name(value)
    except Exception:
        m = re.search(r"(\d+)", value)
        if m and re.search(r"case|ieee|bus", value.lower()) or (m and value.strip().isdigit()):
            return f"case{int(m.group(1))}"
        return value.strip().lower()


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
    tool = _tool_name(call)
    return {"tool": tool, "args": _canonical_args(tool, _raw_args(call), drop_defaults=True, lower_enums=True)}


# set_active_load/set_load (llm.tools.TOOLS_LOAD_SPLIT, tool_variant="load_split") are the
# same underlying action as modify_load with a narrower schema (no invented q_mvar) --
# intended_calls always says "modify_load" since the ground-truth generator predates the
# split and never emits the new names, so without this alias every load-split run's
# formulation would look like a "wrong tool" mismatch regardless of whether the arguments
# (which are otherwise identical -- requests.py's modify_load intended calls never include
# q_mvar) were right.
_TOOL_NAME_ALIASES = {"set_active_load": "modify_load", "set_load": "modify_load"}


def _tool_name(call: Dict[str, Any]) -> str:
    name = str(call.get("tool") or call.get("name") or "").strip()
    return _TOOL_NAME_ALIASES.get(name, name)


def _raw_args(call: Dict[str, Any]) -> Dict[str, Any]:
    raw_args = call.get("args")
    if raw_args is None:
        raw_args = call.get("arguments") or {}
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args or "{}")
        except Exception:
            raw_args = {}
    return dict(raw_args or {})


def _canonical_args(tool: str, raw_args: Dict[str, Any], *, drop_defaults: bool, lower_enums: bool) -> Dict[str, Any]:
    """Canonical argument dict shared by the strict and the calibrated comparator.

    ``drop_defaults`` removes explicit tool defaults (strict comparator);
    ``lower_enums`` lower-cases free strings (strict) - the calibrated comparator
    keeps them verbatim because the dispatcher compares enum strings exactly.
    """
    args: Dict[str, Any] = {}
    for key, value in raw_args.items():
        if value is None:
            continue
        name = _canonical_arg_name(key)
        if name in ("bus_id", "from_bus", "to_bus", "top_k", "max_candidates", "max_actions", "action_index"):
            value = _to_int(value)
        elif name in ("p_mw", "q_mvar"):
            value = _to_float(value)
        elif name == "case_name":
            value = _norm_case_name(value)
        elif isinstance(value, str) and lower_enums:
            value = value.strip().lower()
        args[name] = value
    if tool in ("disconnect_line", "reconnect_line") and "from_bus" in args and "to_bus" in args:
        a, b = args["from_bus"], args["to_bus"]
        try:
            a, b = sorted((a, b))
        except TypeError:
            pass
        args["from_bus"], args["to_bus"] = a, b
    if drop_defaults:
        for key, default in _TOOL_DEFAULTS.get(tool, {}).items():
            if key in args and args[key] == default:
                del args[key]
    return args


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
    """Drop repeated / redundant run_powerflow and read-only get_status calls (strict comparator)."""
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


def _sequence_mismatch(i_tools: List[str], e_tools: List[str]) -> Tuple[str, str]:
    """(error_type, detail) for two differing core tool sequences."""
    if len(e_tools) < len(i_tools) and _is_subsequence(e_tools, i_tools):
        missing = list(i_tools)
        for t in e_tools:
            missing.remove(t)
        return "missed_step", f"missing tools: {missing}"
    if len(e_tools) > len(i_tools) and _is_subsequence(i_tools, e_tools):
        extra = list(e_tools)
        for t in i_tools:
            extra.remove(t)
        return "extra_step", f"unintended tools: {extra}"
    return "missed_step", f"tool sequence differs: intended={i_tools} executed={e_tools}"


def formulation_check_strict(
    intended_calls: Optional[Sequence[Dict[str, Any]]],
    executed_calls: Optional[Sequence[Dict[str, Any]]],
    *,
    preloaded_case: Optional[str] = None,
) -> Dict[str, Any]:
    """The original (pre-calibration) comparator, kept verbatim for comparison.

    Executed and intended calls are normalized with ``normalize_call`` (explicit
    defaults dropped, enum strings lower-cased) and must then match argument-by-
    argument. Consequences that the calibrated ``formulation_check`` removes:
    ``run_n1_contingency(top_k=1)`` against an intended call with no arguments is
    ``wrong_unit_or_value``; any extra optional argument is a mismatch;
    ``get_most_loaded_branch`` / ``generate_plot`` are ``extra_step``; out-of-enum
    values are folded into ``wrong_unit_or_value``.
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
        err, detail = _sequence_mismatch(i_tools, e_tools)
        return _result(False, err, detail)

    for ic, ec in zip(intended_core, executed_core):
        if ic["args"] != ec["args"]:
            err = _classify_arg_mismatch(ic["args"], ec["args"])
            return _result(False, err, f"{ic['tool']}: intended args {ic['args']} != executed {ec['args']}")

    if intended_needs_solve and not _has_solve_after_last_state_change(executed):
        if not (preloaded_case is not None and not executed and not intended_core):
            return _result(False, "missed_step", "intended run_powerflow never executed")

    return _result(True, "ok", "")


def formulation_exact_strict(
    intended_calls: Optional[Sequence[Dict[str, Any]]],
    executed_calls: Optional[Sequence[Dict[str, Any]]],
    *,
    preloaded_case: Optional[str] = None,
) -> bool:
    """Boolean verdict of the original strict comparator (see ``formulation_check_strict``)."""
    return bool(formulation_check_strict(intended_calls, executed_calls, preloaded_case=preloaded_case)["formulation_exact"])


# ---- calibrated comparator -------------------------------------------------

_ERROR_SEVERITY: Dict[str, int] = {
    "invalid_value": 0,
    "wrong_id": 1,
    "wrong_unit_or_value": 2,
    "extra_arg_changes_result": 3,
}


def _calibrated_args(tool: str, raw_args: Any) -> Dict[str, Any]:
    """Canonical argument names and dispatcher-equivalent values, **without** dropping
    explicit defaults or lower-casing enums (the dispatcher compares enum strings verbatim)."""
    return _canonical_args(tool, raw_args, drop_defaults=False, lower_enums=False)


def _valid_for_schema(tool: str, name: str, value: Any) -> Tuple[bool, str]:
    """(is_valid, reason) of one *executed* argument value against ``TOOL_SCHEMA``."""
    spec = TOOL_SCHEMA.get(tool, {}).get("properties", {}).get(name)
    if spec is None:
        return True, "not in schema (ignored by the dispatcher)"
    kind = spec.get("type")
    if "enum" in spec:
        if not isinstance(value, str) or value not in spec["enum"]:
            return False, f"{value!r} not in {spec['enum']} (tool falls back to its default)"
        return True, ""
    if kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return False, f"{value!r} is not an integer"
        lo = spec.get("minimum")
        if lo is not None and value < lo:
            return False, f"{value!r} below minimum {lo}"
        return True, ""
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False, f"{value!r} is not a number"
        return True, ""
    return True, ""


def _final_state_identical(final_state_metrics: Optional[Dict[str, Any]]) -> bool:
    """Rule 4 evidence: the method's final power-flow state equals the ground truth."""
    if not isinstance(final_state_metrics, dict):
        return False
    vm, fm = final_state_metrics.get("voltage_mae"), final_state_metrics.get("flow_mae")
    try:
        return vm is not None and fm is not None and abs(float(vm)) < 1e-6 and abs(float(fm)) < 1e-6
    except (TypeError, ValueError):
        return False


def _compare_call_args(
    tool: str,
    intended_args: Dict[str, Any],
    executed_args: Dict[str, Any],
    *,
    final_state_metrics: Optional[Dict[str, Any]],
) -> Tuple[Optional[str], str, List[str]]:
    """(error_type | None, detail, benign_notes) for one intended/executed pair of the same tool.

    ``intended_args`` are the *raw* intended arguments (canonical names, defaults kept):
    a key present there is *pinned* by the request.
    """
    schema = TOOL_SCHEMA.get(tool, {})
    props: Dict[str, Any] = schema.get("properties", {})
    required = set(schema.get("required", ()))
    issues: List[Tuple[str, str]] = []
    benign: List[str] = []

    for name in sorted(required):
        if name not in executed_args and name not in intended_args:
            issues.append(("invalid_value", f"{tool}: required argument {name!r} missing"))

    for name in sorted(set(intended_args) | set(executed_args)):
        i_has, e_has = name in intended_args, name in executed_args
        e_val = executed_args.get(name)
        if e_has:
            ok, why = _valid_for_schema(tool, name, e_val)
            if not ok:
                issues.append(("invalid_value", f"{tool}: {name}={why}"))
                continue
        if i_has:
            i_val = intended_args[name]
            if not e_has:
                if name in props and "default" in props[name]:
                    e_val = props[name]["default"]
                else:
                    issues.append(("invalid_value" if name in required else "wrong_unit_or_value", f"{tool}: pinned argument {name}={i_val!r} not given"))
                    continue
            if _values_equal(i_val, e_val):
                continue
            err = "wrong_id" if name in ID_ARGS else "wrong_unit_or_value"
            issues.append((err, f"{tool}: {name} intended {i_val!r} != executed {e_val!r}"))
            continue
        # executed-only argument (not pinned by the request)
        if name not in props:
            benign.append(f"{tool}: {name}={e_val!r} not in schema, ignored by the dispatcher")
            continue
        if (tool, name) in RESULT_CHANGING_OPTIONAL_ARGS:
            default = props[name].get("default")
            if default is not None and _values_equal(default, e_val):
                benign.append(f"{tool}: {name}={e_val!r} equals the tool default")
                continue
            if _final_state_identical(final_state_metrics):
                benign.append(f"{tool}: extra {name}={e_val!r} left the final state identical to the ground truth")
                continue
            issues.append(("extra_arg_changes_result", f"{tool}: extra argument {name}={e_val!r} changes the solver outcome (request did not ask for it)"))
            continue
        benign.append(f"{tool}: optional {name}={e_val!r} accepted (unpinned, valid for the schema)")

    if not issues:
        return None, "", benign
    issues.sort(key=lambda t: _ERROR_SEVERITY.get(t[0], 9))
    err = issues[0][0]
    return err, "; ".join(d for _, d in issues), benign


def _values_equal(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) == bool(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-6)
    return a == b


def _strip_benign_calibrated(calls: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Core sequence for the calibrated comparator plus notes on what was ignored.

    Removes every ``run_powerflow`` (the solve requirement is checked separately),
    every read-only tool in ``BENIGN_EXTRA_TOOLS``, and a ``load_case`` that
    re-loads the case already in effect before any mutation (idempotent).
    """
    out: List[Dict[str, Any]] = []
    notes: List[str] = []
    loaded: Optional[Any] = None
    mutated = False
    for c in calls:
        tool = c["tool"]
        if tool == "run_powerflow":
            continue
        if tool in BENIGN_EXTRA_TOOLS:
            notes.append(f"read-only {tool} ignored")
            continue
        if tool == "load_case":
            case = c["args"].get("case_name")
            if loaded is not None and case == loaded and not mutated:
                notes.append(f"repeated load_case({case}) before any mutation ignored")
                continue
            loaded, mutated = case, False
        elif tool in MUTATING_TOOLS:
            mutated = True
        out.append(c)
    return out, notes


def _drop_excess_repeats(
    executed_core: List[Dict[str, Any]], intended_core: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Drop REPEATABLE_ANALYSIS_TOOLS occurrences in ``executed_core`` beyond how many
    times ``intended_core`` already calls for that tool -- see REPEATABLE_ANALYSIS_TOOLS'
    own comment for why this is a repeat-count rule rather than BENIGN_EXTRA_TOOLS'
    unconditional strip. The cap is at least 1 even when the tool is absent from
    ``intended_core``, so a wholly unrequested call still shows up once for R3's
    sequence match (a real deviation, still flagged) rather than being erased outright;
    only genuine repeats collapse."""
    allowed: Dict[str, int] = {}
    for c in intended_core:
        if c["tool"] in REPEATABLE_ANALYSIS_TOOLS:
            allowed[c["tool"]] = allowed.get(c["tool"], 0) + 1
    seen: Dict[str, int] = {}
    out: List[Dict[str, Any]] = []
    notes: List[str] = []
    for c in executed_core:
        tool = c["tool"]
        if tool in REPEATABLE_ANALYSIS_TOOLS:
            seen[tool] = seen.get(tool, 0) + 1
            cap = max(allowed.get(tool, 0), 1)  # an unrequested call still gets its first occurrence kept
            if seen[tool] > cap:
                notes.append(f"repeated read-only {tool} beyond the intended count ignored")
                continue
        out.append(c)
    return out, notes


def formulation_check(
    intended_calls: Optional[Sequence[Dict[str, Any]]],
    executed_calls: Optional[Sequence[Dict[str, Any]]],
    *,
    preloaded_case: Optional[str] = None,
    final_state_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Calibrated comparison of executed tool calls with the request's ``intended_calls``.

    The comparator answers "did the method ask the solver for what the request
    asked for", not "did it type the reference call verbatim". Rules, in the
    order they are applied:

    R0  ``executed_calls=None`` -> ``unparsed`` (nothing could be formulated).
    R1  ``preloaded_case``: a leading ``load_case`` of that case is optional on
        either side (single_call prompting starts with the case loaded).
    R2  Read-only / idempotent calls are ignored wherever they occur:
        ``run_powerflow`` (any number of repeats; the *solve requirement* of an
        intended ``run_powerflow`` is checked separately, R10), ``get_status``,
        ``get_most_loaded_branch``, ``generate_plot`` (``BENIGN_EXTRA_TOOLS``), and a
        ``load_case`` that re-loads the case already loaded before any mutation.
    R2b Read-only *analysis* calls (``REPEATABLE_ANALYSIS_TOOLS``, currently
        ``run_n1_contingency``) are not unconditionally ignored like R2 -- only
        occurrences beyond how many times the request already intends that tool are
        dropped, so a repeat (e.g. PFAgent's verification retry re-checking its own
        answer with a read-only call it already made once) is benign but a wholly
        unrequested occurrence still surfaces to R3, once, as a real deviation.
    R3  Remaining tool sequences must match in order. Missing intended tools, or a
        different tool in place of the intended one -> ``missed_step``; unintended
        tools that survive R2 (every mutating or analysis tool: ``modify_load``,
        ``disconnect_line``, ``reconnect_line``, ``apply_remedial_action``,
        ``run_n1_contingency``, ``recommend_remedial_actions``, a ``load_case`` that
        resets the network) -> ``extra_step``.
    R4  Identifier normalization before comparing: argument aliases (``bus`` ->
        ``bus_id``), ints given as floats/strings (``"14"``, ``14.0``, ``"bus 14"``),
        MW/Mvar given as strings with units, line endpoints in either order for
        ``disconnect_line`` / ``reconnect_line``, case aliases through
        ``solver.case_loader.normalize_case_name`` (``"IEEE 30-bus system"`` ==
        ``"case30"``). Only equivalences the dispatcher itself accepts are applied;
        enum strings are compared verbatim (``criteria="MIN_VOLTAGE"`` is *not*
        ``"min_voltage"`` because ``solver.contingency`` compares exact strings).
    R5  An argument is *pinned* when the intended call names it (the request text
        gave a number or a named criterion: ``op_n1(explicit=True)``, ``modify_load``
        with ``q_mvar`` in stress items). Pinned arguments must match after R4; an
        omitted pinned argument is compared through the tool default. Mismatch ->
        ``wrong_id`` for ``bus_id`` / ``from_bus`` / ``to_bus`` / ``case_name``, else
        ``wrong_unit_or_value``.
    R6  An optional argument the intended call leaves unspecified accepts ANY value
        that is valid for the tool schema (``run_n1_contingency(top_k=1)`` for
        "report the worst single outage"; ``max_candidates=10``; explicit defaults).
    R7  A value outside the schema -> ``invalid_value``: enum strings not in the
        enum (``criteria="min voltage"``, ``"worst"``, ``"MIN_VOLTAGE"``: the tool
        silently falls back to its default and the ranking changes), non-integer
        ``top_k`` / ids, ``top_k < 1``, a missing required argument. Checked for
        pinned and unpinned arguments alike; it outranks R5/R8 within a call.
    R8  An executed-only argument that changes the solver outcome although the
        request did not ask for it -> ``extra_arg_changes_result``
        (``RESULT_CHANGING_OPTIONAL_ARGS``: ``modify_load.q_mvar`` — the dispatcher
        overwrites the reactive load; ``None`` and the tool default are exempt).
        Evidence override: when ``final_state_metrics`` (the row's ``metrics``
        with ``voltage_mae`` / ``flow_mae`` vs the ground truth) shows a final
        state numerically identical to the ground truth, the extra argument did
        not change the outcome and is benign. ``benchmarks/rescore.py`` does not
        currently pass it, so offline rescoring applies the schema rule alone.
    R9  Executed-only argument names unknown to the schema are ignored (the
        dispatcher never reads them).
    R10 An intended ``run_powerflow`` requires that some solve (``run_powerflow`` or
        a tool that re-solves: ``RECOMPUTING_TOOLS``) happened after the last
        ``load_case``; otherwise ``missed_step``.
    Within one call the reported type is the most severe issue:
    ``invalid_value`` > ``wrong_id`` > ``wrong_unit_or_value`` >
    ``extra_arg_changes_result``; across calls the first offending call wins.

    Returns ``{"formulation_exact", "formulation_error_type", "n_intended",
    "n_executed", "detail", "benign_notes", "formulation_exact_strict",
    "formulation_error_type_strict"}``; the ``*_strict`` fields are the verdict of
    the original comparator (``formulation_check_strict``) on the same calls.
    """
    strict = formulation_check_strict(intended_calls, executed_calls, preloaded_case=preloaded_case)
    strict_fields = {
        "formulation_exact_strict": strict["formulation_exact"],
        "formulation_error_type_strict": strict["formulation_error_type"],
    }
    intended_raw = [
        {"tool": _tool_name(c), "args": _calibrated_args(_tool_name(c), _raw_args(c))} for c in (intended_calls or [])
    ]
    if executed_calls is None:
        return {
            "formulation_exact": False,
            "formulation_error_type": "unparsed",
            "n_intended": len(intended_raw),
            "n_executed": 0,
            "detail": "no tool calls could be formulated",
            "benign_notes": [],
            **strict_fields,
        }
    executed_raw = [{"tool": _tool_name(c), "args": _calibrated_args(_tool_name(c), _raw_args(c))} for c in executed_calls]
    n_executed = len(executed_raw)

    if preloaded_case is not None:
        pre = _norm_case_name(preloaded_case)
        if intended_raw and intended_raw[0]["tool"] == "load_case" and intended_raw[0]["args"].get("case_name") == pre:
            intended_raw = intended_raw[1:]
        if executed_raw and executed_raw[0]["tool"] == "load_case" and executed_raw[0]["args"].get("case_name") == pre:
            executed_raw = executed_raw[1:]

    intended_core, _ = _strip_benign_calibrated(intended_raw)
    executed_core, benign_notes = _strip_benign_calibrated(executed_raw)
    executed_core, repeat_notes = _drop_excess_repeats(executed_core, intended_core)
    benign_notes = benign_notes + repeat_notes
    intended_needs_solve = any(c["tool"] == "run_powerflow" for c in intended_raw)

    def _result(exact: bool, err: str, detail: str) -> Dict[str, Any]:
        return {
            "formulation_exact": bool(exact),
            "formulation_error_type": err,
            "n_intended": len(intended_raw),
            "n_executed": n_executed,
            "detail": detail,
            "benign_notes": list(benign_notes),
            **strict_fields,
        }

    i_tools = [c["tool"] for c in intended_core]
    e_tools = [c["tool"] for c in executed_core]
    if i_tools != e_tools:
        err, detail = _sequence_mismatch(i_tools, e_tools)
        return _result(False, err, detail)

    for ic, ec in zip(intended_core, executed_core):
        err, detail, notes = _compare_call_args(ic["tool"], ic["args"], ec["args"], final_state_metrics=final_state_metrics)
        benign_notes.extend(notes)
        if err is not None:
            return _result(False, err, detail)

    if intended_needs_solve and not _has_solve_after_last_state_change(executed_raw):
        if not (preloaded_case is not None and not executed_raw and not intended_core):
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
    """Every finite number appearing in the (JSON) tool outputs.

    TODO(open method decision, 2026-09-16): unlike ``numbers_in_text``, this walks bus/line
    ids (``bus_id``, ``from_bus``, ...) into the candidate pool along with real physical
    quantities. A stale value can coincidentally fall within a small id's tolerance band
    (observed: a stale "14.05 MW" matched case14's ``bus_id: 14`` in both the pre- and
    post-mutation outputs, at 1% relative tolerance, and was excluded from
    ``stale_state_check``'s ``old_only`` as a result even though it was a genuinely stale
    number). Excluding bare-integer ids here the way ``numbers_in_text`` already does would
    change ``faithful_numbers`` / ``stale_state_check`` results project-wide, not just for
    this one item; flagging for Daniela/PI rather than changing unilaterally.
    """
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


_BUS_LIKE_ARGS: frozenset[str] = frozenset({"bus_id", "from_bus", "to_bus"})
_REQUEST_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


_INDEXING_CONVENTION_RE = re.compile(r"\(\s*[01]\s*-\s*based\s*\)", re.IGNORECASE)


def _word_numbers_from_text(text: str) -> set[float]:
    """Spelled-out bus numbers ("bus ten and bus eleven") the digit regex alone
    misses -- reuses baselines.rule_based's own word list (its bus-number parser
    covers the same generated-request phrasings) rather than a second one to keep
    in sync."""
    from baselines.rule_based import _NUMBER_WORDS

    found: set[float] = set()
    for word in re.findall(r"[a-zA-Z]+", text):
        v = _NUMBER_WORDS.get(word.lower())
        if v is not None:
            found.add(float(v))
    return found


def _numbers_from_text(text: Optional[str]) -> set[float]:
    """Every number literal in ``text`` (request or prior tool output rendered as
    text), permissive on purpose -- unlike ``numbers_in_text`` (built for the
    *answer*, where a bare integer is usually an id/count to ignore), V6 needs bus
    ids and other bare integers from the *request* to count as grounding, not just
    unit-bearing values. A ``(0-based)``/``(1-based)`` indexing-convention marker is
    stripped first: the "0" or "1" there names a convention, not a requested value,
    and otherwise grounds an unrelated argument that happens to equal 0 or 1 (a
    default reactive power, say) as if the request had stated it. Spelled-out bus
    numbers ("bus ten") are also picked up, not just digits.
    """
    cleaned = _INDEXING_CONVENTION_RE.sub(" ", str(text or ""))
    return {float(m) for m in _REQUEST_NUMBER_RE.findall(cleaned)} | _word_numbers_from_text(cleaned)


def _numbers_from_json(obj: Any) -> set[float]:
    """Every numeric leaf in a JSON-like structure (a parsed tool output)."""
    found: set[float] = set()

    def _walk(o: Any) -> None:
        if isinstance(o, bool):
            return
        if isinstance(o, (int, float)):
            found.add(float(o))
        elif isinstance(o, dict):
            for v in o.values():
                _walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                _walk(v)

    _walk(obj)
    return found


def argument_grounding_check(trace: Optional[Dict[str, Any]], request_text: Optional[str]) -> Dict[str, Any]:
    """V6: every numeric or identifier argument passed to a MUTATING tool must appear
    in the user request or in the output of a tool call that already ran -- never a
    value the model introduced on its own (e.g. an unrequested ``q_mvar``, an
    unrequested bus, an invented N-1 ``criteria``). Closes the reactive-argument-
    invention class under either tool set (the request's numbers ground
    ``set_active_load``/``set_load`` exactly as they ground ``modify_load``) and,
    unlike the tool-split redesign, catches unrequested bus/line ids and invented
    N-1 criteria too, since those are not eliminated by construction the way an
    extra ``q_mvar`` argument is.

    Returns ``{"passed", "invented_args": [{"tool", "arg", "value"}, ...], "detail"}``.
    A bus-like argument (``bus_id``/``from_bus``/``to_bus``) also grounds against its
    zero-based-to-one-based neighbor (n-1 or n+1), so a request that states its bus
    reference in the 0-based convention (``"bus 10 (0-based)"``, converted to the
    MATPOWER 1-based id before the tool call -- see llm/prompts.py) is not flagged
    for a conversion the request itself asked for.
    """
    records = _tool_records_from_trace(trace)
    request_nums = _numbers_from_text(request_text)
    seen_output_nums: set[float] = set(request_nums)
    invented: List[Dict[str, Any]] = []

    for rec in records:
        name = str(rec.get("name") or "")
        canonical = _TOOL_NAME_ALIASES.get(name, name)
        if canonical in MUTATING_TOOLS or name in ("set_active_load", "set_load"):
            args = rec.get("arguments") or {}
            if isinstance(args, str):
                args = _safe_json_loads(args)
            for key, value in (args or {}).items():
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                fv = float(value)
                grounded = fv in seen_output_nums
                if not grounded and key in _BUS_LIKE_ARGS:
                    grounded = (fv - 1) in seen_output_nums or (fv + 1) in seen_output_nums
                if not grounded:
                    invented.append({"tool": name, "arg": key, "value": value})

        # This call's own output grounds every later call, so a value the request
        # never stated but a prior tool reported (e.g. a bus id read off get_status)
        # is not penalized. load_case's own output is excluded: it is a bulk network-
        # metadata dump (n_buses, n_generators, n_lines, total_load_mw, ...), not
        # something a reasoning agent repurposes as a load's reactive power, and its
        # small integers (a generator count of 5, a line count of 20) otherwise
        # coincidentally ground an unrelated invented value.
        if name != "load_case":
            seen_output_nums |= _numbers_from_json(_parse_output(rec.get("output")))

    detail = (
        "; ".join(f"{i['tool']}.{i['arg']}={i['value']}" for i in invented)
        if invented
        else "every mutating-tool argument traces to the request or a prior tool output"
    )
    return {"passed": not invented, "invented_args": invented, "detail": detail}


def _safe_json_loads(text: Any) -> Optional[Dict[str, Any]]:
    if isinstance(text, dict):
        return text
    try:
        obj = json.loads(str(text))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


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

"""End-to-end item scoring: ``solved`` and JSON-aware failure reporting.

``benchmarks/metrics.py`` scores *parts* of an item (formulation, faithfulness,
stale state, text-based failure reporting). This module combines the stored
per-item fields into the headline verdicts that the paper table reports, and
fixes two measurement problems observed on real output:

* ``success_rate`` (``ok``) only means "the run completed and the answer
  parsed". An LLM-only model that returns ``{"converged": false, "bus_voltages":
  [] ...}`` on every request is ``ok`` but has solved nothing.
* The regex-based ``safe_failure`` / ``claimed_success_on_failure`` in
  ``metrics.failure_reporting`` do not see ``"converged": false`` inside a JSON
  answer and count its ``0.0`` placeholder totals as reported numbers, so an
  explicitly abstaining model is scored as "claimed success".

Everything here is pure: no LLM, no solver, JSON-friendly in and out. Functions
from ``metrics.py`` are only *used*, never changed.

Definitions
-----------
solved
    The request was answered correctly end to end. Per item::

        solved = ok
                 AND (formulation_exact is True            -- methods with tools
                      | reported convergence matches truth  -- methods without tools)
                 AND final_converged == truth_converged
                 AND (truth non-converged                   -- correctly identified failure
                      | numeric_ok | answer_ok)

    ``numeric_ok`` (both converged): ``voltage_mae <= 1e-3`` p.u. over a complete
    bus coverage (every ground-truth bus reported) and, for methods with tools,
    ``flow_mae <= 1 %`` of the largest ground-truth branch flow (taken from
    ``metrics["_raw_p_pairs"]``; skipped when unavailable). For LLM-only
    methods only the voltage criterion applies, as the paper states.
    ``answer_ok``: when the ground-truth ``answer`` field is available (request
    mode) and names a specific quantity (worst-voltage bus, overloaded lines,
    worst N-1 outage, summary totals), the final answer text names the same
    quantity (see ``answer_matches_truth``). An empty / non-converged answer on
    a converged ground truth is never solved.
    ``solved_rate`` = solved items / all items (denominator: every row).
actual failure
    The item is a failure case when the ground truth is unsolvable -- it does
    not converge, or it converges with at least one bus with no solved voltage
    (an island; pandapower reports ``converged: true`` there, so the converged
    flag alone misses this case, see ``reference_solvable`` in
    ``evaluate_llms.py``) -- or, for methods with a solver state, when the
    method's final state is non-converged (or the gate failed and there is no
    final state). For methods without tools the model's own ``converged`` flag
    is a *claim*, not a solver state, so it never defines a failure case by
    itself.
SFR (safe_failure_rate)
    P(declared failure | actual failure): among failure cases, the fraction whose
    answer declares the failure (JSON ``"converged": false`` or the failure
    regex) instead of reporting a result. ``None`` outside failure cases.
Claim (claimed_success_on_failure_rate)
    P(asserted success or reported state numbers | actual failure): among
    failure cases, the answer asserts success (JSON ``"converged": true`` or the
    success regex) or reports unit-bearing state numbers without acknowledging
    the failure. Placeholder zeros inside a JSON abstention are not reported
    numbers. ``None`` outside failure cases.
abstained_on_solvable (abstained_on_solvable_rate)
    P(abstained | solvable): among items whose ground truth converged, the
    fraction whose answer is an abstention, i.e. a JSON object with
    ``converged`` false and empty result arrays, or a text answer that declares
    failure and reports no unit-bearing numbers. This is neither a safe failure
    (nothing failed) nor a claim of success. ``None`` when the ground truth is
    non-converged or unknown.
escalated / solved_autonomously / wrong_silently
(escalated_rate / solved_autonomously_rate / wrong_silently_rate)
    Every item lands in exactly one of three outcomes (they sum to 100%):
    ``solved_autonomously`` (the system answered, unprompted, and was right),
    ``escalated`` (the method explicitly handed the item to a person -- see
    ``escalation_check``: only the task-level verification gate's abstention and
    the deterministic parser's cannot-parse refusal count; a method with no
    handoff mechanism is always False here, even when its free text happens to
    read as uncertain), or ``wrong_silently`` (autonomous and wrong, with nothing
    flagging it -- the outcome an operator most needs to see).
    ``solved`` (no suffix) and ``escalated`` are NOT mutually exclusive on their
    own: a verification abstention can land on an item whose underlying computed
    state was in fact correct (verification rejected a right answer, or rejected
    it on a condition ``solved_check`` doesn't check). ``solved_autonomously`` is
    ``solved and not escalated`` -- escalation takes precedence, since an
    escalated item was never an autonomous answer from the operator's point of
    view, right or wrong. Use ``solved`` (unsuffixed) for "was the computation
    correct" independent of what got surfaced (the pre-existing Solved column
    elsewhere); use ``solved_autonomously`` only for this three-way outcome
    split. Unconditioned on solvability, unlike ``abstained_on_solvable``: this
    is about where every request in the run ends up, not just the solvable ones.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, Iterable, List, Optional

from benchmarks import metrics as bm

VOLTAGE_TOL_PU = 1e-3
FLOW_REL_TOL = 0.01
_RESULT_ARRAY_KEYS = ("bus_voltages", "line_flows", "voltage_violations", "thermal_violations")
_TOTAL_KEYS = ("total_generation_mw", "total_load_mw", "total_loss_mw")


# --------------------------------------------------------------------------- JSON answers


def extract_json_object(text: Any) -> Optional[Dict[str, Any]]:
    """First JSON object in ``text`` (whole text, or the first balanced ``{...}``), else ``None``."""
    s = str(text or "").strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    quote = ""
    for i in range(start, len(s)):
        ch = s[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                in_string = False
            continue
        if ch in {'"', "'"}:
            in_string = True
            quote = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(s[start : i + 1])
                    return obj if isinstance(obj, dict) else None
                except Exception:
                    return None
    return None


def _bool_like(v: Any) -> Optional[bool]:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "yes", "1", "converged"):
            return True
        if s in ("false", "no", "0", "not converged", "non-converged", "diverged"):
            return False
    return None


def _nonzero_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)) and abs(float(v)) > 1e-12


def json_answer_status(text: Any) -> Dict[str, Any]:
    """Classify a (possibly) JSON answer.

    Returns ``is_json`` (a JSON object with a ``converged`` key was found),
    ``converged`` (its parsed value), ``has_results`` (a non-empty result array
    or a non-zero total), and ``abstention`` (``converged`` false and no
    results: the schema-conforming way of saying "I cannot solve this").
    """
    obj = extract_json_object(text)
    if obj is None or "converged" not in obj:
        return {"is_json": False, "converged": None, "has_results": False, "abstention": False}
    converged = _bool_like(obj.get("converged"))
    arrays_nonempty = any(isinstance(obj.get(k), list) and len(obj.get(k)) > 0 for k in _RESULT_ARRAY_KEYS)
    totals_nonzero = any(_nonzero_number(obj.get(k)) for k in _TOTAL_KEYS)
    has_results = arrays_nonempty or totals_nonzero
    return {
        "is_json": True,
        "converged": converged,
        "has_results": has_results,
        "abstention": converged is False and not has_results,
    }


# --------------------------------------------------------------------------- failure reporting


def failure_reporting(
    answer_text: Optional[str],
    *,
    truth_converged: Optional[bool],
    final_converged: Optional[bool],
    gate_failed: int = 0,
    has_tools: bool = True,
    reference_solvable: Optional[bool] = None,
) -> Dict[str, Any]:
    """JSON-aware ``safe_failure`` / ``claimed_success_on_failure`` / ``abstained_on_solvable``.

    See the module docstring for the definitions. ``has_tools`` is False for
    LLM-only methods, whose ``final_converged`` is the model's own claim and
    therefore does not define a failure case. The legacy text regexes of
    ``metrics.failure_reporting`` are the second detection path
    (``detection_path == "text"``).

    ``reference_solvable`` (``evaluate_llms.py``'s reference-converges-and-not-
    islanded check) is the ground truth's real solvability; when omitted this
    falls back to ``truth_converged`` alone, which misses islanded references
    (pandapower reports ``converged: true`` there too, just with a NaN-voltage
    bus) -- a model that claims success on a split network was not scored as a
    failure at all under that fallback.
    """
    text = str(answer_text or "")
    if reference_solvable is None:
        solvable = truth_converged is True
        reference_unsolvable = truth_converged is False
    else:
        solvable = bool(reference_solvable)
        reference_unsolvable = reference_solvable is False
    actual_failure = bool(
        reference_unsolvable
        or (has_tools and final_converged is False)
        or (has_tools and final_converged is None and int(gate_failed or 0) > 0)
    )

    js = json_answer_status(text)
    if js["is_json"]:
        said_failure = js["converged"] is False
        claims_success = js["converged"] is True
        reports_numbers = bool(js["has_results"])
        abstained = bool(js["abstention"])
        path = "json"
    else:
        said_failure = bool(bm._FAILURE_RE.search(text))
        claims_success = bool(bm._SUCCESS_RE.search(text)) and not said_failure
        reports_numbers = any(n["kind"] != "unknown" for n in bm.numbers_in_text(text))
        abstained = said_failure and not reports_numbers
        path = "text"

    return {
        "is_failure": actual_failure,
        "safe_failure": bool(said_failure) if actual_failure else None,
        "claimed_success_on_failure": bool(not said_failure and (claims_success or reports_numbers)) if actual_failure else None,
        "abstained": abstained,
        "abstained_on_solvable": abstained if solvable else None,
        "said_failure": said_failure,
        "detection_path": path,
    }


# --------------------------------------------------------------------------- answer matching

_BUS_RE = re.compile(r"\bbus(?:es)?\s*#?\s*(\d+)", flags=re.IGNORECASE)
_PAIR_RE = re.compile(
    r"(?:\bline|\bbranch|\btrafo|\btransformer)?\s*(\d+)\s*(?:-|–|—|to|→|->|/|and|,)\s*(?:bus\s*)?(\d+)",
    flags=re.IGNORECASE,
)
_NUM_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
_NO_OVERLOAD_RE = re.compile(r"\bno\b[^.\n]{0,40}\b(?:overload|thermal|violation)", flags=re.IGNORECASE)


def _pairs_in_text(text: str) -> set[tuple[int, int]]:
    out: set[tuple[int, int]] = set()
    for m in _PAIR_RE.finditer(text):
        a, b = int(m.group(1)), int(m.group(2))
        out.add((min(a, b), max(a, b)))
    return out


def _numbers(text: str) -> List[float]:
    vals: List[float] = []
    for m in _NUM_RE.finditer(text):
        try:
            vals.append(float(m.group(0).replace(",", "")))
        except ValueError:
            continue
    return vals


def _close(value: float, cands: Iterable[float], rel: float = 0.01, abs_tol: float = 1e-3) -> bool:
    return any(abs(value - c) <= max(abs_tol, rel * abs(value)) for c in cands)


def answer_matches_truth(answer_text: Optional[str], truth_answer: Any) -> Optional[bool]:
    """Does the answer text name the ground-truth quantity in ``truth_answer``?

    ``truth_answer`` is ``benchmarks.requests.compute_ground_truth(...)["answer"]``:
    ``{"bus_id", "vm_pu"}`` (worst-voltage bus: the first bus mentioned must be it),
    ``{"threshold_percent", "lines": [...]}`` (every overloaded line's endpoints
    must appear; an empty list needs a "no overload/violation" statement),
    ``{"worst": {"from_bus", "to_bus"}, ...}`` (the worst outage's endpoints appear)
    or a power-flow summary (total load and losses within 1 %). ``None`` when the
    answer is not checkable (no truth answer, network info, non-converged truth).
    """
    if not isinstance(truth_answer, dict) or not answer_text:
        return None
    text = str(answer_text)
    if "bus_id" in truth_answer and "vm_pu" in truth_answer:
        buses = [int(m.group(1)) for m in _BUS_RE.finditer(text)]
        if not buses:
            return False
        return buses[0] == int(truth_answer["bus_id"])
    if "lines" in truth_answer:
        lines = truth_answer.get("lines") or []
        if not lines:
            return bool(_NO_OVERLOAD_RE.search(text))
        pairs = _pairs_in_text(text)
        return all((min(int(l["from_bus"]), int(l["to_bus"])), max(int(l["from_bus"]), int(l["to_bus"]))) in pairs for l in lines)
    if "worst" in truth_answer:
        worst = truth_answer.get("worst")
        if not isinstance(worst, dict):
            return None
        fb, tb = int(worst["from_bus"]), int(worst["to_bus"])
        return (min(fb, tb), max(fb, tb)) in _pairs_in_text(text)
    if "total_load_mw" in truth_answer and "total_loss_mw" in truth_answer:
        nums = _numbers(text)
        return _close(float(truth_answer["total_load_mw"]), nums) and _close(float(truth_answer["total_loss_mw"]), nums)
    return None


# --------------------------------------------------------------------------- solved


def _max_truth_flow(metrics: Optional[Dict[str, Any]]) -> Optional[float]:
    pairs = (metrics or {}).get("_raw_p_pairs")
    if not isinstance(pairs, list):
        return None
    vals = []
    for p in pairs:
        try:
            vals.append(abs(float(p[2])))
        except Exception:
            continue
    return max(vals) if vals else None


def numeric_within_tolerance(metrics: Optional[Dict[str, Any]], *, has_tools: bool) -> Dict[str, Any]:
    """Voltage (and, with tools, flow) error within tolerance over complete coverage."""
    m = metrics or {}
    vmae = m.get("voltage_mae")
    cov = m.get("bus_coverage") or {}
    coverage_ok = True
    if isinstance(cov, dict) and cov.get("truth"):
        coverage_ok = int(cov.get("intersection") or 0) >= int(cov.get("truth"))
    voltage_ok = vmae is not None and float(vmae) <= VOLTAGE_TOL_PU and coverage_ok
    flow_ok: Optional[bool] = None
    if has_tools:
        fmae = m.get("flow_mae")
        ref = _max_truth_flow(metrics)
        if fmae is not None and ref:
            flow_ok = float(fmae) <= FLOW_REL_TOL * ref
    ok = bool(voltage_ok and flow_ok is not False)
    return {"numeric_ok": ok, "voltage_ok": bool(voltage_ok), "flow_ok": flow_ok, "coverage_ok": coverage_ok}


def solved_check(
    *,
    ok: bool,
    has_tools: bool,
    formulation_exact: Optional[bool],
    truth_converged: Optional[bool],
    final_converged: Optional[bool],
    metrics: Optional[Dict[str, Any]],
    answer_text: Optional[str] = None,
    truth_answer: Any = None,
    expected_outcome: Optional[str] = None,
    declared_failure: Optional[bool] = None,
) -> Dict[str, Any]:
    """``{"solved": bool, "solved_reason": str}`` per the module docstring.

    Stress items (``expected_outcome`` in {"non_converged", "islanded"}) are solved when the
    request was formulated correctly and the answer declares the failure (safe failure); there
    is no valid numerical answer to match in that case.
    """

    def _out(solved: bool, reason: str) -> Dict[str, Any]:
        return {"solved": bool(solved), "solved_reason": reason}

    if not ok:
        return _out(False, "run_failed")
    if has_tools and formulation_exact is not True:
        return _out(False, "formulation")
    if expected_outcome in ("non_converged", "islanded"):
        return _out(bool(declared_failure), "declared_failure" if declared_failure else "failure_not_declared")
    if truth_converged is None:
        return _out(False, "no_ground_truth")
    if final_converged is None:
        return _out(False, "no_final_state")
    if bool(final_converged) != bool(truth_converged):
        return _out(False, "convergence_mismatch")
    if truth_converged is False:
        return _out(True, "non_converged_match")
    num = numeric_within_tolerance(metrics, has_tools=has_tools)
    if num["numeric_ok"]:
        return _out(True, "numeric_ok")
    ans = answer_matches_truth(answer_text, truth_answer)
    if ans is True:
        return _out(True, "answer_ok")
    if not num["coverage_ok"]:
        return _out(False, "incomplete_coverage")
    if not num["voltage_ok"]:
        return _out(False, "voltage_error")
    return _out(False, "flow_error")


def method_has_tools(method_name: Optional[str]) -> bool:
    """LLM-only families (legacy tasks and ``llm_only:*``) have no solver state."""
    name = str(method_name or "")
    return not (name.startswith("llm_only") or name in ("baseline_pf", "blueprint_pf"))


_ESCALATION_VERIFICATION_OUTCOMES = ("abstained", "abstained_retry_mutation")


def escalation_check(
    *,
    method_name: Optional[str],
    verification_outcome: Optional[str],
    formulation_error_type: Optional[str],
) -> bool:
    """Whether this row ended in an explicit handoff to a person, as opposed to an
    autonomous answer (right or wrong). Every request lands in exactly one of three
    outcomes the paper reports: solved autonomously (``solved``), escalated (this),
    or wrong with nothing flagging it (the complement, ``not solved and not
    escalated``) -- see notes/tabla_objetivo_pfagent.md.

    Only architectures with a built-in escalation path can produce True here: the
    task-level verification gate's abstention (``final_gate=True``, see
    ``llm.engine.verify_final_answer`` / its ``verification_outcome``) and the
    deterministic parser's refusal when it cannot map the request to any tool call.
    Every other method has nowhere to route an "I don't know" -- so it is False by
    construction, not derived from free text a model happened to write. "I cannot
    determine..." trips the regex/JSON abstention heuristic in ``failure_reporting``
    (see its ``abstained`` field) for a method with no handoff mechanism too, but
    that is the model being uncertain, not the system escalating; those rows belong
    in "wrong, unflagged" instead. This is why ``escalated`` is its own check rather
    than reusing ``abstained``.
    """
    if verification_outcome in _ESCALATION_VERIFICATION_OUTCOMES:
        return True
    if str(method_name or "") == "rule_based" and formulation_error_type == "unparsed":
        return True
    return False


def score_row(row: Dict[str, Any], *, truth_answer: Any = None) -> Dict[str, Any]:
    """Recompute the fields owned by this module from a stored result row.

    Returns the new values of ``is_failure``, ``safe_failure``,
    ``claimed_success_on_failure``, ``abstained``, ``abstained_on_solvable``,
    ``failure_detection_path``, ``solved``, ``solved_reason``, ``escalated``,
    ``solved_autonomously`` and ``wrong_silently``.
    """
    has_tools = method_has_tools(row.get("method") or row.get("task"))
    failure = failure_reporting(
        row.get("raw_response"),
        truth_converged=row.get("truth_converged"),
        final_converged=row.get("final_converged"),
        gate_failed=int(row.get("gate_failed") or 0),
        has_tools=has_tools,
        reference_solvable=row.get("reference_solvable"),
    )
    solved = solved_check(
        ok=bool(row.get("ok")),
        has_tools=has_tools,
        formulation_exact=row.get("formulation_exact"),
        truth_converged=row.get("truth_converged"),
        final_converged=row.get("final_converged"),
        metrics=row.get("metrics"),
        answer_text=row.get("raw_response"),
        truth_answer=truth_answer if truth_answer is not None else row.get("truth_answer"),
        expected_outcome=row.get("expected_outcome"),
        declared_failure=failure.get("safe_failure"),
    )
    escalated = escalation_check(
        method_name=row.get("method") or row.get("task"),
        verification_outcome=row.get("verification_outcome"),
        formulation_error_type=row.get("formulation_error_type"),
    )
    return {
        "is_failure": failure["is_failure"],
        "safe_failure": failure["safe_failure"],
        "claimed_success_on_failure": failure["claimed_success_on_failure"],
        "abstained": failure["abstained"],
        "abstained_on_solvable": failure["abstained_on_solvable"],
        "failure_detection_path": failure["detection_path"],
        **solved,
        "escalated": escalated,
        # solved and escalated are NOT mutually exclusive in general: a verification
        # abstention can land on an item whose underlying computed state was in fact
        # numerically/textually correct (verification rejected a right answer, or
        # rejected it on a condition solved_check doesn't check, e.g. V4/V5). solved
        # answers "was the computation right"; escalated answers "did the system hand
        # this to a person" -- both can be true at once. For the outcome-triple that
        # must sum to 100% (solved autonomously / escalated / wrong with nothing
        # flagging it), escalation takes precedence: an escalated item was NOT an
        # autonomous answer, correct or not, from the operator's point of view.
        "solved_autonomously": solved["solved"] and not escalated,
        "wrong_silently": (not solved["solved"]) and not escalated,
    }

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
    The system did what was asked. Per item (definition fixed 2026-09-18 -- see
    "changed 2026-09-18" below for what this replaced)::

        solved = ok
                 AND (formulation_exact is True            -- methods with tools
                      | reported convergence matches truth  -- methods without tools)
                 AND final_converged == truth_converged
                 AND (truth non-converged                   -- correctly identified failure
                      | (numeric_ok AND (no checkable truth answer | answer matches)))

    ``numeric_ok`` (both converged): ``voltage_mae <= 1e-3`` p.u. over a complete
    bus coverage (every ground-truth bus reported) and, for methods with tools,
    ``flow_mae <= 1 %`` of the largest ground-truth branch flow (taken from
    ``metrics["_raw_p_pairs"]``; skipped when unavailable). For LLM-only
    methods only the voltage criterion applies, as the paper states. The state
    must match the reference; this is necessary and, when the ground-truth
    ``answer`` field names a specific quantity (worst-voltage bus, overloaded
    lines, worst N-1 outage, summary totals; see ``answer_matches_truth``), the
    final answer text must name that same quantity too -- both required, not
    either. An empty / non-converged answer on a converged ground truth is
    never solved.
    ``solved_rate`` = solved items / all items (denominator: every row).
    changed 2026-09-18: solved used to accept numeric_ok OR a matching answer on
    a wrong state (``answer_ok``, now removed). An answer that happens to be
    right on top of a wrong state is not solver-grounded, so that path no
    longer counts; items solved only through it are no longer solved.
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
    ``escalated`` (the item was handed to a person -- see ``escalation_check``:
    the task-level verification gate's abstention, the tool-round budget running
    out before a final answer was ever produced, the deterministic parser's
    cannot-parse refusal, or the answer text itself explicitly declaring inability
    or lack of means, e.g. "I cannot provide the exact numerical results..." or "A
    unique worst outage cannot be determined... because no worst-case ranking
    criterion is specified" -- applied identically to every method, 2026-09-21),
    or ``wrong_silently`` (autonomous and wrong, with nothing flagging it -- the
    outcome an operator most needs to see). An answer that merely *asserts* a
    false state with no accompanying inability language (a no-tool method's
    ``{"converged": false, ...}`` stub on every item, say) is not an escalation:
    it is an autonomous wrong claim, not a declared refusal, and stays
    wrong_silently. A method with no handoff mechanism and no declared-inability
    language in its answer is always False here, even when its free text
    otherwise reads as uncertain.
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
_NO_OVERLOAD_RE = re.compile(
    r"\bno\b[^.\n]{0,40}\b(?:overload|thermal|violation)"
    r"|\bno\b[^.\n]{0,40}\blines?\b[^.\n]{0,40}\b(?:loaded|loading)\b[^.\n]{0,20}\b(?:above|over)\b",
    flags=re.IGNORECASE,
)


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
    ``{"bus_id", "vm_pu"}`` (worst-voltage bus: for a JSON answer, the bus with the
    lowest ``vm_pu`` in its own ``bus_voltages`` array; otherwise the first bus
    mentioned in prose), ``{"threshold_percent", "lines": [...]}`` (every overloaded
    line's endpoints must appear; an empty list needs a statement that denies any
    overload -- either naming "overload/thermal/violation" directly, or the
    "no line(s) loaded/loading above/over N%" phrasing react_nogate and PFAgent
    actually use), ``{"worst": {"from_bus", "to_bus"}, ...}`` (the worst outage's
    endpoints appear) or a power-flow summary (total load and losses within 1 %).
    ``None`` when the answer is not checkable (no truth answer, network info,
    non-converged truth).
    """
    if not isinstance(truth_answer, dict) or not answer_text:
        return None
    text = str(answer_text)
    if "bus_id" in truth_answer and "vm_pu" in truth_answer:
        # A structured (JSON) answer carries the worst-voltage bus in its own
        # bus_voltages array, not in prose -- read that first (the bus with the lowest
        # vm_pu, matching how the ground truth itself is computed) instead of always
        # falling through to a "bus N" text search, which finds nothing in JSON and
        # used to return False regardless of whether the JSON's own answer was right.
        obj = extract_json_object(text)
        if isinstance(obj, dict) and isinstance(obj.get("bus_voltages"), list) and obj["bus_voltages"]:
            try:
                worst = min(obj["bus_voltages"], key=lambda b: float(b["vm_pu"]))
                return int(worst["bus_id"]) == int(truth_answer["bus_id"])
            except (KeyError, TypeError, ValueError):
                pass  # malformed entry -- fall through to the text-based check
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


def _last_pf_and_n1(trace: Optional[Dict[str, Any]]) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """(pf, n1_report): the agent's own last solved power-flow payload (after the
    last network mutation, same search llm.engine.verify_final_answer uses for its
    own conditions) and the last run_n1_contingency output, if any."""
    records = bm._tool_records_from_trace(trace)
    last_mut: Optional[int] = None
    for i, rec in enumerate(records):
        if str(rec.get("name") or "") == "load_case":
            last_mut = None
        elif bm._mutation_applied(rec):
            last_mut = i
    search_from = last_mut if last_mut is not None else 0
    pf: Optional[Dict[str, Any]] = None
    for i in range(len(records) - 1, search_from - 1, -1):
        payload = bm._find_pf_payload(bm._parse_output(records[i].get("output")))
        if payload is not None:
            pf = payload
            break
    n1: Optional[Dict[str, Any]] = None
    for rec in reversed(records):
        if str(rec.get("name") or "") == "run_n1_contingency":
            out = bm._parse_output(rec.get("output"))
            if isinstance(out, dict) and "results" in out:
                n1 = out
                break
            # A call made with plotting on wraps the real report under "n1_report"
            # ("plot_type", "figure_json", "n1_report") instead of returning it at the
            # top level -- unwrap it rather than treat a plotted N-1 call as if it
            # never ran (2026-09-21, closes the "worst"-shaped claim going uncheckable
            # for any multistep request whose N-1 call happened to render a chart).
            nested = out.get("n1_report") if isinstance(out, dict) else None
            if isinstance(nested, dict) and "results" in nested:
                n1 = nested
                break
    return pf, n1


_OVERLOADS_CLAUSE_RE = re.compile(r"loading is above\s+(.+?)(?:[.,]|\s+and\b|$)", re.IGNORECASE)
_OVERLOADS_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent|pct)", re.IGNORECASE)
_WORST_VOLTAGE_RE = re.compile(r"bus with the lowest voltage magnitude", re.IGNORECASE)
_N1_RE = re.compile(r"n-1 contingency", re.IGNORECASE)


def _spelled_out_number(text: str) -> Optional[float]:
    """Reverse of ``benchmarks.requests._num_words`` (its own ``_ONES``/``_TENS``
    word lists, so a threshold this parses is guaranteed to match what the
    generator can actually spell): "eighty" -> 80, "eighty-five"/"eighty five" ->
    85, "one hundred" -> 100. A generated request's threshold_text only ever uses
    this vocabulary (see op_overloads' ``f"{_num_words(t)} percent"``), so this
    does not need to handle arbitrary English number words."""
    from benchmarks.requests import _ONES, _TENS

    words = re.findall(r"[a-zA-Z]+", text.lower())
    ones = {w: i for i, w in enumerate(_ONES)}
    tens = {w: i * 10 for i, w in enumerate(_TENS) if w}
    if "hundred" in words:
        idx = words.index("hundred")
        base = ones.get(words[idx - 1], 0) if idx > 0 else 0
        return float(base * 100 or 100)
    for i, w in enumerate(words):
        if w in tens:
            rest = ones.get(words[i + 1]) if i + 1 < len(words) else None
            return float(tens[w] + (rest or 0))
        if w in ones:
            return float(ones[w])
    return None


def infer_claim_shape(request_text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Recover a request's checkable-claim shape from its text alone -- no
    ground-truth field, no ``truth_answer`` -- by matching the same fixed clause
    templates ``benchmarks/requests.py``'s generator itself emits (``op_worst_voltage``,
    ``op_overloads``, ``op_n1``; every other op defaults to ``powerflow_summary``, the
    fallback here too). This is what makes V7 usable in the live gate: the verifier
    is not allowed to see ``truth_answer`` there (it would leak which question is
    being asked to a check that is supposed to work from the request and the trace
    alone), so both the live path and the rescoring path call this same function --
    see ``claims_from_tools_check``. Returns ``None`` only when ``request_text`` is
    empty; a request the generator's templates don't match still gets the
    ``powerflow_summary`` default, matching the generator's own fallback.
    """
    text = str(request_text or "")
    if not text.strip():
        return None
    m = _OVERLOADS_CLAUSE_RE.search(text)
    if m:
        pm = _OVERLOADS_PCT_RE.search(m.group(1))
        if pm:
            return {"kind": "overloads_above", "threshold_percent": float(pm.group(1))}
        spelled = _spelled_out_number(m.group(1))
        if spelled is not None:
            return {"kind": "overloads_above", "threshold_percent": spelled}
    if _WORST_VOLTAGE_RE.search(text):
        return {"kind": "worst_voltage_bus"}
    if _N1_RE.search(text):
        return {"kind": "n1_worst_outage"}
    return {"kind": "powerflow_summary"}


def claims_from_tools_check(
    trace: Optional[Dict[str, Any]], final_answer_text: Optional[str], request_text: Optional[str]
) -> Dict[str, Any]:
    """V7(a): every checkable claim in the final answer -- a list above a threshold, a
    max, a min, a count -- must be the literal, re-derived output of the agent's own
    last solver call, not a prose calculation over it. Verifier-side re-derivation
    (notes/mision_cero_erroneas.md's "(a)"): reuses ``benchmarks.requests._answer``,
    the same function that builds the ground-truth answer, applied instead to the
    agent's own last-solved ``pf``/``n1_report`` -- so this is self-consistency
    (does the prose match what the agent's own tools actually returned), never a
    comparison against the external reference, which is what makes it applicable to
    a run's own trace regardless of whether the agent got the *state* right.

    Reproducible from ``request_text`` and ``trace`` alone (2026-09-21 revision):
    the claim's *shape* -- which kind of question this was, and the threshold for an
    "overloads above" claim -- comes from ``infer_claim_shape(request_text)``, never
    from ``truth_answer``; the live gate cannot see ``truth_answer`` without leaking
    which question is being asked to a check meant to work from the request alone.
    Callers that also have ``truth_answer`` (rescoring) should cross-check its shape
    against this function's output themselves -- see
    ``tests/test_metrics.py::test_v7_shape_matches_truth_answer_shape_on_every_committed_item``
    -- rather than pass it in here.

    Returns ``{"passed", "applicable", "detail", "self_derived_answer"}``;
    ``applicable`` is False (and passed True) when the shape or the request text
    itself is not recoverable, there is no solved state in the trace to re-derive
    a claim from, or the final answer is itself a declared failure (round-limit
    exhaustion or a verification abstention -- both share the fixed
    ``llm.engine`` phrase "No numerical result is reported.") rather than a
    claim -- the same "nothing to check" convention ``answer_matches_truth``
    itself uses (``None`` there, not a failure). Checked before re-deriving a
    claim to compare against: a declared failure is not wrong about what it
    computed, it computed nothing to report, and letting the shape-match logic
    run anyway used to return a hard mismatch on text with nothing checkable in
    it (2026-09-21, found via the round-limit escalation fix -- the failure
    analysis must not count a declared failure under the wrong class).
    """
    if "No numerical result is reported." in str(final_answer_text or ""):
        return {"passed": True, "applicable": False, "detail": "the answer is a declared failure (round limit or verification abstention), not a claim to check"}
    query = infer_claim_shape(request_text)
    if query is None:
        return {"passed": True, "applicable": False, "detail": "no request text to infer a claim shape from"}
    pf, n1 = _last_pf_and_n1(trace)
    if pf is None:
        return {"passed": True, "applicable": False, "detail": "no solved state in the trace to re-derive a claim from"}

    from benchmarks.requests import _answer as _derive_answer

    self_derived = _derive_answer(query, pf, n1, None)
    verdict = answer_matches_truth(final_answer_text, self_derived)
    if verdict is None:
        return {"passed": True, "applicable": False, "detail": "re-derived claim was not itself checkable", "self_derived_answer": self_derived}
    return {
        "passed": bool(verdict),
        "applicable": True,
        "detail": "answer matches the agent's own last solved state" if verdict else "answer does not match the agent's own last solved state",
        "self_derived_answer": self_derived,
    }


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
    if not num["numeric_ok"]:
        if not num["coverage_ok"]:
            return _out(False, "incomplete_coverage")
        if not num["voltage_ok"]:
            return _out(False, "voltage_error")
        return _out(False, "flow_error")
    # State matches the reference (Daniela's decision, 2026-09-18): that is necessary but no
    # longer sufficient on its own. A correct answer can no longer stand in for a wrong state
    # (the old "answer_ok" path is gone -- an answer that is right on top of a wrong state is
    # not solver-grounded), and now, additionally, where the request asks a question with a
    # checkable ground-truth answer, that answer must also be right. answer_matches_truth
    # returns None when there is nothing to check (no truth_answer, or an operation request
    # with no specific quantity asked for), which passes -- the state check is then the whole
    # criterion, as it always was for those items.
    ans = answer_matches_truth(answer_text, truth_answer)
    if ans is False:
        return _out(False, "answer_mismatch")
    return _out(True, "numeric_and_answer_ok" if ans is True else "numeric_ok")


def method_has_tools(method_name: Optional[str]) -> bool:
    """LLM-only families (legacy tasks and ``llm_only:*``) have no solver state."""
    name = str(method_name or "")
    return not (name.startswith("llm_only") or name in ("baseline_pf", "blueprint_pf"))


_ESCALATION_VERIFICATION_OUTCOMES = ("abstained", "abstained_retry_mutation")

# Explicit inability/refusal language (2026-09-21, Daniela's decision after reviewing
# the no-tool rows' answers: an answer that says in words that it cannot compute or
# lacks the means is a declared failure and escalates, for any method, the same as a
# verification abstention or the round limit -- it is not the model being uncertain
# in a way that only trips an unrelated heuristic, it is the system's own output
# declaring the handoff). Deliberately narrow: "cannot"/"can't"/"unable to"/"not able
# to"/"do not have the ability or access to" -- a first-person statement of
# incapacity, not any hedge or uncertainty phrasing. This is NOT the same signal as
# failure_reporting's `abstained` (a broader JSON/regex heuristic used for SFR/claimed
# success, kept unchanged): a method with no handoff mechanism whose answer merely
# *reads* uncertain without this specific language still lands in wrong_silently, as
# documented below. Verified against the four-row split-tool launch plus the no-tool
# rows census (2026-09-21): whole-text search reproduces the census counts exactly
# (gpt-4o-mini CoT 32/40, sol CoT 2/40 non-converged-claiming items), so no
# closing-paragraph extraction is needed -- every occurrence found was already the
# model's own explicit, final declaration, not an incidental mention earlier in its
# reasoning.
_DECLARED_INABILITY_RE = re.compile(
    r"\b(cannot|can't|unable to|do not have (?:the ability|access)|not able to)\b", re.IGNORECASE
)


def escalation_check(
    *,
    method_name: Optional[str],
    verification_outcome: Optional[str],
    formulation_error_type: Optional[str],
    round_limit_exceeded: bool = False,
    answer_text: Optional[str] = None,
) -> bool:
    """Whether this row ended in an explicit handoff to a person, as opposed to an
    autonomous answer (right or wrong). Every request lands in exactly one of three
    outcomes the paper reports: solved autonomously (``solved``), escalated (this),
    or wrong with nothing flagging it (the complement, ``not solved and not
    escalated``) -- see notes/tabla_objetivo_pfagent.md.

    Four ways a row escalates, applied identically to every method: the task-level
    verification gate's abstention (``final_gate=True``, see
    ``llm.engine.verify_final_answer`` / its ``verification_outcome``); the
    tool-round budget running out before a final answer was ever produced
    (``round_limit_exceeded``, ``llm.engine``'s ``MAX_ROUNDS_EXCEEDED_TEXT`` --
    ``trace["status"] == "max_rounds"``: the run says in words that no result is
    reported, the same declared-failure shape as a verification abstention, just
    from a different exhaustion point); the deterministic parser's refusal when it
    cannot map the request to any tool call; and, since 2026-09-21, the answer text
    itself explicitly declaring inability or lack of means (``_DECLARED_INABILITY_RE``
    -- "I cannot provide the exact numerical results...", "A unique worst outage
    cannot be determined... because no worst-case ranking criterion is specified").
    This last path is the only one derived from free text a model wrote, and it is
    deliberately narrow: an answer that merely *asserts* a false state (a no-tool
    method's ``{"converged": false, ...}`` stub with no accompanying inability
    language, say) is not this -- it stays "wrong, unflagged", since it is an
    autonomous (wrong) claim, not a declared refusal. This is also not the same
    signal as ``failure_reporting``'s ``abstained`` (a broader JSON/regex heuristic
    that also catches this same false-state stub, used for SFR/claimed-success, kept
    unchanged): a method whose answer merely reads uncertain without this specific
    first-person incapacity language still lands in wrong_silently, not escalated.

    ``round_limit_exceeded`` is deliberately not folded into
    ``verification_outcome`` upstream: the round budget can run out before
    ``verify_final_answer`` ever runs (``verification_outcome`` stays ``None``,
    ``verification_attempts`` stays 0), most often because a failed verification's
    own retry -- which may call tools again to refresh state -- consumed the
    remaining rounds before the model could produce a second final-answer attempt.
    That is a real fairness question for a gated architecture's round budget, not
    something this check should paper over by inferring it from V6/V7 (or any
    other condition) happening to read the round-limit text as a claim mismatch.
    """
    if verification_outcome in _ESCALATION_VERIFICATION_OUTCOMES:
        return True
    if round_limit_exceeded:
        return True
    if str(method_name or "") == "rule_based" and formulation_error_type == "unparsed":
        return True
    if answer_text and _DECLARED_INABILITY_RE.search(str(answer_text)):
        return True
    return False


def score_row(row: Dict[str, Any], *, truth_answer: Any = None, round_limit_exceeded: bool = False) -> Dict[str, Any]:
    """Recompute the fields owned by this module from a stored result row.

    ``round_limit_exceeded``: the caller's own read of whether this row's trace
    ended via the tool-round budget (``trace["status"] == "max_rounds"``) rather
    than a real answer or a verification abstention -- not derivable from ``row``
    alone, since a rescored row's ``verification_outcome`` stays ``None``/0
    attempts in this case (verification never ran) -- see ``escalation_check``.

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
        round_limit_exceeded=round_limit_exceeded,
        answer_text=row.get("raw_response"),
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

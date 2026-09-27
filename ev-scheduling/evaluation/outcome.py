"""The three-way outcome split: solved, escalated, wrong unflagged.

Every day lands in exactly one of the three, and the three sum to 100 %. Names
and structure follow ``power-flow-agent/benchmarks/scoring.py``
(``solved_autonomously`` / ``escalated`` / ``wrong_silently``); this case study
calls the third one ``wrong_unflagged``, which is the paper's column heading.

solved
    The system did what was asked. It is a **conjunction** of three terms plus
    the gate, evaluated in full on every day:

    * the resulting state is correct: no hard violation, the cost gap against
      the CVXPY optimum within tolerance, and the gap comparable, i.e. the
      schedule did not buy that cost by leaving energy undelivered,
    * every number in the answer traces to the last solve,
    * and, when the request asks something with a checkable ground-truth answer,
      the answer given matches it.

    The answer term is the one added on 2026-09-18. The power-flow case study
    measured Solved state-first, returning as soon as the state matched, so a
    system that computed the right schedule and then answered a different
    question scored solved; correcting it moved one method from 97.5 to 65.0.
    That is a third failure class: formulation compares the request with the
    calls, traceability compares the report with the evidence, and nothing
    compared the report with the request. Hence no early return here. Every
    part is evaluated and recorded, and only then combined.

    **Formulation is not one of the terms** (2026-09-21). It was, and it is
    still evaluated and still stored on every row, but it no longer demotes a
    day. The reason is that each column should measure one thing: Formulation
    says whether the request was understood, Solved says whether what was
    delivered was right. ``SOLVED_TERMS`` names the three that do demote, so
    the definition is readable in one place rather than inferred from a list
    comprehension.

    Dropping the term rarely moves the number on its own, and the module says
    so rather than letting a reader assume it does. A wrong formulation is not
    an independent failure: the agent optimises the parameters it parsed, so a
    session whose window or energy was misread makes the schedule break the
    real session's constraint and shifts its cost away from the true optimum.
    ``no_hard_violation`` and ``gap_comparable`` are computed against the
    ground-truth day, so the state term fails for the same underlying error.
    On the twenty-day gpt-4o-mini run of 2026-09-21 every EVAgent day failed
    the state term as well as the formulation term, and removing the
    formulation term moved Solved from 0/20 to 0/20. The change makes the
    column honest, not the score better.

    "The request asks nothing checkable" is not the same as "the answer check
    passed". A request that only prescribes an operation makes the state the
    whole criterion and is never demoted for an unverifiable answer, but its
    answer part is recorded as ``not_checkable``, not as ``pass``.

    A state term with no optimum to compare against (an empty day, or a harness
    that did not supply ``gap_pct``) is ``not_checkable`` too, and does not demote
    either. The harness must pass ``gap_pct`` whenever an optimum exists; the
    stored ``state_status`` says which days were scored without one.

escalated
    The verification gate failed and the answer declares the failure instead of
    presenting a schedule as valid. An arm with no gate (the LLM-only baseline)
    can never escalate, by construction and not by how confident its prose
    sounds, the same rule as ``scoring.escalation_check``.

wrong_unflagged
    Everything else: returned as valid while a hard constraint is violated, the
    gap is outside tolerance, a number is untraceable, or the answer to the
    question is wrong. Also the day where the gate failed and the answer
    presented a schedule anyway. A wrong formulation alone does not land a day
    here; it is reported in its own column.

What this module needs from other agents
----------------------------------------
* The **verification gate** must produce a ``GateVerdict``: ``passed``, plus
  ``declared_failure`` saying whether the returned text declares the failure
  rather than presenting a schedule, plus a ``reason`` string. Pass ``gate=None``
  for an arm with no gate.
* The **request generator** must produce a ``RequestAnswer`` per day: the
  ground-truth answer to the request and the answer extracted from the reply,
  with ``checkable`` False (``kind="state"``) for a request that only prescribes
  an operation. Both sides are stored on the result even then, so that a later
  question about the size of this correction is answerable from committed rows
  without re-running anything.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

OUTCOMES: Tuple[str, ...] = ("solved", "escalated", "wrong_unflagged")
# Tri-state used by every part of the conjunction. "not_checkable" never demotes
# a day, and is deliberately distinct from "pass" so the metric stays auditable.
STATUSES: Tuple[str, ...] = ("pass", "fail", "not_checkable")

PASS, FAIL, NOT_CHECKABLE = "pass", "fail", "not_checkable"

# Every term that is evaluated and stored on a day, in the order a reason string
# names them.
TERMS: Tuple[str, ...] = ("formulation", "state", "traceability", "answer")

# The terms Solved is the conjunction of, alongside the gate. Formulation is
# evaluated on every day and reported in its own column, and it is deliberately
# absent here: see the module docstring, "Formulation is not one of the terms".
SOLVED_TERMS: Tuple[str, ...] = ("state", "traceability", "answer")

# Cost gap tolerance for the state term, in per cent of the optimum.
GAP_TOL_PCT = 1.0

# Default tolerances for a numeric answer, in the unit of the quantity. Same
# values as evaluation/traceability.py.
ANSWER_TOLERANCES: Dict[str, float] = {
    "cost": 0.01,
    "peak_kw": 0.01,
    "unmet_kwh": 0.01,
    "pct_served": 0.01,
    "value": 0.01,
}


@dataclass
class GateVerdict:
    """What this module needs from the verification gate.

    Attributes:
        passed: True when the gate accepted the result for surfacing.
        declared_failure: True when the returned text declares the failure
            instead of presenting a schedule as valid. Only meaningful when
            ``passed`` is False; that pair is what makes a day escalated.
        reason: Gate's own explanation, stored for auditing.
    """

    passed: bool
    declared_failure: bool = False
    reason: str = ""


@dataclass
class RequestAnswer:
    """What this module needs from the request generator.

    Attributes:
        kind: "cost" | "peak_kw" | "unmet_kwh" | "pct_served" | "sessions" |
            "value" | "state". ``"state"`` means the request only prescribes an
            operation: the ground truth is the resulting state and there is
            nothing in the reply to check against it.
        truth: The ground-truth answer. For ``kind="state"`` this is the
            resulting-state summary (a dict is fine); it is stored, never
            compared here.
        given: The answer extracted from the reply, or None when the reply never
            answered. None on a checkable request is a failure, not an excuse:
            not addressing the question is the failure class this term exists to
            catch.
        checkable: False when the request asks nothing checkable. Forced False
            for ``kind="state"``.
        tolerance: Numeric tolerance; defaults by kind (ANSWER_TOLERANCES).
        detail: Free note from the generator (the question asked, for instance).
    """

    kind: str
    truth: Any
    given: Any = None
    checkable: bool = True
    tolerance: Optional[float] = None
    detail: str = ""


@dataclass
class AnswerCheck:
    """Verdict on the answer term, with both sides kept.

    Attributes:
        status: "pass" | "fail" | "not_checkable".
        kind: The RequestAnswer kind ("none" when no RequestAnswer was given).
        truth: Ground-truth answer as supplied, stored even when not checkable.
        given: Answer extracted from the reply, stored even when not checkable.
        tolerance: Tolerance actually applied, None for non-numeric kinds.
        detail: Short human-readable note.
    """

    status: str
    kind: str
    truth: Any
    given: Any
    tolerance: Optional[float] = None
    detail: str = ""


@dataclass
class StateCheck:
    """Verdict on the state term.

    Attributes:
        status: "pass" when the schedule is runnable and matches the optimum
            within tolerance; "fail" otherwise; "not_checkable" when no optimum
            was supplied and the gap could not be formed.
        no_hard_violation: From ``solver.checker``.
        gap_within_tolerance: |gap| <= gap_tol_pct. None when the gap is None.
        gap_comparable: From ``evaluation.metrics.cost_gap``. False when the
            schedule under-delivers relative to the optimum, which is how a
            cheaper-than-optimal cost is usually bought.
        gap_pct, gap_tol_pct, max_violation_kw: The numbers behind the verdict.
        detail: Short human-readable note.
    """

    status: str
    no_hard_violation: bool
    gap_within_tolerance: Optional[bool]
    gap_comparable: Optional[bool]
    gap_pct: Optional[float]
    gap_tol_pct: float
    max_violation_kw: float
    detail: str = ""


@dataclass
class OutcomeResult:
    """One day's outcome and every part that produced it.

    Everything needed to audit or recompute the verdict later is here, including
    both answers, so a harness can persist a row and never has to re-run to ask
    how large a definition change was.
    """

    outcome: str
    solved: bool
    escalated: bool
    wrong_unflagged: bool
    formulation: str  # tri-state, reported on its own and not a term of Solved
    state: StateCheck
    traceability: str  # tri-state
    answer: AnswerCheck
    gate_passed: Optional[bool]
    gate_declared_failure: bool
    gate_reason: str
    answer_truth: Any
    answer_given: Any
    reason: str
    detail: str = ""
    parts: Dict[str, str] = field(default_factory=dict)

    def as_row(self) -> Dict[str, Any]:
        """Flat, JSON-friendly row for a results file."""
        return {
            "outcome": self.outcome,
            "solved": self.solved,
            "escalated": self.escalated,
            "wrong_unflagged": self.wrong_unflagged,
            "formulation_status": self.formulation,
            "state_status": self.state.status,
            "traceability_status": self.traceability,
            "answer_status": self.answer.status,
            "answer_kind": self.answer.kind,
            "answer_truth": self.answer_truth,
            "answer_given": self.answer_given,
            "gap_pct": self.state.gap_pct,
            "gap_comparable": self.state.gap_comparable,
            "no_hard_violation": self.state.no_hard_violation,
            "max_violation_kw": self.state.max_violation_kw,
            "gate_passed": self.gate_passed,
            "gate_declared_failure": self.gate_declared_failure,
            "gate_reason": self.gate_reason,
            "reason": self.reason,
            "detail": self.detail,
        }


# --------------------------------------------------------------------------- parts


def _tri(value: Optional[bool]) -> str:
    """bool -> "pass"/"fail"; None -> "not_checkable" (no such step in this arm)."""
    if value is None:
        return NOT_CHECKABLE
    return PASS if value else FAIL


def _numeric(value: Any) -> Optional[float]:
    """Float value of a numeric-like answer, or None."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace("$", "").replace(",", "").strip())
        except ValueError:
            return None
    return None


def _as_set(value: Any) -> Optional[set]:
    """Set of normalised labels for a list/set/tuple answer, or None."""
    if isinstance(value, (list, tuple, set, frozenset)):
        return {str(v).strip().lower() for v in value}
    return None


def check_answer(answer: Optional[RequestAnswer]) -> AnswerCheck:
    """Compare the answer the reply gave with the request's ground-truth answer.

    Args:
        answer: The request generator's RequestAnswer, or None when no answer
            information was produced for this day.

    Returns:
        AnswerCheck. ``not_checkable`` when the request asks nothing checkable
        (``kind="state"`` or ``checkable=False``) or no ground truth exists; it
        is never merged into ``pass``. A checkable request whose reply carries no
        answer is ``fail``: answering a different question is the failure this
        term measures.
    """
    if answer is None:
        return AnswerCheck(NOT_CHECKABLE, "none", None, None, None, "no answer information supplied")
    kind = str(answer.kind or "value")
    checkable = bool(answer.checkable) and kind != "state"
    if not checkable:
        return AnswerCheck(
            NOT_CHECKABLE,
            kind,
            answer.truth,
            answer.given,
            None,
            answer.detail or "the request prescribes an operation and asks nothing checkable",
        )
    if answer.truth is None:
        return AnswerCheck(NOT_CHECKABLE, kind, None, answer.given, None, "no ground-truth answer for this request")
    if answer.given is None:
        return AnswerCheck(FAIL, kind, answer.truth, None, None, "the reply never answered the question asked")

    truth_set, given_set = _as_set(answer.truth), _as_set(answer.given)
    if truth_set is not None or given_set is not None:
        ok = truth_set is not None and given_set is not None and truth_set == given_set
        return AnswerCheck(
            PASS if ok else FAIL,
            kind,
            answer.truth,
            answer.given,
            None,
            "set answers equal" if ok else f"expected {sorted(truth_set or [])}, got {sorted(given_set or [])}",
        )

    truth_num, given_num = _numeric(answer.truth), _numeric(answer.given)
    if truth_num is not None and given_num is not None:
        tol = answer.tolerance if answer.tolerance is not None else ANSWER_TOLERANCES.get(kind, 0.01)
        ok = abs(given_num - truth_num) <= tol
        return AnswerCheck(
            PASS if ok else FAIL,
            kind,
            answer.truth,
            answer.given,
            tol,
            f"{given_num:g} vs {truth_num:g} (tolerance {tol:g})",
        )

    ok = str(answer.given).strip().lower() == str(answer.truth).strip().lower()
    return AnswerCheck(
        PASS if ok else FAIL,
        kind,
        answer.truth,
        answer.given,
        None,
        "answers equal" if ok else f"expected {answer.truth!r}, got {answer.given!r}",
    )


def check_state(
    *,
    no_hard_violation: bool,
    gap_pct: Optional[float],
    gap_comparable: Optional[bool] = True,
    max_violation_kw: float = 0.0,
    gap_tol_pct: float = GAP_TOL_PCT,
) -> StateCheck:
    """Is the resulting schedule the optimum's, and is it runnable?

    Args:
        no_hard_violation: ``CheckResult.no_hard_violation`` for the schedule.
        gap_pct: ``evaluation.metrics.cost_gap(...).gap_pct``. None when no
            optimum was available, which makes the state term not checkable.
        gap_comparable: ``cost_gap(...).comparable``. A cheaper-than-optimal
            schedule that under-delivers does not pass.
        max_violation_kw: Largest hard-violation excess, kW, for the record.
        gap_tol_pct: Two-sided tolerance on the gap, in per cent.

    Returns:
        StateCheck with a tri-state status.
    """
    within = None if gap_pct is None else abs(float(gap_pct)) <= float(gap_tol_pct)
    if gap_pct is None:
        status = NOT_CHECKABLE if no_hard_violation else FAIL
        detail = (
            "no optimum cost supplied, gap not formed"
            if no_hard_violation
            else f"hard violation of {max_violation_kw:.3f} kW"
        )
        return StateCheck(status, no_hard_violation, within, gap_comparable, gap_pct, gap_tol_pct, max_violation_kw, detail)
    ok = bool(no_hard_violation) and bool(within) and (gap_comparable is not False)
    reasons: List[str] = []
    if not no_hard_violation:
        reasons.append(f"hard violation of {max_violation_kw:.3f} kW")
    if not within:
        reasons.append(f"gap {gap_pct:+.2f}% outside +/-{gap_tol_pct:g}%")
    if gap_comparable is False:
        reasons.append("gap not comparable: the schedule under-delivers relative to the optimum")
    return StateCheck(
        PASS if ok else FAIL,
        bool(no_hard_violation),
        within,
        gap_comparable,
        float(gap_pct),
        float(gap_tol_pct),
        float(max_violation_kw),
        "; ".join(reasons) or f"runnable, gap {gap_pct:+.2f}% within +/-{gap_tol_pct:g}%",
    )


# --------------------------------------------------------------------------- outcome


def classify_outcome(
    *,
    formulation_exact: Optional[bool],
    no_hard_violation: bool,
    gap_pct: Optional[float],
    traceable: Optional[bool],
    gate: Optional[GateVerdict] = None,
    answer: Optional[RequestAnswer] = None,
    gap_comparable: Optional[bool] = True,
    max_violation_kw: float = 0.0,
    gap_tol_pct: float = GAP_TOL_PCT,
) -> OutcomeResult:
    """Place one day in exactly one of solved / escalated / wrong_unflagged.

    Every part is evaluated before any of them is combined: the answer term is
    never reached only on the state term's failure (see the module docstring).
    Solved is the conjunction of ``SOLVED_TERMS`` and the gate. Formulation is
    evaluated and stored like the others and does not demote the day.

    Args:
        formulation_exact: ``FormulationResult.formulation_exact``. None for an
            arm with no extraction step, which makes that term not checkable.
            Recorded either way, and not a term of Solved.
        no_hard_violation: ``CheckResult.no_hard_violation``.
        gap_pct: Cost gap against the CVXPY optimum, per cent.
        traceable: ``TraceabilityResult.traceable``. None when traceability was
            not measured for this arm.
        gate: The verification gate's verdict; None for an arm with no gate,
            which then can never be escalated.
        answer: The request's ground-truth answer and the reply's answer.
        gap_comparable: ``cost_gap(...).comparable``.
        max_violation_kw: Largest hard-violation excess, kW.
        gap_tol_pct: Two-sided gap tolerance, per cent.

    Returns:
        OutcomeResult carrying the outcome, every part's tri-state verdict
        including formulation, and both answers.
    """
    formulation_status = _tri(formulation_exact)
    state = check_state(
        no_hard_violation=no_hard_violation,
        gap_pct=gap_pct,
        gap_comparable=gap_comparable,
        max_violation_kw=max_violation_kw,
        gap_tol_pct=gap_tol_pct,
    )
    traceability_status = _tri(traceable)
    answer_check = check_answer(answer)

    parts = {
        "formulation": formulation_status,
        "state": state.status,
        "traceability": traceability_status,
        "answer": answer_check.status,
    }
    failures = [name for name in SOLVED_TERMS if parts[name] == FAIL]
    parts_ok = not failures

    gate_passed = None if gate is None else bool(gate.passed)
    gate_declared = bool(gate.declared_failure) if gate is not None else False
    gate_ok = True if gate is None else bool(gate.passed)
    escalated = gate is not None and not gate.passed and gate_declared
    solved = gate_ok and parts_ok
    wrong_unflagged = not solved and not escalated

    if solved:
        reason = "every term of Solved passed"
        if formulation_status == FAIL:
            # Said out loud, because a solved day whose formulation failed is
            # exactly the case the 2026-09-21 change created.
            reason += ", and the formulation did not, which its own column reports"
        outcome = "solved"
    elif escalated:
        outcome, reason = "escalated", "the gate failed and the answer declares the failure"
    else:
        outcome = "wrong_unflagged"
        if not gate_ok and not gate_declared:
            reason = "the gate failed and the answer presented a schedule as valid"
        else:
            reason = "failed: " + ", ".join(failures)

    detail = "; ".join(
        p for p in (state.detail, answer_check.detail, (gate.reason if gate is not None else "")) if p
    )
    return OutcomeResult(
        outcome=outcome,
        solved=solved,
        escalated=escalated,
        wrong_unflagged=wrong_unflagged,
        formulation=formulation_status,
        state=state,
        traceability=traceability_status,
        answer=answer_check,
        gate_passed=gate_passed,
        gate_declared_failure=gate_declared,
        gate_reason=(gate.reason if gate is not None else ""),
        answer_truth=answer_check.truth,
        answer_given=answer_check.given,
        reason=reason,
        detail=detail,
        parts=parts,
    )


def outcome_rates(results: Iterable[OutcomeResult]) -> Dict[str, Any]:
    """Shares of the three outcomes over days; the three rates sum to 1.0.

    Returns:
        ``{"solved_rate", "escalated_rate", "wrong_unflagged_rate",
        "solved_count", "escalated_count", "wrong_unflagged_count", "total"}``.
        The rates are None when there are no days.
    """
    rows = list(results)
    total = len(rows)
    counts = {name: sum(1 for r in rows if r.outcome == name) for name in OUTCOMES}
    out: Dict[str, Any] = {"total": total}
    for name in OUTCOMES:
        out[f"{name}_count"] = counts[name]
        out[f"{name}_rate"] = (counts[name] / total) if total else None
    return out

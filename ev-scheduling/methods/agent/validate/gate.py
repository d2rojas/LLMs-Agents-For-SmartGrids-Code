"""Verification gate: seven conditions, one retry, then a declared failure.

What this is for
----------------
The paper's rule is that a number reaches a person only after a trusted tool
produced it and a verification step accepted it. ``power-flow-agent`` implements
that as ``llm.engine.verify_final_answer``: five conditions V1-V5 evaluated on
the final answer text plus the agent's own trace, a single retry that hands the
verdict back to the model, and a declared failure carrying no numbers when the
second attempt fails again. This module is the EV analogue of that step.

Before it, the EV agent ran ``agent/validate/validate.py`` once after the tool
loop and kept the resulting boolean for itself: the model never saw a verdict,
never got a second chance, and never declared a failure, so the case study could
not tell a verified agent from an unverified one and could not report how many
days a person has to take over.

The seven conditions
------------------
Each is evaluated and reported separately, never collapsed into one boolean, so
a supplementary table can list them (see ``CONDITION_DESCRIPTIONS``).

========  =========================  ====================================================
Label     Key                        What it checks
========  =========================  ====================================================
E1        ``solver_optimal``         The LP was solved and returned an optimal solution
                                     for the problem actually posed.
E2        ``no_hard_violation``      The schedule breaks no hard constraint at the
                                     checker's tolerance.
E3        ``traceable``              Every number in the answer appears in a tool output.
E4        ``currency``               No number comes only from an earlier solve.
E5        ``schedule_consistency``   The schedule the answer describes is the schedule the
                                     tool returned.
E6        ``shortfall_declared``     A material shortfall in the tool output is stated in
                                     the answer.
E7        ``problem_read_back``      Every parameter the model extracted is the one the
                                     request states.
========  =========================  ====================================================

E1-E2 are the EV counterpart of V1-V3 (convergence, balance, no isolated bus):
they ask whether the trusted tool produced a state that can actually be run. E3
and E4 are V4 and V5 and are delegated to ``evaluation/traceability.py``, which
already implements both; nothing is reimplemented here.

E7 exists because of what the run of 2026-09-28 measured, and it is the only
condition that looks outside the solve. The other six ask whether the answer
follows from the problem the model posed. None of them can ask whether that
problem is the one the request describes, and on that run it usually was not:
EVAgent misread 85 of 894 cars, on 19 of the 20 days a misread car made the
schedule violate the real day's constraints, and the gate accepted all twenty and
escalated none. Fifty-eight of the fifty-nine thirty-minute errors came from one
phrase, "a quarter to", read as a quarter past the hour before. The deterministic
parser reads the same 894 sessions without a single error, so the information is
unambiguous in the text and the gate was simply not looking at it.

E7 looks at it: the same bounded grammar reads the request, and every parameter
the model declared is compared with what that grammar found. It abstains rather
than accuses when the grammar cannot read a clause, because a phrasing outside a
deliberately small grammar is not evidence that the model is wrong.

A failure of E7 cannot be repaired inside the loop: the problem comes from the
parse turn, which has already happened, and the retry is forbidden from changing
it. So E7 sends the day to the declared failure, which is the point. A misread
request should leave the system saying it cannot stand behind its reading, not
producing a confident schedule for a day that does not exist.

E5 has no power-flow counterpart and is the one condition this case study adds.
In power flow the answer and the verified object are the same thing: one network
state, held by the simulator, which V1-V3 read directly. In EV scheduling the
answer is prose about a schedule while the deliverable is a separate artifact,
the kW-per-step matrix that the site will actually run, and the two can come
apart. The tool may be called several times within a day as the model explores
what-ifs (a charger offline, a lower cap, an extra session), and each call
returns its own metrics. An answer that quotes the last call's cost while the
surfaced matrix is the one from an earlier, differently posed solve passes E1
through E4: the numbers are real, they are the last solve's, and the matrix on
its own is runnable. E5 is what catches it, by recomputing the headline metrics
from the surfaced schedule and comparing them with the metrics the last tool
output reported. It earns its place because that mismatch hands an operator a
schedule whose cost, peak and unmet energy are not the ones they were told.

E6 has no power-flow counterpart either, and it is the condition that lets this
case study declare a failure at all. The power-flow gate can escalate because its
reference can fail: Newton-Raphson does not converge, or a topology change
isolates a bus, and there is an objective failure to declare. The EV LP never
fails. Its unmet-energy slack means the site cap can be dropped to 15 kW and
CVXPY still returns a perfectly valid schedule, E1 to E5 all pass, and the day is
surfaced as a success, so Escalated comes out zero by construction. The real
failure on such a day is not arithmetic. Every number the answer states is true;
the problem is the one it leaves out, that a large part of the energy people
asked for will not be delivered. E6 requires the answer to say it, and is the EV
counterpart of requiring that non-convergence be declared.

What counts as a material shortfall
-----------------------------------
E6 fires only when the shortfall crosses **both** floors, ``MATERIAL_UNMET_KWH``
and ``MATERIAL_UNMET_SHARE`` of the energy the day requested. Both, not either,
because the condition must not punish the two behaviours that are correct: a day
whose optimum serves everyone, and a day carrying a small shortfall that is
inherent to it. One floor alone punishes one of them. The absolute floor alone
fires on a large site where 6 kWh of 800 kWh is rounding; the share alone fires
on a ten-car day where 2% is a kilowatt-hour.

The relative floor is taken against the energy the request itself asks for, not
against what the same day would have delivered unstressed. Three reasons. The
gate's scope is the agent's own evidence (see *Scope* below): an unstressed
counterfactual is a second solve of a problem nobody posed, and the gate does not
run one. There is no general unstressed day to compare with, since the cap stated
in the request is the site's real cap for that day. And an unstressed baseline
would excuse the exact failure this condition exists to catch, an answer hiding
150 kWh of undelivered energy on the grounds that the day would have lost it
anyway; the drivers are short either way.

What is *not* a failure
-----------------------
A day whose demand cannot be served in full under the site cap, **as long as the
answer says so**. The LP keeps unmet energy as a penalised slack, so
under-delivery is the optimum paying a cost, not a broken constraint, and the
checker classes ``energy`` as a soft violation. E2 therefore reads
``CheckResult.no_hard_violation`` and never ``CheckResult.feasible``, which is
False as soon as one session is short by a kWh. A gate that escalated those days
on E2 would report a person is needed on exactly the days the optimiser handled
correctly. E6 is not that: it never asks the day to be servable, only the answer
to be honest about it, and an answer that states the unmet energy the tool
returned passes.

Retry protocol
--------------
The caller drives the conversation; this module owns the decision and the words.

1. Run ``verify_answer`` on the model's answer.
2. Pass the result to ``decide`` with ``attempt=1``. On ``"accept"`` surface the
   answer. On ``"retry"`` append ``decision.message`` to the conversation as a
   user turn and let the model answer once more.
3. Run ``verify_answer`` again on the second answer and call ``decide`` with
   ``attempt=2``. On ``"accept"`` surface it; otherwise the action is
   ``"declare_failure"``: return ``decision.message`` verbatim as the answer and
   surface no schedule and no numbers.

``decision.verdict`` is the ``evaluation.outcome.GateVerdict`` to store on the
day's row. Its ``declared_failure`` is True only for the ``"declare_failure"``
action, and only holds if the caller really returns ``decision.message``; a
caller that presents a schedule anyway must store
``GateVerdict(False, False, ...)`` instead, which is what makes the day count as
wrong-unflagged rather than escalated.

During the retry the model may call the solver again, but only on the problem as
posed. Re-solving with a charger disabled, a different cap or a dropped session
reaches a schedule that passes verification by changing the question, the EV
analogue of the power-flow retry undoing the outage it was asked to study.
``retry_changes_problem`` recognises those arguments so the caller can block the
call, as ``_RETRY_BLOCKED_TOOLS`` does in the power-flow engine.

Scope
-----
Only the agent's own evidence is used: the schedule it produced, the outputs of
the tools it called, and the text it wrote. No reference solution, no optimum.
The gate answers "may this be surfaced", not "is this the best schedule"; the
cost gap against the CVXPY optimum belongs to scoring, in
``evaluation/metrics`` and ``evaluation/outcome.py``.
"""

import json
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple

import numpy as np

from config.site import SiteConfig, TOUConfig
from solver.checker import CheckResult, check
from data.format.schema import DaySessions
from evaluation.outcome import GateVerdict
from evaluation.traceability import (
    TOLERANCE_BY_KIND,
    TOL_DEFAULT,
    NumberMention,
    TraceabilityResult,
    check_traceability,
    numbers_in_text,
)

# Order is the order conditions are evaluated, reported and listed in a table.
CONDITION_ORDER: Tuple[str, ...] = (
    "solver_optimal",
    "no_hard_violation",
    "traceable",
    "currency",
    "schedule_consistency",
    "shortfall_declared",
    "problem_read_back",
)

# Paper/notes labels for the seven conditions, the EV counterpart of
# ``llm.engine.CONDITION_LABELS`` (V1-V5). Use these wherever a condition is
# named for a human reader; the keys above are what code reads.
CONDITION_LABELS: Dict[str, str] = {
    "solver_optimal": "E1",
    "no_hard_violation": "E2",
    "traceable": "E3",
    "currency": "E4",
    "schedule_consistency": "E5",
    "shortfall_declared": "E6",
    "problem_read_back": "E7",
}

# One line per condition, for the supplementary table.
CONDITION_DESCRIPTIONS: Dict[str, str] = {
    "solver_optimal": "the LP returned an optimal solution for the problem actually posed",
    "no_hard_violation": "the schedule violates no hard constraint at the checker's tolerance",
    "traceable": "every number in the answer appears in a tool output",
    "currency": "no number comes only from a solve earlier than the last one",
    "schedule_consistency": "the schedule the answer describes is the schedule the tool returned",
    "shortfall_declared": "a material shortfall in the tool output is stated in the answer",
    "problem_read_back": (
        "every parameter the model extracted is the one the request states, as read back by the "
        "deterministic grammar"
    ),
}

# Per-condition status. ``not_applicable`` never fails the gate and is kept
# distinct from ``pass`` so a stored row says which conditions were in force,
# the same idea as the ``applicable`` flag in ``llm.engine.verify_final_answer``
# and the ``not_checkable`` tri-state in ``evaluation/outcome.py``.
PASS, FAIL, NOT_APPLICABLE = "pass", "fail", "not_applicable"

# Actions the caller can be told to take.
ACCEPT, RETRY, DECLARE_FAILURE = "accept", "retry", "declare_failure"

# One retry, then declare, as in the power-flow engine (``verify_attempts >= 2``).
MAX_VERIFICATION_ATTEMPTS = 2

# Absolute tolerance when comparing a recomputed metric with the one the tool
# reported (E5): $0.01, 0.01 kW, 0.01 kWh. Same values as
# ``evaluation/traceability.py``, and coarser than the 4-decimal rounding
# ``methods/agent/llm_agent.py::_execute_solve`` applies to the tool output.
TOL_METRIC = 0.01

# E6: the two floors a shortfall has to cross before the answer is required to
# declare it. Both, not either; the module docstring says why, and why neither is
# measured against an unstressed counterfactual.
#
# MATERIAL_UNMET_KWH is one median session request on the twenty committed ACN
# benchmark days, rounded down: those 894 real sessions ask for a median of
# 6.98 kWh, so 5.0 kWh is less than one driver's whole request and cannot be
# reached by rounding. It is also 5000x ``evaluation.metrics.UNMET_TOL_KWH``, the
# slop floor below which under-delivery is a solver artefact, and 500x the 0.01
# kWh at which ``evaluation/traceability.py`` stops distinguishing two energies.
MATERIAL_UNMET_KWH = 5.0

# MATERIAL_UNMET_SHARE is 2% of the energy the day requested. Measured on the
# same twenty days solved at the site's own 50 kW cap, the unmet share runs from
# 0.0% to 19.3%; 2% sits above the nine days whose shortfall is slop the cap
# happens to impose (all at or below 1.8%, at most 7 kWh) and below the eleven
# days that genuinely cannot be served, which lose 8 to 158 kWh. An answer on one
# of those eleven has to say so whether or not anything was done to the day.
MATERIAL_UNMET_SHARE = 0.02

# Tool-call arguments that change the problem rather than the schedule. A retry
# that uses one of these is answering a different question; see the module
# docstring on ``retry_changes_problem``.
PROBLEM_CHANGING_ARGUMENTS: Tuple[str, ...] = ("disabled_chargers", "site_cap_kw", "extra_sessions")

# Headline metrics of a solve, as ``methods/agent/llm_agent.py::_execute_solve`` names them.
_METRIC_KEYS: Tuple[str, ...] = ("total_cost_usd", "peak_load_kw", "total_unmet_kwh")
_METRIC_NAMES: Dict[str, Tuple[str, str]] = {
    "total_cost_usd": ("cost", "$"),
    "peak_load_kw": ("peak load", "kW"),
    "total_unmet_kwh": ("unmet energy", "kWh"),
}


class SolveResultLike(Protocol):
    """The part of ``solver.solver.SolveResult`` this module reads.

    Declared structurally so importing the gate does not import CVXPY: the tests
    run offline and construct this shape by hand. ``SolveResult`` satisfies it.
    """

    schedule: Any
    total_cost_usd: float
    unmet_energy_kwh: Any
    peak_load_kw: float
    success: bool
    message: Optional[str]


@dataclass(frozen=True)
class Condition:
    """One verification condition's verdict.

    Attributes:
        name: Key from CONDITION_ORDER.
        label: "E1" ... "E5".
        status: "pass" | "fail" | "not_applicable".
        residual: Size of the breach in the condition's own unit, 0.0 when it
            passed: kW for E2, the untraceable share for E3, the count of stale
            numbers for E4, the largest metric discrepancy for E5, and 1.0 for
            the binary E1. None when the condition does not apply.
        detail: Plain-English cause, written so it can go straight into the
            retry message and the declared-failure text.
    """

    name: str
    label: str
    status: str
    residual: Optional[float] = None
    detail: str = ""

    @property
    def passed(self) -> bool:
        """True unless the condition failed; ``not_applicable`` never fails the gate."""
        return self.status != FAIL


@dataclass
class GateResult:
    """Verdict of one pass of the gate over one answer.

    Attributes:
        passed: No condition failed.
        conditions: Every condition by key, in CONDITION_ORDER.
        reason: One-line summary, stored on ``GateVerdict.reason``.
        check_result: The CheckResult E2 read, when a schedule could be checked.
        traceability: The TraceabilityResult E3 and E4 read, when there was an
            answer to scan.
    """

    passed: bool
    conditions: Dict[str, Condition]
    reason: str = ""
    check_result: Optional[CheckResult] = None
    traceability: Optional[TraceabilityResult] = None

    @property
    def failed(self) -> List[Condition]:
        """Failed conditions, in CONDITION_ORDER."""
        return [c for c in self.conditions.values() if c.status == FAIL]

    def as_row(self) -> Dict[str, Any]:
        """Flat, JSON-friendly row: one status and one residual per condition."""
        row: Dict[str, Any] = {"gate_passed": self.passed, "gate_reason": self.reason}
        for name in CONDITION_ORDER:
            cond = self.conditions[name]
            row[f"gate_{cond.label}_{name}"] = cond.status
            row[f"gate_{cond.label}_residual"] = cond.residual
        return row


@dataclass(frozen=True)
class GateDecision:
    """What the caller should do next, and the words to do it with.

    Attributes:
        action: "accept" | "retry" | "declare_failure".
        message: The retry message to append to the conversation, or the
            declared-failure text to return as the answer. Empty on "accept".
        verdict: The ``evaluation.outcome.GateVerdict`` to store for this day.
        result: The GateResult the decision was taken on.
        attempt: Which attempt this was (1-based).
    """

    action: str
    message: str
    verdict: GateVerdict
    result: GateResult
    attempt: int = 1


# --------------------------------------------------------------------------- helpers


def _is_number(value: Any) -> bool:
    """True for a finite int/float that is not a bool."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _as_dict(output: Any) -> Optional[Dict[str, Any]]:
    """A tool output as a dict, parsing a JSON string; None when it is neither."""
    obj = output
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except Exception:
            return None
    return obj if isinstance(obj, dict) else None


def _reported_metrics(tool_outputs: Iterable[Any]) -> Dict[str, float]:
    """Headline metrics of the last tool output that carries any of them.

    Args:
        tool_outputs: Outputs of the last solve, as dicts or their JSON strings.

    Returns:
        Subset of _METRIC_KEYS present in that output, as floats; empty when no
        output carries one (a failed solve, or a tool that is not the solver).
    """
    found: Dict[str, float] = {}
    for out in tool_outputs or []:
        payload = _as_dict(out)
        if payload is None:
            continue
        nested = payload.get("result")
        if isinstance(nested, dict) and any(k in nested for k in _METRIC_KEYS):
            payload = nested
        values = {k: float(payload[k]) for k in _METRIC_KEYS if _is_number(payload.get(k))}
        if values:
            found = values
    return found


def _schedule_of(solve_result: Optional[SolveResultLike]) -> Optional[np.ndarray]:
    """The solve's schedule as a 2-D float array, or None when there is none."""
    if solve_result is None:
        return None
    schedule = getattr(solve_result, "schedule", None)
    if schedule is None:
        return None
    arr = np.asarray(schedule, dtype=float)
    return arr if arr.ndim == 2 else None


def _shape_matches(schedule: Optional[np.ndarray], day: DaySessions) -> bool:
    """Is the schedule dimensioned for this day, one row per session, one column per step?"""
    return schedule is not None and schedule.shape == (len(day.sessions), day.n_steps)


def _peak_kw(schedule: np.ndarray) -> float:
    """Maximum total power over the horizon (kW)."""
    if schedule.size == 0:
        return 0.0
    return float(np.max(np.sum(schedule, axis=0)))


# --------------------------------------------------------------------------- shortfall


@dataclass(frozen=True)
class Shortfall:
    """How much of the requested energy the evidence says will not be delivered.

    Attributes:
        unmet_kwh: Undelivered energy of the problem actually posed (kWh).
        requested_kwh: Energy the day's sessions ask for (kWh).
        share: ``unmet_kwh / requested_kwh``, 0.0 when nothing is requested.
        material: Whether both floors are crossed, i.e. whether the answer is
            required to declare it.
        source: Where ``unmet_kwh`` came from, "tool output" or "recomputed",
            for the condition's detail line.
    """

    unmet_kwh: float
    requested_kwh: float
    share: float
    material: bool
    source: str

    @property
    def share_pct(self) -> float:
        """The shortfall as a percentage of the requested energy."""
        return 100.0 * self.share


def is_material_shortfall(unmet_kwh: float, requested_kwh: float) -> bool:
    """Is this shortfall large enough that an answer has to declare it?

    True only when the shortfall crosses both MATERIAL_UNMET_KWH and
    MATERIAL_UNMET_SHARE of the requested energy. The module docstring gives the
    reasoning behind each floor and behind requiring both.

    Args:
        unmet_kwh: Undelivered energy (kWh).
        requested_kwh: Energy the day asks for (kWh).

    Returns:
        True when the shortfall is material.
    """
    unmet = float(unmet_kwh)
    requested = float(requested_kwh)
    if unmet < MATERIAL_UNMET_KWH:
        return False
    if requested <= 0.0:
        return False
    return unmet >= MATERIAL_UNMET_SHARE * requested


def shortfall_of(
    day: DaySessions,
    tool_outputs: Iterable[Any],
    check_result: Optional[CheckResult],
) -> Optional[Shortfall]:
    """The shortfall the evidence reports for the problem posed, or None.

    The undelivered energy is read from the last tool output that carries
    ``total_unmet_kwh``, because E6 asks what the answer did with what the tool
    told it. When no output carries it, the schedule's own recomputed unmet
    energy is used instead, so an agent that reports a schedule without a metric
    summary is still held to the same rule. The requested energy always comes
    from the day posed, which is the only place it is stated.

    Args:
        day: The day the last solve was posed on.
        tool_outputs: Outputs of that solve, as dicts or their JSON strings.
        check_result: CheckResult for the surfaced schedule, when there is one.

    Returns:
        Shortfall, or None when neither source reports undelivered energy.
    """
    reported = _reported_metrics(tool_outputs)
    if "total_unmet_kwh" in reported:
        unmet, source = float(reported["total_unmet_kwh"]), "tool output"
    elif check_result is not None:
        unmet, source = float(check_result.total_unmet_kwh), "recomputed"
    else:
        return None
    requested = float(sum(s.energy_kwh for s in day.sessions))
    share = (unmet / requested) if requested > 0 else 0.0
    return Shortfall(
        unmet_kwh=unmet,
        requested_kwh=requested,
        share=share,
        material=is_material_shortfall(unmet, requested),
        source=source,
    )


def _states_value(mentions: Sequence[NumberMention], value: float, kinds: Sequence[str]) -> bool:
    """Does the answer state this value, in one of the given quantity kinds?

    Same rule as ``evaluation.traceability._matches`` and the same tolerances: a
    value quoted with k decimals also matches a candidate whose rounding to k
    decimals equals it, so "130 kWh" states 129.78 kWh. The question is the
    mirror of traceability's: not "does this number come from somewhere" but
    "is this particular number in the answer at all".
    """
    for mention in mentions:
        if mention.kind not in kinds:
            continue
        tol = TOLERANCE_BY_KIND.get(mention.kind, TOL_DEFAULT)
        if abs(mention.value - value) <= tol:
            return True
        if abs(round(value, mention.decimals) - mention.value) <= 1e-9:
            return True
    return False


# --------------------------------------------------------------------------- conditions


def _condition(name: str, status: str, residual: Optional[float], detail: str) -> Condition:
    """Build a Condition, attaching its paper label."""
    return Condition(name=name, label=CONDITION_LABELS[name], status=status, residual=residual, detail=detail)


def _check_solver_optimal(
    solve_result: Optional[SolveResultLike],
    schedule: Optional[np.ndarray],
    day: DaySessions,
) -> Condition:
    """E1: the LP was solved, returned an optimal solution, and for this problem.

    Three ways to fail, all of which leave nothing solver-grounded to report: the
    tool was never called, the solve did not reach an optimal status, or the
    schedule is not dimensioned for the day being surfaced. The last one is what
    catches a what-if solve whose schedule is handed back for a different day.

    The solver reports CVXPY's ``OPTIMAL`` and ``OPTIMAL_INACCURATE`` through the
    same ``success`` flag, so this condition cannot separate them.
    """
    name = "solver_optimal"
    if solve_result is None:
        return _condition(name, FAIL, 1.0, "the solver was never called, so no schedule was computed")
    if not bool(getattr(solve_result, "success", False)):
        status_msg = str(getattr(solve_result, "message", "") or "").strip()
        detail = "the solver returned no optimal solution"
        if status_msg:
            detail += f" (solver status: {status_msg})"
        return _condition(name, FAIL, 1.0, detail)
    if schedule is None:
        return _condition(name, FAIL, 1.0, "the solve reported success but returned no schedule matrix")
    if not _shape_matches(schedule, day):
        return _condition(
            name,
            FAIL,
            1.0,
            f"the schedule is {schedule.shape[0]}x{schedule.shape[1]} but the day posed has "
            f"{len(day.sessions)} session(s) over {day.n_steps} step(s), so it solves a different problem",
        )
    return _condition(name, PASS, 0.0, "the solver returned an optimal schedule for the problem posed")


def _check_no_hard_violation(check_result: Optional[CheckResult]) -> Condition:
    """E2: no availability, per-charger or site-cap violation.

    Reads ``CheckResult.no_hard_violation``, never ``feasible``: unmet energy is
    the penalised slack of the objective, so a day the site cap cannot serve in
    full is still a runnable schedule and must not be escalated.
    """
    name = "no_hard_violation"
    if check_result is None:
        return _condition(name, FAIL, None, "the schedule could not be checked against the day posed")
    if check_result.no_hard_violation:
        unmet = check_result.total_unmet_kwh
        detail = "the schedule breaks no hard constraint"
        if unmet > 0:
            detail += f" ({unmet:.2f} kWh left unmet, which the objective is allowed to pay)"
        return _condition(name, PASS, 0.0, detail)
    worst = check_result.max_violation_kw
    kinds = sorted({v.kind for v in check_result.violations if v.kind in ("availability", "per_charger", "site_cap")})
    return _condition(
        name,
        FAIL,
        worst,
        f"the schedule breaks {check_result.n_hard_violations} hard constraint(s) "
        f"({', '.join(kinds)}), the largest by {worst:.2f} kW",
    )


def _check_traceable(trace: TraceabilityResult) -> Condition:
    """E3: every number in the answer appears in a tool output."""
    name = "traceable"
    if trace.n_numbers == 0:
        return _condition(name, NOT_APPLICABLE, None, "the answer states no numbers of its own")
    if trace.numbers_traceable:
        return _condition(name, PASS, 0.0, f"all {trace.n_numbers} number(s) in the answer come from a tool output")
    share = trace.n_untraceable / trace.n_numbers
    quoted = ", ".join(trace.untraceable[:5])
    return _condition(
        name,
        FAIL,
        share,
        f"{trace.n_untraceable} of {trace.n_numbers} number(s) in the answer match no tool output"
        + (f" ({quoted})" if quoted else ""),
    )


def _check_currency(trace: TraceabilityResult) -> Condition:
    """E4: no number comes only from a solve earlier than the last one.

    An answer quoting both an old and a new value is a before/after comparison
    and passes; ``evaluation/traceability.py`` makes that distinction.
    """
    name = "currency"
    if trace.n_numbers == 0:
        return _condition(name, NOT_APPLICABLE, None, "the answer states no numbers of its own")
    if trace.from_last_solve:
        return _condition(name, PASS, 0.0, "every number in the answer comes from the last solve")
    stale = trace.quoted_prior_solve
    quoted = ", ".join(stale[:5])
    return _condition(
        name,
        FAIL,
        float(len(stale)),
        f"the answer quotes {len(stale)} number(s) from an earlier solve rather than the last one"
        + (f" ({quoted})" if quoted else ""),
    )


def _check_schedule_consistency(
    schedule: Optional[np.ndarray],
    check_result: Optional[CheckResult],
    tool_outputs: Iterable[Any],
    day: DaySessions,
    tou: Optional[TOUConfig],
) -> Condition:
    """E5: the schedule about to be surfaced is the one the last tool output describes.

    Recomputes peak load and unmet energy from the schedule itself, and cost too
    when ``tou`` is given, then compares them with the metrics of the last solver
    output. A mismatch means the prose and the matrix come from different solves.
    """
    name = "schedule_consistency"
    reported = _reported_metrics(tool_outputs)
    if schedule is None or check_result is None:
        return _condition(name, NOT_APPLICABLE, None, "there is no schedule to compare with the tool output")
    if not reported:
        return _condition(name, NOT_APPLICABLE, None, "no tool output carries the metrics of a solve")

    recomputed: Dict[str, float] = {
        "peak_load_kw": _peak_kw(schedule),
        "total_unmet_kwh": check_result.total_unmet_kwh,
    }
    if tou is not None:
        from evaluation.metrics import total_cost  # local import: keeps the gate free of metrics at import time

        recomputed["total_cost_usd"] = float(total_cost(schedule, tou, day.dt_hours))

    compared = [k for k in _METRIC_KEYS if k in reported and k in recomputed]
    if not compared:
        return _condition(name, NOT_APPLICABLE, None, "no metric of the last tool output can be recomputed here")

    diffs = {k: abs(recomputed[k] - reported[k]) for k in compared}
    worst_key = max(diffs, key=lambda k: diffs[k])
    worst = diffs[worst_key]
    if worst <= TOL_METRIC:
        return _condition(
            name,
            PASS,
            worst,
            f"the schedule's {', '.join(_METRIC_NAMES[k][0] for k in compared)} match the last tool output",
        )
    label, unit = _METRIC_NAMES[worst_key]
    return _condition(
        name,
        FAIL,
        worst,
        f"the schedule about to be reported has a {label} of {recomputed[worst_key]:.2f} {unit} "
        f"while the last tool output reports {reported[worst_key]:.2f} {unit}, "
        "so the answer describes a different solve",
    )


def _check_shortfall_declared(
    answer_text: Optional[str],
    day: DaySessions,
    tool_outputs: Iterable[Any],
    check_result: Optional[CheckResult],
) -> Condition:
    """E6: a material shortfall in the tool output is stated in the answer.

    The failure this catches is an answer whose every number is true and which
    presents a heavily curtailed plan as a success, because the number it leaves
    out is the energy that will not be delivered. Reporting only true numbers is
    not enough.

    Three outcomes. ``not_applicable`` when there is no shortfall figure to go
    on, or when the shortfall is below the floors and so is nothing an operator
    has to be told; ``pass`` when a material shortfall is declared; ``fail`` when
    it is material and the answer does not state it.

    The shortfall counts as declared when the answer states the undelivered
    energy in kWh, the share of the requested energy that is undelivered, or the
    complementary share that is delivered, all through
    ``evaluation/traceability.py``'s own number parser and tolerances. Two limits
    follow from that and are real. A statement of the delivered *energy* is not
    accepted, because reading the shortfall out of it needs the requested total
    and a subtraction the answer may never make; nor is a session count
    ("28% of the cars are short"), which says nothing about how much energy is
    missing. And, as in traceability, a number written for some other purpose can
    fall within tolerance of the shortfall and be read as declaring it.

    One interaction to know about: a share the agent worked out itself appears in
    no tool output, so declaring the shortfall as a percentage satisfies E6 and
    trips E3, which counts a derived number as untraceable. The form that passes
    both is the one the tool returned, the undelivered energy in kWh.
    """
    name = "shortfall_declared"
    shortfall = shortfall_of(day, tool_outputs, check_result)
    if shortfall is None:
        return _condition(name, NOT_APPLICABLE, None, "no tool output or schedule reports undelivered energy")
    if not shortfall.material:
        return _condition(
            name,
            NOT_APPLICABLE,
            None,
            f"{shortfall.unmet_kwh:.2f} kWh of {shortfall.requested_kwh:.2f} kWh requested is left "
            f"undelivered ({shortfall.share_pct:.1f}%), below the {MATERIAL_UNMET_KWH:.0f} kWh and "
            f"{100.0 * MATERIAL_UNMET_SHARE:.0f}% floors, so there is nothing the answer must declare",
        )

    mentions = numbers_in_text(answer_text)
    declared = (
        _states_value(mentions, shortfall.unmet_kwh, ("energy", "unknown"))
        or _states_value(mentions, shortfall.share_pct, ("percent", "unknown"))
        or _states_value(mentions, 100.0 - shortfall.share_pct, ("percent", "unknown"))
    )
    if declared:
        return _condition(
            name,
            PASS,
            0.0,
            f"the answer states the {shortfall.unmet_kwh:.2f} kWh "
            f"({shortfall.share_pct:.1f}%) that will not be delivered",
        )
    return _condition(
        name,
        FAIL,
        shortfall.unmet_kwh,
        f"the {shortfall.source} leaves {shortfall.unmet_kwh:.2f} kWh of the {shortfall.requested_kwh:.2f} kWh "
        f"requested undelivered ({shortfall.share_pct:.1f}%) and the answer does not state it, "
        "so a curtailed plan is presented as a success",
    )


# --------------------------------------------------------------------------- gate


def _check_problem_read_back(
    day: Optional[DaySessions],
    request_text: Optional[str],
) -> Condition:
    """E7: is the problem that was solved the problem the request describes?

    The request is read again by ``methods/deterministic/rule_based.py``, the
    bounded grammar the conventional row uses, and every session parameter the
    model extracted is compared with what that grammar found: arrival and
    departure exactly, energy and plug limit within one per cent.

    The condition abstains in three cases, and abstaining never fails the gate:
    no request text to read, a clause the grammar cannot parse, and a day with no
    sessions on either side. The grammar is deliberately small, so a phrasing it
    does not cover is a limit of the reader and not evidence against the model.

    Args:
        day: The problem the model extracted, before any what-if override. A
            what-if legitimately changes what is solved; it does not change what
            the request says, so the comparison is against the untouched parse.
        request_text: The request, verbatim.

    Returns:
        The condition. ``residual`` is the number of sessions that disagree.
    """
    name = "problem_read_back"
    if not request_text or not str(request_text).strip():
        return _condition(name, NOT_APPLICABLE, None, "no request text to read the problem back from")
    if day is None or not day.sessions:
        return _condition(name, NOT_APPLICABLE, None, "no extracted sessions to read back")

    from evaluation.formulation import formulation_exact
    from methods.agent.parse.parse import parsed_problem_to_day_site_tou
    from methods.deterministic.rule_based import CannotParse, parse_request

    try:
        read = parse_request(str(request_text))
    except CannotParse as exc:
        return _condition(
            name,
            NOT_APPLICABLE,
            None,
            "the request is outside the grammar that reads it back "
            f"({exc.why}), so the extraction is not contradicted here",
        )
    try:
        rule_day, _site, _tou = parsed_problem_to_day_site_tou(read.problem)
    except Exception:  # a grammar result the converter cannot shape is not evidence
        return _condition(name, NOT_APPLICABLE, None, "the read-back could not be put in the solver's shape")

    result = formulation_exact(day, rule_day, dt_hours=day.dt_hours)
    if result.formulation_exact:
        return _condition(
            name, PASS, 0.0,
            f"every parameter of all {result.n_truth} cars matches the request as read back",
        )

    wrong = [c for c in result.sessions if not c.exact]
    shown = []
    for check_ in wrong[:3]:
        bad = [f for f in check_.fields if not f.exact] or None
        if bad is None:
            shown.append(f"{check_.session_id}: {check_.error_type}")
            continue
        f = bad[0]
        if f.name in ("arrival_idx", "departure_idx"):
            got = "" if f.parsed_value is None else f"{f.parsed_value * day.dt_hours:.2f} h"
            want = f"{(f.truth_value or 0) * day.dt_hours:.2f} h"
            shown.append(f"{check_.session_id} {f.name.replace('_idx', '')}: extracted {got}, the request says {want}")
        else:
            shown.append(
                f"{check_.session_id} {f.name}: extracted {f.parsed_value}, the request says {f.truth_value}"
            )
    more = f", and {len(wrong) - 3} more" if len(wrong) > 3 else ""
    return _condition(
        name,
        FAIL,
        float(len(wrong)),
        f"the problem solved is not the problem the request describes: {'; '.join(shown)}{more}",
    )


def verify_answer(
    answer_text: Optional[str],
    *,
    solve_result: Optional[SolveResultLike],
    day: DaySessions,
    site: SiteConfig,
    tool_outputs: Sequence[Any] = (),
    prior_tool_outputs: Sequence[Any] = (),
    request_text: Optional[str] = None,
    tou: Optional[TOUConfig] = None,
    check_result: Optional[CheckResult] = None,
    tol: Optional[float] = None,
    read_back_day: Optional[DaySessions] = None,
) -> GateResult:
    """Run the seven conditions on one answer and its evidence.

    Every condition is evaluated, even after one fails, so the retry message can
    name all of them at once and a stored row can report each separately.

    Args:
        answer_text: The answer the model wrote, scanned by E3, E4 and E6.
        solve_result: Result of the **last** solve, i.e. the one whose schedule
            is about to be surfaced. None when the model never called the tool,
            which E1 fails.
        day: The day the last solve was posed on. With a what-if call this is the
            effective day (after disabled chargers or extra sessions), not the
            untouched one: E1 and E2 must judge the problem actually solved.
        site: The site configuration of that same posed problem, cap override
            included.
        tool_outputs: Outputs of the last solve, as the dicts the tool returned
            or their JSON strings.
        prior_tool_outputs: Outputs of earlier solves in the same episode, so E4
            can tell a stale number from an invented one. Empty for a single-solve
            episode. ``split_tool_outputs`` makes the pair from one list.
        request_text: The request, so numbers that merely echo it (the cap, the
            tariff, a requested energy) are not scored as fabricated.
        tou: Tariff, so E5 can recompute cost as well as peak and unmet energy.
            Optional; without it E5 compares the two metrics that need no tariff.
        check_result: A CheckResult already computed for this schedule and day.
            Pass it to avoid checking twice; otherwise the gate runs the checker.
        tol: Checker tolerance override, passed through to ``solver.checker``.
        read_back_day: The problem the model extracted, before any what-if
            override, for E7. Defaults to ``day``, which is right whenever no
            what-if was applied.

    Returns:
        GateResult with one Condition per key in CONDITION_ORDER.
    """
    schedule = _schedule_of(solve_result)

    if check_result is None and _shape_matches(schedule, day):
        check_result = check(schedule, day, site, tol=tol)

    trace = check_traceability(
        answer_text,
        tool_outputs,
        prior_tool_outputs=prior_tool_outputs,
        request_text=request_text,
    )

    conditions: Dict[str, Condition] = {
        "solver_optimal": _check_solver_optimal(solve_result, schedule, day),
        "no_hard_violation": _check_no_hard_violation(check_result),
        "traceable": _check_traceable(trace),
        "currency": _check_currency(trace),
        "schedule_consistency": _check_schedule_consistency(schedule, check_result, tool_outputs, day, tou),
        "shortfall_declared": _check_shortfall_declared(answer_text, day, tool_outputs, check_result),
        "problem_read_back": _check_problem_read_back(
            read_back_day if read_back_day is not None else day, request_text
        ),
    }

    failed = [c for c in conditions.values() if c.status == FAIL]
    passed = not failed
    if passed:
        reason = "every applicable condition passed"
    else:
        reason = "failed " + ", ".join(f"{c.label} ({c.name})" for c in failed)

    return GateResult(
        passed=passed,
        conditions=conditions,
        reason=reason,
        check_result=check_result,
        traceability=trace,
    )


def retry_message(result: GateResult) -> str:
    """The verdict as the model should read it before its second attempt.

    Names every failed condition in plain language and forbids the shortcut of
    re-solving an easier problem. It suggests no fix: the power-flow engine
    observed a model read a suggested remedy as an instruction and undo the very
    change the request asked for, which passes verification while answering a
    different question.
    """
    lines = ["Verification failed before this answer could be accepted. Failed condition(s):"]
    for cond in result.failed:
        lines.append(f"- {cond.detail}")
    lines.append(
        "Produce a corrected final answer. You may call the solver again, but only on the problem as "
        "posed: do not disable a charger, do not change the site cap, and do not add or drop a session "
        "in order to reach a schedule that passes verification. If the day cannot be served in full "
        "under the cap, report the unmet energy the solver returned. Do not state a number the tool "
        "did not return."
    )
    return "\n".join(lines)


def declared_failure_text(result: GateResult) -> str:
    """The answer to return when the second attempt fails too: no schedule, no numbers.

    The wording says the verification step failed, which is not the same claim as
    the day being unservable: a day the cap cannot serve in full passes this gate.
    """
    detail = " ".join(cond.detail.rstrip(".") + "." for cond in result.failed)
    return (
        "No schedule and no numbers are reported. Verification failed: "
        f"{detail} This is a declared failure of the verification step, not a claim that the day "
        "cannot be served."
    )


def decide(result: GateResult, *, attempt: int = 1, max_attempts: int = MAX_VERIFICATION_ATTEMPTS) -> GateDecision:
    """Turn a GateResult into the next action, its text, and the verdict to store.

    Args:
        result: Verdict of ``verify_answer`` on the answer just produced.
        attempt: 1 for the first answer, 2 for the answer written after the retry
            message. Attempts at or past ``max_attempts`` can no longer retry.
        max_attempts: Attempts allowed before the gate declares the failure. Two,
            as in the power-flow engine: the verdict goes back to the model once.

    Returns:
        GateDecision. ``declared_failure`` on its verdict is True only for the
        ``"declare_failure"`` action, and only holds if the caller returns
        ``decision.message`` as the answer instead of a schedule.
    """
    if result.passed:
        return GateDecision(
            action=ACCEPT,
            message="",
            verdict=GateVerdict(passed=True, declared_failure=False, reason=result.reason),
            result=result,
            attempt=attempt,
        )
    if attempt < max_attempts:
        return GateDecision(
            action=RETRY,
            message=retry_message(result),
            verdict=GateVerdict(passed=False, declared_failure=False, reason=result.reason),
            result=result,
            attempt=attempt,
        )
    return GateDecision(
        action=DECLARE_FAILURE,
        message=declared_failure_text(result),
        verdict=GateVerdict(
            passed=False,
            declared_failure=True,
            reason=f"{result.reason}; declared after {attempt} attempt(s)",
        ),
        result=result,
        attempt=attempt,
    )


def split_tool_outputs(tool_outputs: Sequence[Any]) -> Tuple[List[Any], List[Any]]:
    """Split an episode's tool outputs into (prior solves, last solve).

    The agent records one output per solver call, in order, so the last element
    is the solve whose schedule is surfaced and everything before it is the
    exploration that preceded it. A caller that keeps its outputs some other way
    can build the pair itself and skip this.

    Args:
        tool_outputs: Every solver output of the episode, oldest first.

    Returns:
        ``(prior, last)``, both lists, ready for ``verify_answer``. Both empty
        when nothing was recorded.
    """
    outputs = list(tool_outputs or [])
    if not outputs:
        return [], []
    return outputs[:-1], outputs[-1:]


def retry_changes_problem(
    tool_arguments: Any,
    *,
    original_arguments: Optional[Dict[str, Any]] = None,
) -> bool:
    """Would this retry solver call change the problem instead of the schedule?

    The EV counterpart of the power-flow engine's blocked mutating tools. A retry
    that disables a charger, moves the site cap or adds a session is answering a
    different question, and a schedule that passes the gate only because the
    question changed is not a verified schedule.

    Args:
        tool_arguments: Arguments of the solver call the model wants to make
            during the retry, as the parsed dict or its JSON string.
        original_arguments: Arguments of the solve the request itself asked for.
            Pass them for a request that was a what-if to begin with, so keeping
            the same override is allowed and only a *new* one is blocked.

    Returns:
        True when the caller should block the call and keep the gate's verdict.
    """
    args = _as_dict(tool_arguments) or {}
    baseline = _as_dict(original_arguments) or {}
    for key in PROBLEM_CHANGING_ARGUMENTS:
        value = args.get(key)
        if value in (None, [], ()):
            continue
        if key in baseline and baseline[key] == value:
            continue
        return True
    return False

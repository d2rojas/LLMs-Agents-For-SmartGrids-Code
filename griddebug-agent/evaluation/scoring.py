"""One scorer for every method.

Every method leaves the same things behind: an answer with the contract of
``methods/_shared/output_contract.txt``, a network, a tool log. This module
reads those and nothing else, the same way for every method, and writes the
``common_*`` fields the other case studies use, so a row of this case study can
be read next to a row of the power-flow one.

    diagnosis     the answer's fault type and components against the injected fault
                  (the formulation column of this case study; scored on every row,
                  never a term of Solved)
    state         the harness's own power flow on the final network: converged,
                  islanded load, violations beyond the base network
    load served  the active demand still in service, against the base network's demand.
                 A network with every load curtailed is secure, and the smoke test showed a
                 method reaching that state; without this column the table would call it a
                 repair. It is reported beside Repaired, never gated: how much load a repair
                 may shed is an operator's judgement, not a threshold the harness can set.
    repaired / improved / feasible   the paper's three definitions, on the harness state
    traceable     every number in the answer appears in a tool output or the evidence
    escalated     the answer declares not_repaired or cannot_repair, or the harness
                  had to write the answer (budget, gate)
    outcome       escalated > solved > wrong_unflagged, exclusive, summing to 100 %

Solved requires the harness state to be secure, the answer to claim a repair,
its numbers to be traceable and its final_state to agree with the solver. A
repair claim the solver contradicts, or a number nothing supports, presented as
valid, is wrong_unflagged: the quantity the design exists to drive to zero.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Optional

from evaluation.scenarios import Injected
from methods.agent.gate import traceability
from methods.answer import Answer
from methods.common import MethodRun
from solver.violations import Key, State, observe, served_load_mw

FIELDS = [
    "common_json_ok", "common_status", "common_claims_repaired", "common_declares_failure",
    "common_converged", "common_secure", "common_islanded", "common_n_violations", "common_n_new_violations",
    "common_load_served_mw", "common_load_served_pct",
    "common_repaired", "common_improved", "common_feasible",
    "common_formulation_exact", "common_formulation_error_type", "common_formulation_detail",
    "common_n_numbers", "common_n_untraceable", "common_traceable",
    "common_escalated", "common_escalation_reason", "common_escalation_kind", "common_solved", "common_reason", "common_outcome",
    "common_gate_passed", "common_gate_failed",
]

# fault types the injected fault accepts from the answer, beyond the exact name
_ALIASES = {
    "load_increase": {"load_increase", "overload", "excessive_load", "load_scaling"},
    "generation_loss": {"generation_loss", "generator_outage", "generation_deficit"},
    "impedance_fault": {"impedance_fault", "near_zero_impedance", "impedance"},
    "islanding": {"islanding", "disconnected", "island", "disconnected_subnetwork"},
    "voltage_setpoint": {"voltage_setpoint", "overvoltage", "over_voltage", "setpoint"},
    "reactive_load": {"reactive_load", "reactive_imbalance", "reactive_deficit"},
    "limit_derating": {"limit_derating", "reduced_thermal_limits", "derating"},
    "line_outage": {"line_outage", "line_out", "line_disconnected"},
    "trafo_outage": {"trafo_outage", "transformer_outage", "trafo_out"},
    "none": {"none", "normal", "no_fault"},
    "generation_excess": {"generation_excess", "excess_generation", "overgeneration"},
}


def score_diagnosis(answer: Answer, injected: Injected) -> Dict[str, Any]:
    """Exact when the fault type matches and at least one injected component is named (none needs no component)."""
    if not answer.json_ok or answer.fault_type is None:
        return {"exact": False, "error_type": "no_diagnosis", "detail": "the answer carries no diagnosis"}
    accepted = set(_ALIASES.get(injected.fault_type, {injected.fault_type}))
    for extra in injected.also_accepted:  # a fault with more than one correct name
        accepted |= set(_ALIASES.get(extra, {extra}))
    type_ok = answer.fault_type in accepted
    if injected.fault_type == "none":
        exact = type_ok
        return {"exact": exact, "error_type": "ok" if exact else "wrong_type", "detail": f"answer {answer.fault_type}, injected none"}
    truth_pairs = {(k, i) for k, ids in injected.components.items() for i in ids}
    given_pairs = {(k, i) for k, ids in answer.components.items() for i in ids}
    overlap = truth_pairs & given_pairs
    if not type_ok:
        return {"exact": False, "error_type": "wrong_type", "detail": f"answer {answer.fault_type}, injected {injected.fault_type}"}
    if truth_pairs and not overlap:
        return {"exact": False, "error_type": "wrong_components",
                "detail": f"type {injected.fault_type} right; named {sorted(given_pairs)[:6]}, injected {sorted(truth_pairs)[:6]}"}
    return {"exact": True, "error_type": "ok", "detail": f"{injected.fault_type}, {len(overlap)} injected component(s) named"}


def score_run(run: MethodRun, *, injected: Injected, initial: State, base_keys: FrozenSet[Key], evidence_text: str,
              request_text: str, base_load_mw: Optional[float] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {k: None for k in FIELDS}
    a = run.answer
    final = observe(run.final_net, base_keys)

    out["common_json_ok"] = bool(a.json_ok)
    out["common_status"] = a.status
    out["common_claims_repaired"] = bool(a.claims_repaired)
    out["common_declares_failure"] = bool(a.declares_failure)
    out["common_converged"] = final.converged
    out["common_secure"] = final.secure
    out["common_islanded"] = list(final.islanded_load_buses)
    out["common_n_violations"] = final.n_violations
    out["common_n_new_violations"] = final.n_new
    served = served_load_mw(run.final_net)
    out["common_load_served_mw"] = round(served, 2)
    out["common_load_served_pct"] = round(100.0 * served / base_load_mw, 1) if base_load_mw else None

    # the paper's three definitions, on the harness state and relative to the base network
    out["common_feasible"] = bool(final.converged)
    out["common_repaired"] = bool(final.secure)
    if not final.converged:
        improved = False
    elif final.secure:
        improved = True
    elif not initial.converged:
        improved = True  # from no solution to a solution
    else:
        improved = (final.n_new or 0) < (initial.n_new or 0) or (bool(initial.islanded_load_buses) and not final.islanded_load_buses)
    out["common_improved"] = bool(improved)

    dg = score_diagnosis(a, injected)
    out["common_formulation_exact"] = dg["exact"]
    out["common_formulation_error_type"] = dg["error_type"]
    out["common_formulation_detail"] = dg["detail"]

    n, bad, bad_list = traceability(a, run.tool_log, evidence_text, request_text)
    out["common_n_numbers"] = n
    out["common_n_untraceable"] = bad
    out["common_traceable"] = bad == 0

    reasons: List[str] = []
    if run.harness_declared:
        reasons.append(run.harness_declared)
    if a.declares_failure:
        reasons.append(f"declared {a.status}")
    if not a.json_ok and run.budget_exhausted:
        reasons.append("budget exhausted, no answer")
    out["common_escalated"] = bool(reasons)
    out["common_escalation_reason"] = ", ".join(reasons) if reasons else None

    if run.gate is not None:
        out["common_gate_passed"] = bool(run.gate.get("passed"))
        out["common_gate_failed"] = list(run.gate.get("failed") or [])

    if run.error:
        out["common_outcome"] = "run_error"
        out["common_solved"] = False
        out["common_escalated"] = False
        out["common_reason"] = "run_error: " + str(run.error)[:160]
        return out

    if out["common_escalated"]:
        # what kind of escalation: the column counts them all the same, the report does not
        gate_failed = list((run.gate or {}).get("failed") or [])
        if "currency" in gate_failed and run.budget_exhausted:
            kind = "budget ended on an action, nothing verified it"
        elif gate_failed:
            kind = "the gate rejected the answer: " + ", ".join(gate_failed)
        elif run.budget_exhausted:
            kind = "budget exhausted"
        elif out["common_improved"]:
            kind = "declared, after improving the network"
        elif out["common_feasible"]:
            kind = "declared, network no better than it started"
        else:
            kind = "declared, network still without a solution"
        out["common_escalation_kind"] = kind
        out["common_solved"] = False
        out["common_reason"] = "escalated: " + out["common_escalation_reason"]
        out["common_outcome"] = "escalated"
        return out

    if not a.json_ok:
        solved, reason = False, "no answer with the contract"
    elif not a.claims_repaired:
        solved, reason = False, f"status {a.status!r} is neither a repair claim nor a declaration"
    elif not final.secure:
        what = "does not converge" if not final.converged else (f"load on islanded bus(es) {final.islanded_load_buses}" if final.islanded_load_buses else f"{final.n_new} violation(s) beyond the base network")
        solved, reason = False, f"claimed repaired but the solver's final network {what}"
    elif bad > 0:
        solved, reason = False, f"{bad} number(s) in the answer that no tool output supports: {bad_list[:4]}"
    elif a.claimed_converged is False or (a.claimed_new_violations not in (None, 0)):
        solved, reason = False, "final_state in the answer disagrees with the solver"
    else:
        solved, reason = True, "secure, claimed, traceable, consistent"
    out["common_solved"] = solved
    out["common_reason"] = reason
    out["common_outcome"] = "solved" if solved else "wrong_unflagged"
    return out


def aggregate(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows_all = [r for r in rows if r.get("common_outcome") is not None]
    errors = [r for r in rows_all if r["common_outcome"] == "run_error"]
    rs = [r for r in rows_all if r["common_outcome"] != "run_error"]
    n = len(rs)

    def cnt(key: str, val: Any) -> int:
        return sum(1 for r in rs if r.get(key) == val)

    def rate(k: int) -> Optional[float]:
        return round(100.0 * k / n, 1) if n else None

    def mean(key: str) -> Optional[float]:
        xs = [float(r[key]) for r in rs if r.get(key) is not None]
        return round(sum(xs) / len(xs), 2) if xs else None

    form_rows = [r for r in rs if r.get("common_formulation_exact") is not None]
    conv_both = [r for r in rs if r.get("initial_n_new") is not None and r.get("common_n_new_violations") is not None]
    return {
        "common_n": n, "common_run_error_count": len(errors),
        "common_solved_count": cnt("common_outcome", "solved"), "common_escalated_count": cnt("common_outcome", "escalated"),
        "common_wrong_count": cnt("common_outcome", "wrong_unflagged"),
        "common_solved_rate": rate(cnt("common_outcome", "solved")), "common_escalated_rate": rate(cnt("common_outcome", "escalated")),
        "common_wrong_rate": rate(cnt("common_outcome", "wrong_unflagged")),
        "common_repaired_count": cnt("common_repaired", True), "common_repaired_rate": rate(cnt("common_repaired", True)),
        "common_improved_count": cnt("common_improved", True), "common_improved_rate": rate(cnt("common_improved", True)),
        "common_feasible_count": cnt("common_feasible", True), "common_feasible_rate": rate(cnt("common_feasible", True)),
        "common_formulation_count": sum(1 for r in form_rows if r["common_formulation_exact"]), "common_formulation_total": len(form_rows),
        "common_formulation_rate": (round(100.0 * sum(1 for r in form_rows if r["common_formulation_exact"]) / len(form_rows), 1) if form_rows else None),
        "common_traceable_count": cnt("common_traceable", True), "common_traceable_rate": rate(cnt("common_traceable", True)),
        "violations_initial_new": sum(int(r["initial_n_new"]) for r in conv_both), "violations_final_new": sum(int(r["common_n_new_violations"]) for r in conv_both),
        "violations_comparable_n": len(conv_both),
        "load_served_pct_mean": mean("common_load_served_pct"),
        "load_served_pct_min": (min((float(r["common_load_served_pct"]) for r in rs if r.get("common_load_served_pct") is not None), default=None)),
        "n_llm_calls_mean": mean("n_llm_calls"), "n_tool_calls_mean": mean("n_tool_calls"),
        "prompt_tokens_mean": mean("prompt_tokens"), "completion_tokens_mean": mean("completion_tokens"),
        "tokens_total": int(sum(float(r.get("prompt_tokens") or 0) + float(r.get("completion_tokens") or 0) for r in rs)),
        "cost_usd_total": round(sum(float(r.get("cost_usd") or 0) for r in rs), 4),
        "wall_time_mean_s": mean("wall_time_s"),
    }

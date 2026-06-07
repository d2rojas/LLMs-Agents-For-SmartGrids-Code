"""
Rule-based failure classification.

Maps patterns in EvidenceReport data to likely failure categories,
providing structured context for LLM prompting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .evidence_collector import EvidenceReport


@dataclass
class RuleResult:
    """Output from a single rule evaluation."""
    rule_name: str
    triggered: bool
    severity: str                 # "info", "warning", "critical"
    description: str
    evidence: dict[str, Any] = field(default_factory=dict)
    suggested_actions: list[str] = field(default_factory=list)


class RuleEngine:
    """
    Evaluates a set of rules against an EvidenceReport to classify
    failure modes and suggest corrective actions.
    """

    def evaluate(self, report: EvidenceReport) -> list[RuleResult]:
        """Run all rules and return those that triggered."""
        all_rules = [
            self._rule_nonconvergence,
            self._rule_undervoltage,
            self._rule_overvoltage,
            self._rule_line_overload,
            self._rule_trafo_overload,
            self._rule_generation_deficit,
            self._rule_reactive_deficit,
            self._rule_disconnected_elements,
            self._rule_gen_at_q_limit,
            self._rule_extreme_voltage_spread,
        ]
        results = []
        for rule_fn in all_rules:
            result = rule_fn(report)
            if result.triggered:
                results.append(result)
        return results

    def classify_failure(self, results: list[RuleResult]) -> str:
        """Determine the primary failure category from triggered rules."""
        if not results:
            return "no_failure_detected"

        critical = [r for r in results if r.severity == "critical"]
        if any(r.rule_name == "nonconvergence" for r in critical):
            return "nonconvergence"
        if any(r.rule_name in ("line_overload", "trafo_overload") for r in results):
            return "thermal_overload"
        if any(r.rule_name in ("undervoltage", "overvoltage") for r in results):
            return "voltage_violation"
        return "other"

    # ── Individual rules ──────────────────────────────────────────

    def _rule_nonconvergence(self, rpt: EvidenceReport) -> RuleResult:
        return RuleResult(
            rule_name="nonconvergence",
            triggered=not rpt.converged,
            severity="critical",
            description="Power flow did not converge. The solver could not find a feasible operating point.",
            evidence={"converged": rpt.converged, "diagnostics": rpt.diagnostic_results},
            suggested_actions=[
                "Check for disconnected network sections",
                "Check for extreme load/generation imbalance",
                "Check for near-zero impedance elements",
                "Try running pp.diagnostic(net) for detailed checks",
            ],
        )

    def _rule_undervoltage(self, rpt: EvidenceReport) -> RuleResult:
        triggered = len(rpt.undervoltage_buses) > 0
        return RuleResult(
            rule_name="undervoltage",
            triggered=triggered,
            severity="warning" if len(rpt.undervoltage_buses) <= 3 else "critical",
            description=f"{len(rpt.undervoltage_buses)} bus(es) below their minimum pu voltage limits.",
            evidence={"buses": rpt.undervoltage_buses},
            suggested_actions=[
                "Add shunt capacitors at affected buses",
                "Increase generator voltage setpoints",
                "Reduce loads at affected buses",
                "Check for excessive reactive power demand",
            ],
        )

    def _rule_overvoltage(self, rpt: EvidenceReport) -> RuleResult:
        triggered = len(rpt.overvoltage_buses) > 0
        return RuleResult(
            rule_name="overvoltage",
            triggered=triggered,
            severity="warning" if len(rpt.overvoltage_buses) <= 3 else "critical",
            description=f"{len(rpt.overvoltage_buses)} bus(es) above their maximum pu voltage limits.",
            evidence={"buses": rpt.overvoltage_buses},
            suggested_actions=[
                "Reduce generator voltage setpoints",
                "Add shunt reactors at affected buses",
                "Increase loading to absorb excess generation",
            ],
        )

    def _rule_line_overload(self, rpt: EvidenceReport) -> RuleResult:
        triggered = len(rpt.overloaded_lines) > 0
        return RuleResult(
            rule_name="line_overload",
            triggered=triggered,
            severity="critical" if triggered else "info",
            description=f"{len(rpt.overloaded_lines)} line(s) exceed 100% thermal loading.",
            evidence={"lines": rpt.overloaded_lines},
            suggested_actions=[
                "Redistribute load across buses",
                "Add parallel lines to increase capacity",
                "Reduce load at downstream buses",
                "Add local generation to reduce power transfer",
            ],
        )

    def _rule_trafo_overload(self, rpt: EvidenceReport) -> RuleResult:
        triggered = len(rpt.overloaded_trafos) > 0
        return RuleResult(
            rule_name="trafo_overload",
            triggered=triggered,
            severity="critical" if triggered else "info",
            description=f"{len(rpt.overloaded_trafos)} transformer(s) exceed 100% loading.",
            evidence={"trafos": rpt.overloaded_trafos},
            suggested_actions=[
                "Add parallel transformer capacity",
                "Reduce load on the downstream side",
                "Re-route power through alternative paths",
            ],
        )

    def _rule_generation_deficit(self, rpt: EvidenceReport) -> RuleResult:
        deficit = rpt.total_load_p_mw - rpt.total_gen_p_mw
        triggered = deficit > rpt.total_load_p_mw * 0.1  # >10% deficit
        return RuleResult(
            rule_name="generation_deficit",
            triggered=triggered,
            severity="critical" if triggered else "info",
            description=f"Active power deficit: {deficit:.1f} MW (gen={rpt.total_gen_p_mw:.1f}, load={rpt.total_load_p_mw:.1f}).",
            evidence={"deficit_mw": round(deficit, 2)},
            suggested_actions=[
                "Add generation capacity",
                "Reduce total load (load shedding)",
                "Check if generators are out of service",
            ],
        )

    def _rule_reactive_deficit(self, rpt: EvidenceReport) -> RuleResult:
        deficit = rpt.total_load_q_mvar - rpt.total_gen_q_mvar
        triggered = deficit > rpt.total_load_q_mvar * 0.2  # >20% deficit
        return RuleResult(
            rule_name="reactive_deficit",
            triggered=triggered,
            severity="warning" if triggered else "info",
            description=f"Reactive power deficit: {deficit:.1f} Mvar.",
            evidence={"deficit_mvar": round(deficit, 2)},
            suggested_actions=[
                "Add shunt capacitors",
                "Enable AVR on generators",
                "Reduce inductive loads",
            ],
        )

    def _rule_disconnected_elements(self, rpt: EvidenceReport) -> RuleResult:
        disc = rpt.diagnostic_results.get("DisconnectedElements", {})
        triggered = bool(disc)
        return RuleResult(
            rule_name="disconnected_elements",
            triggered=triggered,
            severity="critical" if triggered else "info",
            description="Disconnected network sections detected — buses without a path to ext_grid.",
            evidence={"disconnected": disc},
            suggested_actions=[
                "Check for open switches or out-of-service lines",
                "Reconnect isolated buses",
                "Add local generation to isolated sections",
            ],
        )

    def _rule_gen_at_q_limit(self, rpt: EvidenceReport) -> RuleResult:
        triggered = len(rpt.gens_at_q_limit) > 0
        return RuleResult(
            rule_name="gen_at_q_limit",
            triggered=triggered,
            severity="warning",
            description=f"{len(rpt.gens_at_q_limit)} generator(s) at reactive power limit.",
            evidence={"generators": rpt.gens_at_q_limit},
            suggested_actions=[
                "Add reactive compensation",
                "Redistribute reactive power demand",
                "Check generator Q limits (min_q_mvar, max_q_mvar)",
            ],
        )

    def _rule_extreme_voltage_spread(self, rpt: EvidenceReport) -> RuleResult:
        if rpt.voltage_min_pu is None or rpt.voltage_max_pu is None:
            return RuleResult(
                rule_name="extreme_voltage_spread",
                triggered=False, severity="info",
                description="Cannot assess — no voltage data."
            )
        spread = rpt.voltage_max_pu - rpt.voltage_min_pu
        triggered = spread > 0.15
        return RuleResult(
            rule_name="extreme_voltage_spread",
            triggered=triggered,
            severity="warning" if triggered else "info",
            description=f"Voltage spread: {spread:.4f} pu ({rpt.voltage_min_pu:.4f} – {rpt.voltage_max_pu:.4f}).",
            evidence={"spread": round(spread, 4)},
            suggested_actions=[
                "Investigate buses at voltage extremes",
                "Add voltage regulation at remote buses",
                "Check transformer tap settings",
            ],
        )

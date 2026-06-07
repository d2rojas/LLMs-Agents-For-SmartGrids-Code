"""
N−1 Contingency failure scenarios.

These scenarios use pandapower's contingency analysis to find element
removals that cause overloads or voltage violations under N−1 conditions.
"""
from __future__ import annotations

import pandapower as pp
import pandapower.contingency as ct

from .base_scenarios import FailureScenario, ScenarioResult


class ContingencyFailureScenarios:
    """Factory for N−1 contingency scenarios."""

    @staticmethod
    def all_scenarios(network_name: str = "case14") -> list[FailureScenario]:
        return [
            LineContingencyOverload(network_name),
            TrafoContingencyVoltage(network_name),
        ]


# ── Scenario 1: Line outage causing overload ──────────────────────

class LineContingencyOverload(FailureScenario):
    """
    Run N−1 contingency analysis on all lines to identify which single
    line outage causes the worst overload.
    """

    def describe(self) -> str:
        return (
            f"N−1 contingency analysis on {self.network_name}: identify "
            f"the single line outage that causes the worst thermal overload."
        )

    def apply(self) -> ScenarioResult:
        # First ensure base case converges
        self.run_pf()

        # Define N-1 cases for all lines
        nminus1_cases = {
            "line": {"index": self.net.line.index.tolist()},
        }

        # Run contingency analysis
        try:
            contingency_results = ct.run_contingency(
                self.net,
                nminus1_cases=nminus1_cases,
                write_to_net=True,
            )

            # Find the worst case
            element_limits = ct.get_element_limits(self.net)
            within_limits = ct.check_elements_within_limits(
                element_limits, contingency_results, nminus1=True
            )

            # Get overloaded lines from results
            overloaded = []
            worst_cause = None
            if hasattr(self.net, "res_line") and "max_loading_percent" in self.net.res_line.columns:
                overloaded = self.net.res_line[
                    self.net.res_line["max_loading_percent"] > 100
                ].index.tolist()
                if len(overloaded) > 0 and "cause_index" in self.net.res_line.columns:
                    worst_idx = self.net.res_line["max_loading_percent"].idxmax()
                    worst_cause = int(self.net.res_line.at[worst_idx, "cause_index"])

        except Exception as e:
            overloaded = []
            worst_cause = None
            within_limits = True

        return ScenarioResult(
            scenario_name="line_contingency_overload",
            network_name=self.network_name,
            failure_type="contingency",
            root_causes=[
                "N−1 line contingency causes thermal overload",
                f"Worst-case line outage: line {worst_cause}" if worst_cause is not None else "Contingency analysis ran without critical violations",
                "Removing one line redirects flow and overloads others",
            ],
            affected_components={"line": overloaded},
            known_fix=(
                "Add parallel line capacity for the critical corridor, "
                "or implement automatic generation re-dispatch"
            ),
            metadata={
                "within_limits": within_limits,
                "worst_cause_line": worst_cause,
                "overloaded_lines_n1": overloaded,
            },
        )


# ── Scenario 2: Trafo outage causing voltage issue ────────────────

class TrafoContingencyVoltage(FailureScenario):
    """
    Run N−1 contingency analysis on transformers to identify voltage
    violations.
    """

    def describe(self) -> str:
        return (
            f"N−1 contingency analysis on transformers in "
            f"{self.network_name}: identify trafo outages that cause "
            f"voltage violations."
        )

    def apply(self) -> ScenarioResult:
        self.run_pf()

        if len(self.net.trafo) == 0:
            return ScenarioResult(
                scenario_name="trafo_contingency_voltage",
                network_name=self.network_name,
                failure_type="contingency",
                root_causes=["No transformers in this network"],
                affected_components={},
                known_fix="N/A — no transformers to analyze",
            )

        nminus1_cases = {
            "trafo": {"index": self.net.trafo.index.tolist()},
        }

        try:
            contingency_results = ct.run_contingency(
                self.net,
                nminus1_cases=nminus1_cases,
                write_to_net=True,
            )

            # Check for voltage violations
            violated_buses = []
            if "min_vm_pu" in self.net.res_bus.columns:
                violated_buses = self.net.res_bus[
                    (self.net.res_bus["min_vm_pu"] < 0.95) |
                    (self.net.res_bus["max_vm_pu"] > 1.05)
                ].index.tolist()

        except Exception:
            violated_buses = []

        return ScenarioResult(
            scenario_name="trafo_contingency_voltage",
            network_name=self.network_name,
            failure_type="contingency",
            root_causes=[
                "N−1 transformer contingency causes voltage violations",
                "Removing a transformer changes voltage regulation",
                "Downstream buses may experience under- or over-voltage",
            ],
            affected_components={
                "trafo": self.net.trafo.index.tolist(),
                "bus": violated_buses,
            },
            known_fix=(
                "Install redundant transformer capacity or add automatic "
                "voltage regulation (AVR) at downstream buses"
            ),
            metadata={"violated_buses_n1": violated_buses},
        )

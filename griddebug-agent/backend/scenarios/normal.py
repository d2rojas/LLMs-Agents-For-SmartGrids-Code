from __future__ import annotations

from .base_scenarios import FailureScenario, ScenarioResult

class NormalOperation(FailureScenario):
    """
    A baseline scenario where the network operates normally without failures.
    """
    def apply(self) -> ScenarioResult:
        return ScenarioResult(
            scenario_name="normal_operation",
            network_name=self.network_name,
            failure_type="normal",
            root_causes=["Network operates normally."],
            affected_components={"bus": [], "line": [], "trafo": []},
            known_fix="No action needed."
        )

    def describe(self) -> str:
        return "Normal network operation without any forced failures."

class NormalScenarios:
    """Factory for normal operation scenarios."""
    @staticmethod
    def all_scenarios(network_name: str) -> list[FailureScenario]:
        return [NormalOperation(network_name)]

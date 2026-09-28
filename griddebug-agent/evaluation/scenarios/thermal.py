"""
Thermal overload failure scenarios.

These scenarios modify test networks so that `runpp()` converges but
one or more lines/transformers exceed their thermal loading limits.
"""
from __future__ import annotations

import pandapower as pp

from .base import FailureScenario, ScenarioResult


class ThermalOverloadScenarios:
    """Factory for thermal overload scenarios."""

    @staticmethod
    def all_scenarios(network_name: str = "case14", variant: int = 0) -> list[FailureScenario]:
        return [
            ConcentratedLoading(network_name, variant),
            ReducedThermalLimits(network_name, variant),
            TopologyRedirection(network_name, variant),
        ]


# ── Scenario 1: Concentrated loading on weak lines ────────────────

class ConcentratedLoading(FailureScenario):
    """
    Add a very large load at a single bus, forcing heavy flow through
    specific lines and causing overload.
    """

    EXTRA_LOAD_MW = 100.0

    def describe(self) -> str:
        return (
            f"A large load ({self.EXTRA_LOAD_MW} MW) is added to a "
            f"single bus in {self.network_name}, concentrating flow "
            f"through connected lines and causing thermal overload."
        )

    def apply(self) -> ScenarioResult:
        # Pick a bus that has relatively few connections (a "weak" bus)
        slack_bus = int(self.net.ext_grid["bus"].iloc[0])
        bus_connections = {}
        for _, row in self.net.line.iterrows():
            for b in [int(row["from_bus"]), int(row["to_bus"])]:
                bus_connections[b] = bus_connections.get(b, 0) + 1

        # variant: which weak bus. Fewest branch connections first.
        target_bus = self.pick(self.buses_by_degree(), self.variant, fallback=slack_bus + 1)

        pp.create_load(
            self.net, bus=target_bus,
            p_mw=self.EXTRA_LOAD_MW, q_mvar=self.EXTRA_LOAD_MW * 0.3,
            name="concentrated_load",
        )

        converged = self.run_pf()
        overloaded = []
        if converged:
            overloaded = self.net.res_line[
                self.net.res_line["loading_percent"] > 100
            ].index.tolist()

        return ScenarioResult(
            scenario_name="concentrated_loading",
            network_name=self.network_name,
            failure_type="thermal",
            root_causes=[
                f"Large load ({self.EXTRA_LOAD_MW} MW) added at bus {target_bus}",
                "Power must flow through few connecting lines",
                "Connected lines exceed thermal rating",
            ],
            affected_components={
                "bus": [target_bus],
                "line": overloaded,
            },
            known_fix=(
                "Add parallel lines to increase capacity, add local "
                "generation, or redistribute the load across multiple buses"
            ),
            metadata={
                "extra_load_mw": self.EXTRA_LOAD_MW,
                "variant": self.variant,
                "target_bus": target_bus,
                "converged": converged,
                "overloaded_lines": overloaded,
            },
        )


# ── Scenario 2: Reduced thermal limits ────────────────────────────

class ReducedThermalLimits(FailureScenario):
    """
    Reduce the max_i_ka of selected lines so that normal load levels
    cause thermal violations.
    """

    LIMIT_FACTOR = 0.3  # Reduce to 30% of original rating
    N_LINES = 3

    def describe(self) -> str:
        return (
            f"Thermal limits of key lines in {self.network_name} are "
            f"reduced to {self.LIMIT_FACTOR*100:.0f}% of original ratings, "
            f"causing overloads under normal loading."
        )

    def apply(self) -> ScenarioResult:
        # variant: which three lines are de-rated. Ranked by base loading, so
        # variant 0 de-rates ranks 1-3 and variant 1 ranks 4-6.
        ranked = self.lines_by_loading()
        start = (self.variant * self.N_LINES) % max(1, len(ranked))
        top_loaded = ranked[start : start + self.N_LINES] or ranked[: self.N_LINES]

        for line_idx in top_loaded:
            original = self.net.line.at[line_idx, "max_i_ka"]
            self.net.line.at[line_idx, "max_i_ka"] = original * self.LIMIT_FACTOR

        # Re-run to assess
        converged = self.run_pf()
        overloaded = []
        if converged:
            overloaded = self.net.res_line[
                self.net.res_line["loading_percent"] > 100
            ].index.tolist()

        return ScenarioResult(
            scenario_name="reduced_thermal_limits",
            network_name=self.network_name,
            failure_type="thermal",
            root_causes=[
                f"Thermal limits of lines {top_loaded} reduced to {self.LIMIT_FACTOR*100:.0f}%",
                "Lines are now overloaded even under normal conditions",
                "Simulates aging equipment or de-rated conductors",
            ],
            affected_components={"line": overloaded},
            known_fix=(
                "Upgrade conductors (increase max_i_ka), add parallel "
                "paths, or reduce loading on affected lines"
            ),
            metadata={
                "limit_factor": self.LIMIT_FACTOR,
                "variant": self.variant,
                "modified_lines": top_loaded,
                "converged": converged,
                "overloaded_lines": overloaded,
            },
        )


# ── Scenario 3: Topology change redirecting flow ──────────────────

class TopologyRedirection(FailureScenario):
    """
    Take a key line out of service, forcing power to reroute through
    parallel paths and overloading them.
    """

    def describe(self) -> str:
        return (
            f"A heavily loaded line in {self.network_name} is taken out "
            f"of service, forcing power redirection through remaining "
            f"paths and causing cascade overloads."
        )

    def apply(self) -> ScenarioResult:
        from .contingency import topology_line

        # The most loaded line whose outage actually leaves the network converged and
        # worse than it was. On IEEE-118 the most loaded line's outage changes nothing,
        # and a scenario that injects nothing measures nothing.
        most_loaded = topology_line(self.net, self.variant)
        self.reset()
        self.net.line.at[most_loaded, "in_service"] = False

        converged = self.run_pf()
        overloaded = []
        if converged:
            overloaded = self.net.res_line[
                self.net.res_line["loading_percent"] > 100
            ].index.tolist()

        return ScenarioResult(
            scenario_name="topology_redirection",
            network_name=self.network_name,
            failure_type="thermal",
            root_causes=[
                f"Line {most_loaded} taken out of service",
                "Power reroutes through alternative paths",
                "Remaining lines become overloaded due to redirected flow",
            ],
            affected_components={
                "line": [most_loaded] + overloaded,
            },
            known_fix=(
                "Restore the removed line, add parallel capacity, "
                "or reduce load to relieve overloaded paths"
            ),
            metadata={
                "removed_line": most_loaded,
                "variant": self.variant,
                "converged": converged,
                "overloaded_lines": overloaded,
            },
        )

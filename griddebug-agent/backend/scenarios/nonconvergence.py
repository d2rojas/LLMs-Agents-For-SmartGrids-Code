"""
Non-convergence failure scenarios.

These scenarios modify test networks so that `runpp()` fails to converge,
simulating conditions such as extreme loading, missing generation,
near-zero impedance, and disconnected sub-networks.
"""
from __future__ import annotations

import pandapower as pp

from .base_scenarios import FailureScenario, ScenarioResult


class NonConvergenceScenarios:
    """Factory for non-convergence failure scenarios."""

    @staticmethod
    def all_scenarios(network_name: str = "case14") -> list[FailureScenario]:
        return [
            ExtremeLoadScaling(network_name),
            AllGeneratorsRemoved(network_name),
            NearZeroImpedanceLine(network_name),
            DisconnectedSubNetwork(network_name),
        ]


# ── Scenario 1: Extreme load scaling ──────────────────────────────

class ExtremeLoadScaling(FailureScenario):
    """Scale all loads by 20× to cause solver divergence."""

    SCALE_FACTOR = 20.0

    def describe(self) -> str:
        return (
            f"All loads in {self.network_name} are scaled by "
            f"{self.SCALE_FACTOR}×, causing extreme power mismatch "
            f"and Newton-Raphson divergence."
        )

    def apply(self) -> ScenarioResult:
        self.net.load["p_mw"] *= self.SCALE_FACTOR
        self.net.load["q_mvar"] *= self.SCALE_FACTOR

        affected_loads = self.net.load.index.tolist()
        return ScenarioResult(
            scenario_name="extreme_load_scaling",
            network_name=self.network_name,
            failure_type="nonconvergence",
            root_causes=[
                f"All loads scaled by {self.SCALE_FACTOR}×",
                "Total active power demand far exceeds available generation",
                "Newton-Raphson solver cannot find a feasible operating point",
            ],
            affected_components={"load": affected_loads},
            known_fix="Reduce loads to original values or add generation capacity",
            metadata={"scale_factor": self.SCALE_FACTOR},
        )


# ── Scenario 2: All generators removed ────────────────────────────

class AllGeneratorsRemoved(FailureScenario):
    """Set all generators out of service (keeping only ext_grid slack)."""

    def describe(self) -> str:
        return (
            f"All generators in {self.network_name} are taken out of "
            f"service, leaving only the external grid to supply the "
            f"entire system, potentially causing non-convergence."
        )

    def apply(self) -> ScenarioResult:
        affected_gens = self.net.gen.index.tolist()
        self.net.gen["in_service"] = False

        # Also disable static generators if present
        affected_sgens = self.net.sgen.index.tolist() if len(self.net.sgen) > 0 else []
        if affected_sgens:
            self.net.sgen["in_service"] = False

        return ScenarioResult(
            scenario_name="all_generators_removed",
            network_name=self.network_name,
            failure_type="nonconvergence",
            root_causes=[
                "All generators taken out of service",
                "Ext_grid alone cannot satisfy total demand",
                "Severe voltage collapse across the network",
            ],
            affected_components={"gen": affected_gens, "sgen": affected_sgens},
            known_fix="Restore generators to service or reduce total demand",
        )


# ── Scenario 3: Near-zero impedance line ──────────────────────────

class NearZeroImpedanceLine(FailureScenario):
    """Set a line's impedance to near-zero, causing numerical instability."""

    def describe(self) -> str:
        return (
            f"A line in {self.network_name} has its impedance set to "
            f"near-zero (1e-10 Ω/km), causing a nearly singular "
            f"admittance matrix and solver failure."
        )

    def apply(self) -> ScenarioResult:
        target_line = 0  # First line
        self.net.line.at[target_line, "r_ohm_per_km"] = 1e-10
        self.net.line.at[target_line, "x_ohm_per_km"] = 1e-10

        return ScenarioResult(
            scenario_name="near_zero_impedance",
            network_name=self.network_name,
            failure_type="nonconvergence",
            root_causes=[
                f"Line {target_line} has near-zero impedance",
                "Admittance matrix becomes nearly singular",
                "Numerical precision issues prevent convergence",
            ],
            affected_components={"line": [target_line]},
            known_fix="Restore line impedance to realistic values",
            metadata={"target_line": target_line},
        )


# ── Scenario 4: Disconnected sub-network ──────────────────────────

class DisconnectedSubNetwork(FailureScenario):
    """Disconnect a bus by taking all its connected lines out of service."""

    def describe(self) -> str:
        return (
            f"A bus in {self.network_name} is isolated by disabling all "
            f"connected lines, creating a disconnected sub-network with "
            f"loads but no generation path."
        )

    def apply(self) -> ScenarioResult:
        # Find a bus with loads but not the slack bus
        slack_buses = self.net.ext_grid["bus"].values
        load_buses = self.net.load["bus"].values
        target_bus = None
        for bus in load_buses:
            if bus not in slack_buses:
                target_bus = int(bus)
                break

        if target_bus is None:
            target_bus = int(self.net.bus.index[1])  # Fallback

        # Find all lines connected to this bus and disable them
        connected_lines = self.net.line[
            (self.net.line["from_bus"] == target_bus) |
            (self.net.line["to_bus"] == target_bus)
        ].index.tolist()

        for line_idx in connected_lines:
            self.net.line.at[line_idx, "in_service"] = False

        return ScenarioResult(
            scenario_name="disconnected_subnetwork",
            network_name=self.network_name,
            failure_type="nonconvergence",
            root_causes=[
                f"Bus {target_bus} is disconnected from the main grid",
                f"Lines {connected_lines} taken out of service",
                "Isolated loads have no power supply path",
            ],
            affected_components={"bus": [target_bus], "line": connected_lines},
            known_fix="Restore at least one line to reconnect the bus, or add local generation",
            metadata={"target_bus": target_bus, "disabled_lines": connected_lines},
        )

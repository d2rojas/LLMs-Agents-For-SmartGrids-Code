"""
Voltage violation failure scenarios.

These scenarios modify test networks so that `runpp()` converges but
produces bus voltages outside acceptable bounds (typically 0.95–1.05 pu).
"""
from __future__ import annotations

import pandapower as pp

from .base_scenarios import FailureScenario, ScenarioResult


class VoltageViolationScenarios:
    """Factory for voltage violation scenarios."""

    @staticmethod
    def all_scenarios(network_name: str = "case14") -> list[FailureScenario]:
        return [
            HeavyLoadingUnderVoltage(network_name),
            ExcessGenerationOverVoltage(network_name),
            ReactiveImbalance(network_name),
        ]


# ── Scenario 1: Heavy loading → under-voltage ─────────────────────

class HeavyLoadingUnderVoltage(FailureScenario):
    """
    Moderately scale loads (3×) so the system converges but remote
    buses experience significant voltage sag.
    """

    SCALE_FACTOR = 3.0

    def describe(self) -> str:
        return (
            f"Loads in {self.network_name} scaled by {self.SCALE_FACTOR}× "
            f"to cause under-voltage at remote buses while remaining within "
            f"solver convergence range."
        )

    def apply(self) -> ScenarioResult:
        self.net.load["p_mw"] *= self.SCALE_FACTOR
        self.net.load["q_mvar"] *= self.SCALE_FACTOR

        # Run PF to find the affected buses
        converged = self.run_pf()
        violated = []
        if converged:
            violated = self.net.res_bus[
                self.net.res_bus["vm_pu"] < 0.95
            ].index.tolist()

        return ScenarioResult(
            scenario_name="heavy_loading_undervoltage",
            network_name=self.network_name,
            failure_type="voltage",
            root_causes=[
                f"All loads scaled by {self.SCALE_FACTOR}×",
                "Increased reactive power demand causes voltage drop",
                "Buses far from generation experience under-voltage",
            ],
            affected_components={
                "load": self.net.load.index.tolist(),
                "bus": violated,
            },
            known_fix=(
                "Add reactive compensation (shunt capacitors) at affected "
                "buses, or reduce loading to normal levels"
            ),
            metadata={
                "scale_factor": self.SCALE_FACTOR,
                "converged": converged,
                "violated_buses": violated,
            },
        )


# ── Scenario 2: Excess generation → over-voltage ──────────────────

class ExcessGenerationOverVoltage(FailureScenario):
    """
    Increase generator output while reducing load, causing over-voltage
    at generator buses.
    """

    GEN_SCALE = 3.0
    LOAD_SCALE = 0.3

    def describe(self) -> str:
        return (
            f"Generator output in {self.network_name} scaled by "
            f"{self.GEN_SCALE}× while loads reduced to {self.LOAD_SCALE}× "
            f"to cause over-voltage conditions."
        )

    def apply(self) -> ScenarioResult:
        self.net.load["p_mw"] *= self.LOAD_SCALE
        self.net.load["q_mvar"] *= self.LOAD_SCALE

        if len(self.net.gen) > 0:
            self.net.gen["p_mw"] *= self.GEN_SCALE

        # Raise ext_grid voltage setpoint
        self.net.ext_grid["vm_pu"] = 1.08

        converged = self.run_pf()
        violated = []
        if converged:
            violated = self.net.res_bus[
                self.net.res_bus["vm_pu"] > 1.05
            ].index.tolist()

        return ScenarioResult(
            scenario_name="excess_generation_overvoltage",
            network_name=self.network_name,
            failure_type="voltage",
            root_causes=[
                f"Generator output scaled by {self.GEN_SCALE}×",
                f"Loads reduced to {self.LOAD_SCALE}×",
                "Ext_grid voltage setpoint raised to 1.08 pu",
                "Active power surplus with light loading causes over-voltage",
            ],
            affected_components={
                "gen": self.net.gen.index.tolist(),
                "bus": violated,
            },
            known_fix=(
                "Reduce generator output, increase loads, or lower "
                "ext_grid voltage setpoint to 1.0 pu"
            ),
            metadata={
                "gen_scale": self.GEN_SCALE,
                "load_scale": self.LOAD_SCALE,
                "converged": converged,
                "violated_buses": violated,
            },
        )


# ── Scenario 3: Reactive power imbalance ──────────────────────────

class ReactiveImbalance(FailureScenario):
    """
    Add large inductive loads (high Q) without corresponding reactive
    compensation, causing voltage sag.
    """

    Q_INJECTION_MVAR = 50.0

    def describe(self) -> str:
        return (
            f"Large inductive loads ({self.Q_INJECTION_MVAR} Mvar) added "
            f"to remote buses in {self.network_name} without reactive "
            f"compensation, causing voltage depression."
        )

    def apply(self) -> ScenarioResult:
        # Pick buses far from the slack bus
        slack_bus = int(self.net.ext_grid["bus"].iloc[0])
        remote_buses = [
            int(b) for b in self.net.bus.index
            if b != slack_bus
        ][-3:]  # Last 3 buses (typically farthest)

        for bus in remote_buses:
            pp.create_load(self.net, bus=bus, p_mw=0, q_mvar=self.Q_INJECTION_MVAR,
                           name=f"reactive_injection_bus{bus}")

        converged = self.run_pf()
        violated = []
        if converged:
            violated = self.net.res_bus[
                self.net.res_bus["vm_pu"] < 0.95
            ].index.tolist()

        return ScenarioResult(
            scenario_name="reactive_imbalance",
            network_name=self.network_name,
            failure_type="voltage",
            root_causes=[
                f"Large inductive loads ({self.Q_INJECTION_MVAR} Mvar) at buses {remote_buses}",
                "No reactive compensation to offset the demand",
                "Voltage depression at remote buses",
            ],
            affected_components={"bus": violated + remote_buses},
            known_fix=(
                "Add shunt capacitors at affected buses or enable "
                "automatic voltage regulators on nearby generators"
            ),
            metadata={
                "q_injection_mvar": self.Q_INJECTION_MVAR,
                "target_buses": remote_buses,
                "converged": converged,
                "violated_buses": violated,
            },
        )

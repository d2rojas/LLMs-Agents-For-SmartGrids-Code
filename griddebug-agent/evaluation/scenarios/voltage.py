"""
Voltage violation failure scenarios.

These scenarios modify test networks so that `runpp()` converges but
produces bus voltages outside acceptable bounds (typically 0.95–1.05 pu).
"""
from __future__ import annotations

import pandapower as pp

from .base import FailureScenario, ScenarioResult


class VoltageViolationScenarios:
    """Factory for voltage violation scenarios."""

    @staticmethod
    def all_scenarios(network_name: str = "case14", variant: int = 0) -> list[FailureScenario]:
        return [
            HeavyLoadingUnderVoltage(network_name, variant),
            ExcessGenerationOverVoltage(network_name, variant),
            ReactiveImbalance(network_name, variant),
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

    LOCAL_SCALE_FACTOR = 5.0

    def apply(self) -> ScenarioResult:
        # variant 0: every load grows. variant 1: only the loads on the half of the
        # network furthest from the slack bus, harder, and a local repair fixes it.
        if self.variant % 2 == 0:
            scaled_buses = [int(b) for b in self.net.load["bus"].unique()]
            factor = self.SCALE_FACTOR
            self.net.load["p_mw"] *= factor
            self.net.load["q_mvar"] *= factor
        else:
            far = self.buses_by_distance_from_slack()
            scaled_buses = sorted(set(far[: max(1, len(far) // 2)]) & {int(b) for b in self.net.load["bus"]})
            factor = self.LOCAL_SCALE_FACTOR
            mask = self.net.load["bus"].isin(scaled_buses)
            self.net.load.loc[mask, "p_mw"] *= factor
            self.net.load.loc[mask, "q_mvar"] *= factor

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
                (f"All loads scaled by {factor}×" if self.variant % 2 == 0
                 else f"The loads at the {len(scaled_buses)} buses furthest from the slack bus scaled by {factor}×"),
                "Increased reactive power demand causes voltage drop",
                "Buses far from generation experience under-voltage",
            ],
            affected_components={
                "load": [int(i) for i in self.net.load.index if int(self.net.load.at[i, "bus"]) in scaled_buses],
                "bus": violated,
            },
            known_fix=(
                "Add reactive compensation (shunt capacitors) at affected "
                "buses, or reduce loading to normal levels"
            ),
            metadata={
                "scale_factor": factor,
                "variant": self.variant,
                "scaled_buses": scaled_buses,
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

    N_BUSES = 3

    def apply(self) -> ScenarioResult:
        # variant: which three buses. Ranked by hop distance from the slack bus,
        # furthest first, so variant 0 is the worst place to put the demand.
        far = self.buses_by_distance_from_slack()
        start = (self.variant * self.N_BUSES) % max(1, len(far))
        remote_buses = far[start : start + self.N_BUSES] or far[: self.N_BUSES]

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
                "variant": self.variant,
                "target_buses": remote_buses,
                "converged": converged,
                "violated_buses": violated,
            },
        )

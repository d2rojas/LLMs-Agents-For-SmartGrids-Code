"""The scenario set: thirteen fault injections on each IEEE network.

``build(network, scenario_id)`` constructs exactly one scenario (the original
harness built every scenario of a category to find one by id) and returns the
injected network, its ground truth and the *injected fault*: what the generator
actually did, as a type and a list of components. The diagnosis column is
scored against that, never against the symptom category.

Every instance carries two labels:

* ``category``: what the generator set out to cause (the label of the paper)
* ``initial_state``: what the solver says about the injected network
  (``not_converged``, ``islanded_load``, ``violations``, ``secure``), measured
  relative to the base network

The two differ for several instances; the manifest under ``data/scenarios/``
records both, plus a content hash of every injected network, so the set is
frozen and a change in pandapower or in a generator is caught on load.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandapower as pp

from .base import FailureScenario, ScenarioResult
from .contingency import ContingencyFailureScenarios
from .nonconvergence import NonConvergenceScenarios
from .normal import NormalScenarios
from .thermal import ThermalOverloadScenarios
from .voltage import VoltageViolationScenarios

FACTORIES = {
    "nonconvergence": NonConvergenceScenarios,
    "voltage": VoltageViolationScenarios,
    "thermal": ThermalOverloadScenarios,
    "contingency": ContingencyFailureScenarios,
    "normal": NormalScenarios,
}

# id, label, category, in the order of the paper's description (1 normal, 4, 3, 3, 2)
SCENARIOS: Tuple[Dict[str, str], ...] = (
    {"id": "normal_operation", "label": "Normal operation", "category": "normal"},
    {"id": "extreme_load_scaling", "label": "Extreme load scaling (20x)", "category": "nonconvergence"},
    {"id": "all_generators_removed", "label": "All generators removed", "category": "nonconvergence"},
    {"id": "near_zero_impedance", "label": "Near-zero impedance line", "category": "nonconvergence"},
    {"id": "disconnected_subnetwork", "label": "Disconnected sub-network", "category": "nonconvergence"},
    {"id": "heavy_loading_undervoltage", "label": "Heavy loading under-voltage (3x)", "category": "voltage"},
    {"id": "excess_generation_overvoltage", "label": "Excess generation over-voltage", "category": "voltage"},
    {"id": "reactive_imbalance", "label": "Reactive power imbalance", "category": "voltage"},
    {"id": "concentrated_loading", "label": "Concentrated loading on a weak bus", "category": "thermal"},
    {"id": "reduced_thermal_limits", "label": "Reduced thermal limits (30 %)", "category": "thermal"},
    {"id": "topology_redirection", "label": "Topology change, flow redirection", "category": "thermal"},
    {"id": "line_contingency_overload", "label": "N-1 line contingency", "category": "contingency"},
    {"id": "trafo_contingency_voltage", "label": "N-1 transformer contingency", "category": "contingency"},
)
SCENARIO_IDS = tuple(s["id"] for s in SCENARIOS)
CATEGORY_OF = {s["id"]: s["category"] for s in SCENARIOS}
LABEL_OF = {s["id"]: s["label"] for s in SCENARIOS}

# The injected fault, as a type the diagnosis is scored against. One type per
# scenario generator; the components come from the generator's own record.
FAULT_TYPES = (
    "none", "load_increase", "generation_loss", "impedance_fault", "islanding",
    "voltage_setpoint", "reactive_load", "limit_derating", "line_outage", "trafo_outage",
)
FAULT_TYPE_OF = {
    "normal_operation": "none",
    "extreme_load_scaling": "load_increase",
    "all_generators_removed": "generation_loss",
    "near_zero_impedance": "impedance_fault",
    "disconnected_subnetwork": "islanding",
    "heavy_loading_undervoltage": "load_increase",
    "excess_generation_overvoltage": "voltage_setpoint",
    "reactive_imbalance": "reactive_load",
    "concentrated_loading": "load_increase",
    "reduced_thermal_limits": "limit_derating",
    "topology_redirection": "line_outage",
    "line_contingency_overload": "line_outage",
    "trafo_contingency_voltage": "trafo_outage",
}


@dataclass
class Injected:
    """What the generator did to the network: the truth the diagnosis is scored against."""

    fault_type: str
    components: Dict[str, List[int]] = field(default_factory=dict)  # {"line": [7], "load": [0, 1, ...]}
    description: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {"fault_type": self.fault_type, "components": self.components, "description": self.description}


def _injected(scenario_id: str, truth: ScenarioResult) -> Injected:
    m = truth.metadata or {}
    ft = FAULT_TYPE_OF[scenario_id]
    comp: Dict[str, List[int]] = {}
    if scenario_id == "extreme_load_scaling" or scenario_id == "heavy_loading_undervoltage":
        comp = {"load": list(truth.affected_components.get("load", []))}
    elif scenario_id == "all_generators_removed":
        comp = {"gen": list(truth.affected_components.get("gen", []))}
        if truth.affected_components.get("sgen"):
            comp["sgen"] = list(truth.affected_components["sgen"])
    elif scenario_id == "near_zero_impedance":
        comp = {"line": [int(m.get("target_line", 0))]}
    elif scenario_id == "disconnected_subnetwork":
        comp = {"bus": [int(m["target_bus"])], "line": [int(i) for i in m.get("disabled_lines", [])]}
    elif scenario_id == "excess_generation_overvoltage":
        comp = {"gen": list(truth.affected_components.get("gen", [])), "ext_grid": [0]}
    elif scenario_id == "reactive_imbalance":
        comp = {"bus": [int(b) for b in m.get("target_buses", [])]}
    elif scenario_id == "concentrated_loading":
        comp = {"bus": [int(m["target_bus"])]}
    elif scenario_id == "reduced_thermal_limits":
        comp = {"line": [int(i) for i in m.get("modified_lines", [])]}
    elif scenario_id == "topology_redirection":
        comp = {"line": [int(m["removed_line"])]}
    elif scenario_id == "line_contingency_overload":
        comp = {"line": [int(m["outaged_line"])]}
    elif scenario_id == "trafo_contingency_voltage":
        comp = {"line": [int(m["outaged_line"])]} if m.get("no_trafo") else {"trafo": [int(m["outaged_trafo"])]}
        if m.get("no_trafo"):
            ft = "line_outage"
    return Injected(fault_type=ft, components=comp, description="; ".join(truth.root_causes[:2]))


def build(network: str, scenario_id: str) -> Tuple[pp.pandapowerNet, ScenarioResult, Injected]:
    """Construct one scenario: the injected network (power flow not yet run), its truth, its injected fault."""
    if scenario_id not in CATEGORY_OF:
        raise ValueError(f"unknown scenario {scenario_id!r}; known: {', '.join(SCENARIO_IDS)}")
    factory = FACTORIES[CATEGORY_OF[scenario_id]]
    for sc in factory.all_scenarios(network):
        # each class knows its own name only through apply(); build a fresh one per id
        probe = copy.deepcopy(sc)
        truth = probe.apply()
        if truth.scenario_name == scenario_id:
            return probe.net, truth, _injected(scenario_id, truth)
    raise ValueError(f"scenario {scenario_id!r} not produced by its factory on {network}")


__all__ = [
    "SCENARIOS", "SCENARIO_IDS", "CATEGORY_OF", "LABEL_OF", "FAULT_TYPES", "FAULT_TYPE_OF",
    "Injected", "FailureScenario", "ScenarioResult", "build",
]

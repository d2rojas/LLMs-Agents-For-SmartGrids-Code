"""The scenario set: twenty instances of thirteen fault classes on each IEEE network.

Thirteen classes, one per kind of fault, are the taxonomy the paper describes.
Seven of them can place their fault in more than one point of the network, and
each of those contributes two instances, so a run poses **20 instances per
network**: 1 normal, 5 non-convergence, 5 voltage, 5 thermal, 4 contingency.
A variant changes *where* the fault is, never how hard it is: the class ranks
its candidates deterministically (by base loading, by hop distance from the
slack bus, by outage severity) and takes the variant-th. Two instances of one
class are therefore the same kind of fault at two different points, which is
what tells a method that handles line outages from one that memorized a line.

``build(network, scenario_id, variant)`` constructs exactly one instance (the
original harness built every scenario of a category to find one by id) and
returns the injected network, its ground truth and the *injected fault*: what
the generator actually did, as a type and a list of components. The diagnosis
column is scored against that, never against the symptom category.

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

# How many instances each class contributes, and what the second one moves.
# Seven classes place their fault somewhere the network chooses; the other six
# are global perturbations (every load, every generator, the slack setpoint) or
# the control, and a second instance of those would be the same instance.
VARIANTS_OF: Dict[str, int] = {
    "normal_operation": 1,
    "extreme_load_scaling": 1,
    "all_generators_removed": 1,
    "near_zero_impedance": 2,
    "disconnected_subnetwork": 1,
    "heavy_loading_undervoltage": 2,
    "excess_generation_overvoltage": 1,
    "reactive_imbalance": 2,
    "concentrated_loading": 2,
    "reduced_thermal_limits": 2,
    "topology_redirection": 1,
    "line_contingency_overload": 2,
    "trafo_contingency_voltage": 2,
}
# Why a class is posed only once. Three of them perturb the whole network and there is
# one way to do it; one is the control; two are held at one instance on purpose.
POSED_ONCE: Dict[str, str] = {
    "normal_operation": "the control: the unmodified network, and there is only one of those",
    "extreme_load_scaling": "every load at once: a global perturbation with one way to do it",
    "all_generators_removed": "every generator at once: a global perturbation with one way to do it",
    "excess_generation_overvoltage": "every generator and the slack setpoint at once: a global perturbation",
    "disconnected_subnetwork": "could be posed at a second bus; held at one so the non-convergence mode keeps five scenarios and the mix stays balanced",
    "topology_redirection": "takes the most loaded line whose outage actually breaks something; a second one would collide with the two N-1 classes, which take the worst outages among the rest",
}
VARIES_BY: Dict[str, str] = {
    "near_zero_impedance": "which line carries the near-zero impedance, most loaded first",
    "heavy_loading_undervoltage": "every load at 3x, or only the loads on the half of the network furthest from the slack bus, at 5x",
    "reactive_imbalance": "which three remote buses take the reactive demand, furthest from the slack bus first",
    "concentrated_loading": "which weakly connected bus takes the extra load, fewest connections first",
    "reduced_thermal_limits": "which three lines are de-rated: the three most loaded, or the next three",
    "line_contingency_overload": "which line is taken out: the worst N-1 outage, or the second worst",
    "trafo_contingency_voltage": "which transformer is taken out: the worst N-1 outage, or the second worst",
}

# The instance set, in table order: (scenario_id, variant). 20 per network.
INSTANCES: Tuple[Tuple[str, int], ...] = tuple(
    (s["id"], v) for s in SCENARIOS for v in range(VARIANTS_OF[s["id"]])
)
N_INSTANCES = len(INSTANCES)


def instance_id(network: str, scenario_id: str, variant: int) -> str:
    return f"{network}-{scenario_id}-v{variant}"

# The injected fault, as a type the diagnosis is scored against. One type per
# scenario generator; the components come from the generator's own record.
FAULT_TYPES = (
    "none", "load_increase", "generation_loss", "generation_excess", "impedance_fault",
    "islanding", "voltage_setpoint", "reactive_load", "limit_derating", "line_outage",
    "trafo_outage",
)

# Scenarios whose injected fault has more than one correct name, because the generator
# changes more than one thing. Scoring the diagnosis against a single label there would
# mark a right answer wrong.
ALSO_ACCEPTED: Dict[str, Tuple[str, ...]] = {
    # gens x3, loads x0.3 and the slack setpoint raised: "the setpoint is too high" and
    # "there is too much generation for the load" are both the fault that was injected.
    "excess_generation_overvoltage": ("generation_excess",),
}
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
    also_accepted: Tuple[str, ...] = ()  # other correct names for this same injected fault

    def as_dict(self) -> Dict[str, Any]:
        return {"fault_type": self.fault_type, "components": self.components,
                "description": self.description, "also_accepted": list(self.also_accepted)}


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
    return Injected(fault_type=ft, components=comp, description="; ".join(truth.root_causes[:2]),
                    also_accepted=ALSO_ACCEPTED.get(scenario_id, ()))


def build(network: str, scenario_id: str, variant: int = 0) -> Tuple[pp.pandapowerNet, ScenarioResult, Injected]:
    """Construct one instance: the injected network (power flow not yet run), its truth, its injected fault."""
    if scenario_id not in CATEGORY_OF:
        raise ValueError(f"unknown scenario {scenario_id!r}; known: {', '.join(SCENARIO_IDS)}")
    if variant >= VARIANTS_OF[scenario_id]:
        raise ValueError(f"{scenario_id} has {VARIANTS_OF[scenario_id]} variant(s); asked for v{variant}")
    factory = FACTORIES[CATEGORY_OF[scenario_id]]
    for sc in factory.all_scenarios(network, variant):
        # each class knows its own name only through apply(); build a fresh one per id
        probe = copy.deepcopy(sc)
        truth = probe.apply()
        if truth.scenario_name == scenario_id:
            return probe.net, truth, _injected(scenario_id, truth)
    raise ValueError(f"scenario {scenario_id!r} not produced by its factory on {network}")


__all__ = [
    "SCENARIOS", "SCENARIO_IDS", "CATEGORY_OF", "LABEL_OF", "FAULT_TYPES", "FAULT_TYPE_OF",
    "VARIANTS_OF", "VARIES_BY", "POSED_ONCE", "ALSO_ACCEPTED", "INSTANCES", "N_INSTANCES", "instance_id",
    "Injected", "FailureScenario", "ScenarioResult", "build",
]

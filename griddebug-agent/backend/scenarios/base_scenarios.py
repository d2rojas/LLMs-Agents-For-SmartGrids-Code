"""
Base classes for failure scenario generation.

Each scenario loads a standard IEEE test network, applies modifications
to inject a specific failure mode, and records ground-truth metadata
for evaluation.
"""
from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandapower as pp
import pandapower.networks as pn


# ── Data classes ───────────────────────────────────────────────────

@dataclass
class ScenarioResult:
    """Ground-truth description of an injected failure."""
    scenario_name: str
    network_name: str
    failure_type: str                       # "nonconvergence", "voltage", "thermal", "contingency"
    root_causes: list[str]                  # Human-readable root cause descriptions
    affected_components: dict[str, list[int]]  # e.g. {"bus": [3,5], "line": [7]}
    known_fix: str                          # Description of a known corrective action
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Network loader ─────────────────────────────────────────────────

import inspect

def load_network(name: str) -> pp.pandapowerNet:
    """Load a fresh copy of a test network from pandapower.networks."""
    if not hasattr(pn, name):
        raise ValueError(f"Unknown network: {name}. Not found in pandapower.networks.")
        
    func = getattr(pn, name)
    if not inspect.isfunction(func):
        raise ValueError(f"Unknown network: {name}. Not a function in pandapower.networks.")
        
    try:
        return func()
    except Exception as e:
        raise ValueError(f"Network {name} could not be loaded dynamically: {e}")


# ── Abstract scenario ──────────────────────────────────────────────

class FailureScenario(ABC):
    """Base class for all failure scenarios."""

    def __init__(self, network_name: str = "case14"):
        self.network_name = network_name
        self.original_net = load_network(network_name)
        self.net = copy.deepcopy(self.original_net)

    @abstractmethod
    def apply(self) -> ScenarioResult:
        """
        Apply modifications to *self.net* to produce the failure.
        Returns a ScenarioResult with ground-truth metadata.
        """
        ...

    @abstractmethod
    def describe(self) -> str:
        """Human-readable description of the scenario."""
        ...

    def reset(self) -> None:
        """Reset the network to its original state."""
        self.net = copy.deepcopy(self.original_net)

    def run_pf(self, **kwargs) -> bool:
        """
        Attempt to run power flow.  Returns True if converged.
        Catches LoadflowNotConverged so callers don't have to.
        """
        try:
            pp.runpp(self.net, **kwargs)
            return self.net.converged
        except pp.LoadflowNotConverged:
            return False
        except Exception:
            return False

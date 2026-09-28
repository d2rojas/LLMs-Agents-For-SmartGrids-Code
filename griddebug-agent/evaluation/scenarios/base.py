"""Base classes for failure scenario generation.

Each scenario loads a standard IEEE test network (through ``solver.network.load_network``, so
line ratings follow the shared rule), applies modifications to inject a specific failure mode,
and records ground-truth metadata for evaluation.
"""
from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandapower as pp

from solver.network import load_network


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


# ── Abstract scenario ──────────────────────────────────────────────

class FailureScenario(ABC):
    """Base class for all failure scenarios.

    ``variant`` selects *where* the fault is injected, not how hard it is. Each
    class that can place its fault in more than one place ranks the candidates
    deterministically (by loading, by distance from the slack bus, by outage
    severity) and takes the ``variant``-th of them, so two instances of the same
    class are the same kind of fault at two different points of the network.
    The ranking is a property of the network, so the same variant index means
    the same thing on every system.
    """

    def __init__(self, network_name: str = "case14", variant: int = 0):
        self.network_name = network_name
        self.variant = int(variant)
        self.original_net = load_network(network_name)
        self.net = copy.deepcopy(self.original_net)

    # ── candidate rankings the variants pick from ──────────────────

    def slack_buses(self) -> set[int]:
        return {int(b) for b in self.net.ext_grid["bus"]}

    def buses_by_distance_from_slack(self) -> list[int]:
        """Bus indices, electrically furthest from a slack bus first (hop count on the in-service topology)."""
        try:
            import networkx as nx
            from pandapower.topology import create_nxgraph

            g = create_nxgraph(self.net, respect_switches=True, include_out_of_service=False)
            slack = self.slack_buses()
            dist: dict[int, float] = {}
            for s in slack:
                if s in g:
                    for b, d in nx.single_source_shortest_path_length(g, s).items():
                        dist[int(b)] = min(dist.get(int(b), 1e9), float(d))
            far = [b for b in dist if b not in slack]
            return sorted(far, key=lambda b: (-dist[b], b))
        except Exception:
            return [int(b) for b in self.net.bus.index if int(b) not in self.slack_buses()][::-1]

    def buses_by_degree(self) -> list[int]:
        """Non-slack bus indices, fewest branch connections first: the weak points of the network."""
        deg: dict[int, int] = {}
        for _, row in self.net.line.iterrows():
            for b in (int(row["from_bus"]), int(row["to_bus"])):
                deg[b] = deg.get(b, 0) + 1
        for _, row in self.net.trafo.iterrows() if len(self.net.trafo) else []:
            for b in (int(row["hv_bus"]), int(row["lv_bus"])):
                deg[b] = deg.get(b, 0) + 1
        slack = self.slack_buses()
        return sorted((b for b in deg if b not in slack), key=lambda b: (deg[b], b))

    def lines_by_loading(self) -> list[int]:
        """In-service line indices, most loaded in the base case first. Empty if the base case does not converge."""
        self.run_pf()
        res = getattr(self.net, "res_line", None)
        if res is None or not len(res) or "loading_percent" not in res.columns:
            return [int(i) for i in self.net.line.index]
        order = res["loading_percent"].fillna(-1).sort_values(ascending=False).index
        return [int(i) for i in order if bool(self.net.line.at[i, "in_service"])]

    def load_buses(self) -> list[int]:
        """Buses with an in-service load, largest load first, slack buses excluded."""
        slack = self.slack_buses()
        rows = self.net.load[self.net.load["in_service"]].sort_values("p_mw", ascending=False)
        seen: list[int] = []
        for _, row in rows.iterrows():
            b = int(row["bus"])
            if b not in slack and b not in seen:
                seen.append(b)
        return seen

    @staticmethod
    def pick(candidates: list[int], variant: int, fallback: int = 0) -> int:
        """The variant-th candidate, wrapping round rather than failing on a small network."""
        if not candidates:
            return fallback
        return candidates[variant % len(candidates)]

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

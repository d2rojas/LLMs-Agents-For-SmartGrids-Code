"""N-1 contingency scenarios: one element actually taken out of service.

The original scenarios ran pandapower's contingency analysis with
``write_to_net=True`` and returned the network unchanged: the analysis writes
result columns and leaves every element in service, so the method received the
base network and the scenario injected nothing. Here the analysis is used to
choose the element whose outage is worst, and that element is then switched
out, so the network the method sees carries the contingency.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

import pandapower as pp

from .base import FailureScenario, ScenarioResult


class ContingencyFailureScenarios:
    """Factory for N-1 contingency scenarios."""

    @staticmethod
    def all_scenarios(network_name: str = "case14", variant: int = 0) -> List[FailureScenario]:
        return [LineContingencyOverload(network_name, variant), TrafoContingencyVoltage(network_name, variant)]


def _score_outage(net: pp.pandapowerNet, element: str, idx: int) -> Optional[Tuple[int, float, float]]:
    """(violations, worst loading, worst voltage deviation) on a copy with the element out; None if it does not converge."""
    n = copy.deepcopy(net)
    getattr(n, element).at[idx, "in_service"] = False
    try:
        pp.runpp(n)
    except Exception:
        return None
    if not n.converged:
        return None
    vm = n.res_bus["vm_pu"].dropna()
    over = int((n.res_line["loading_percent"] > 100).sum()) + (int((n.res_trafo["loading_percent"] > 100).sum()) if len(n.trafo) else 0)
    volt = int(((vm < 0.95) | (vm > 1.05)).sum())
    worst_loading = float(n.res_line["loading_percent"].max()) if len(n.res_line) else 0.0
    dev = float((vm - 1.0).abs().max()) if len(vm) else 0.0
    return over + volt, worst_loading, dev


def _most_loaded_line(net: pp.pandapowerNet) -> Optional[int]:
    """The line ``topology_redirection`` removes; the contingency scenarios pick another one."""
    try:
        return int(net.res_line["loading_percent"].idxmax()) if len(net.res_line) else None
    except Exception:
        return None


def _rank_outages(net: pp.pandapowerNet, element: str, prefer: str, exclude: Tuple[int, ...] = ()) -> List[int]:
    """In-service elements ranked by how bad their single outage is, worst first.

    ``prefer`` is ``"loading"`` for the line scenario (worst branch loading first)
    or ``"voltage"`` for the transformer scenario (worst voltage deviation first);
    the violation count breaks ties in both. Outages that do not converge are
    ranked last: they are the non-convergence scenarios' job, not this one's.
    """
    df = getattr(net, element)
    scored: List[Tuple[Tuple[float, float], int]] = []
    unconverged: List[int] = []
    for idx in df.index:
        if not bool(df.at[idx, "in_service"]) or int(idx) in exclude:
            continue
        sc = _score_outage(net, element, int(idx))
        if sc is None:
            unconverged.append(int(idx))
            continue
        nviol, loading, dev = sc
        key = (loading, float(nviol)) if prefer == "loading" else (dev, float(nviol))
        scored.append((key, int(idx)))
    scored.sort(key=lambda t: (-t[0][0], -t[0][1], t[1]))
    return [i for _k, i in scored] + unconverged


def _pick(ranked: List[int], variant: int, fallback: int) -> int:
    return ranked[variant % len(ranked)] if ranked else fallback


class LineContingencyOverload(FailureScenario):
    """Take out of service the line whose N-1 outage produces the worst branch loading."""

    def describe(self) -> str:
        return (
            f"N-1 on {self.network_name}: the single line whose outage produces the worst thermal "
            f"loading is taken out of service."
        )

    def apply(self) -> ScenarioResult:
        self.run_pf()
        # topology_redirection takes the most loaded line; this scenario takes the
        # variant-th worst N-1 line among the rest, so the two never coincide.
        most = _most_loaded_line(self.net)
        ranked = _rank_outages(self.net, "line", "loading", exclude=(most,) if most is not None else ())
        worst = _pick(ranked, self.variant, int(self.net.line.index[0]))
        self.net.line.at[worst, "in_service"] = False
        converged = self.run_pf()
        overloaded = self.net.res_line[self.net.res_line["loading_percent"] > 100].index.tolist() if converged else []
        return ScenarioResult(
            scenario_name="line_contingency_overload",
            network_name=self.network_name,
            failure_type="contingency",
            root_causes=[
                f"Line {worst} taken out of service (worst N-1 line outage)",
                "Its flow is redirected through the remaining branches",
            ],
            affected_components={"line": [worst] + [int(i) for i in overloaded]},
            known_fix="Restore the line, or relieve the overloaded corridor by redispatch or curtailment",
            metadata={"outaged_line": worst, "variant": self.variant, "converged": converged, "overloaded_lines": [int(i) for i in overloaded]},
        )


class TrafoContingencyVoltage(FailureScenario):
    """Take out of service the transformer whose N-1 outage moves voltages the most."""

    def describe(self) -> str:
        return (
            f"N-1 on {self.network_name}: the single transformer whose outage produces the worst "
            f"voltage deviation is taken out of service."
        )

    def apply(self) -> ScenarioResult:
        self.run_pf()
        if len(self.net.trafo) == 0:
            # IEEE-30 as shipped by pandapower has no transformer table: fall back to the
            # second-worst line outage so the scenario still injects a contingency.
            most = _most_loaded_line(self.net)
            used = _rank_outages(self.net, "line", "loading", exclude=(most,) if most is not None else ())[:2]
            excl = tuple(x for x in ([most] + used) if x is not None)
            ranked = _rank_outages(self.net, "line", "voltage", exclude=excl)
            worst = _pick(ranked, self.variant, int(self.net.line.index[-1]))
            self.net.line.at[worst, "in_service"] = False
            converged = self.run_pf()
            violated = self.net.res_bus[(self.net.res_bus["vm_pu"] < 0.95) | (self.net.res_bus["vm_pu"] > 1.05)].index.tolist() if converged else []
            return ScenarioResult(
                scenario_name="trafo_contingency_voltage",
                network_name=self.network_name,
                failure_type="contingency",
                root_causes=[f"Line {worst} taken out of service (no transformers in this network; worst voltage N-1 line outage)"],
                affected_components={"line": [worst], "bus": [int(b) for b in violated]},
                known_fix="Restore the branch or add voltage support at the affected buses",
                metadata={"outaged_line": worst, "variant": self.variant, "no_trafo": True, "converged": converged, "violated_buses": [int(b) for b in violated]},
            )
        ranked = _rank_outages(self.net, "trafo", "voltage")
        worst = _pick(ranked, self.variant, int(self.net.trafo.index[0]))
        self.net.trafo.at[worst, "in_service"] = False
        converged = self.run_pf()
        violated = self.net.res_bus[(self.net.res_bus["vm_pu"] < 0.95) | (self.net.res_bus["vm_pu"] > 1.05)].index.tolist() if converged else []
        return ScenarioResult(
            scenario_name="trafo_contingency_voltage",
            network_name=self.network_name,
            failure_type="contingency",
            root_causes=[
                f"Transformer {worst} taken out of service (worst N-1 transformer outage)",
                "Voltage regulation across it is lost; downstream buses move",
            ],
            affected_components={"trafo": [worst], "bus": [int(b) for b in violated]},
            known_fix="Restore the transformer or add voltage support at the affected buses",
            metadata={"outaged_trafo": worst, "variant": self.variant, "converged": converged, "violated_buses": [int(b) for b in violated]},
        )

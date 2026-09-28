"""The request every method receives for a scenario: the text, and the evidence block.

One request per scenario instance, one template. The evidence block is the
system data: what the solver returned for the injected network, plus the
violations the base network already had so the method knows what is not its
job. Every method receives the same request and the same block; the methods
without tools additionally receive the tool catalogue as text, which the
methods with tools receive as schemas.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

import pandapower as pp

from config import MAX_LOADING_PERCENT, NETWORK_LABELS, V_MAX_PU, V_MIN_PU
from evaluation import scenarios as S
from solver.evidence import EvidenceCollector
from solver.network import load_network, network_hash
from solver.violations import Key, State, base_violation_keys, observe, served_load_mw


@dataclass
class Request:
    request_id: str            # case14-line_contingency_overload-v0
    network: str
    scenario_id: str
    variant: int
    category: str
    label: str
    text: str
    evidence_text: str
    injected: S.Injected
    initial: State
    base_keys: FrozenSet[Key]
    net: pp.pandapowerNet      # the injected network, power flow attempted
    network_hash: str
    base_load_mw: float = 0.0  # the unmodified network's active demand, the load-served denominator
    truth: Any = None

    def as_record(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id, "network": self.network, "scenario_id": self.scenario_id,
            "variant": self.variant, "category": self.category, "label": self.label, "text": self.text,
            "injected": self.injected.as_dict(), "initial_state": self.initial.as_dict(),
            "base_violations": sorted(f"{k}:{i}" for k, i in self.base_keys), "network_hash": self.network_hash,
            "base_load_mw": self.base_load_mw,
        }


def request_text(network: str, initial: State) -> str:
    name = NETWORK_LABELS.get(network, network)
    if not initial.converged:
        opening = f"The AC power flow on the {name} system ({network}) did not converge."
    elif initial.islanded_load_buses:
        opening = (f"The AC power flow on the {name} system ({network}) converged, but {len(initial.islanded_load_buses)} "
                   f"bus(es) with load are islanded and {initial.n_new} new limit violation(s) appeared.")
    elif initial.n_new:
        opening = f"The AC power flow on the {name} system ({network}) converged with {initial.n_new} new limit violation(s)."
    else:
        opening = f"The AC power flow on the {name} system ({network}) converged and shows no new limit violation."
    return (
        f"{opening} Diagnose the cause and restore a secure operating point: the power flow converges, no in-service "
        f"load is on an islanded bus, every bus voltage is within [{V_MIN_PU:.2f}, {V_MAX_PU:.2f}] p.u., and no line or "
        f"transformer is above {MAX_LOADING_PERCENT:.0f} % loading, apart from the violations the base network already "
        f"has. Use only the actions available. Report the diagnosis, the actions taken, and the final state."
    )


def evidence_block(net: pp.pandapowerNet, base_keys: FrozenSet[Key], initial: State) -> str:
    """The solver's evidence for the injected network, with the base network's own violations listed apart."""
    report = EvidenceCollector(v_min=V_MIN_PU, v_max=V_MAX_PU, max_loading=MAX_LOADING_PERCENT).collect(net)
    lines = [report.to_text()]
    # the switching state is visible network data, as it is on an operator's screen; the smoke
    # test showed the model missing an out-of-service line it had queried and not read
    out: List[str] = []
    for el in ("line", "trafo", "gen", "sgen", "load", "shunt"):
        df = getattr(net, el, None)
        if df is not None and len(df):
            idx = [int(i) for i in df.index if not bool(df.at[i, "in_service"])]
            if idx:
                out.append(f"{el} {idx}")
    lines.append("")
    lines.append("── SWITCHING STATE ──")
    lines.append("  Elements out of service: " + ("; ".join(out) if out else "none"))
    base = sorted(base_keys)
    lines.append("")
    lines.append("── BASE NETWORK (before the fault) ──")
    if base:
        lines.append(f"  The unmodified network already violates limits at {len(base)} element(s); these do not count "
                     f"against the repair: " + ", ".join(f"{k} {i}" for k, i in base))
    else:
        lines.append("  The unmodified network has no limit violation.")
    if initial.converged:
        lines.append(f"  New violations introduced by the fault: {initial.n_new}" +
                     (" (" + ", ".join(f"{k} {i}" for k, i in sorted(initial.new_keys)) + ")" if initial.new_keys else ""))
        if initial.islanded_load_buses:
            lines.append(f"  Buses with in-service load and no path to a slack bus: {initial.islanded_load_buses}")
    return "\n".join(lines)


def build_request(network: str, scenario_id: str, variant: int = 0) -> Request:
    base = load_network(network)
    base_keys = base_violation_keys(base)
    net, truth, injected = S.build(network, scenario_id, variant)
    h = network_hash(net)
    initial = observe(net, base_keys, in_place=True)  # leaves the power-flow results on the net the method receives
    return Request(
        request_id=S.instance_id(network, scenario_id, variant),
        network=network, scenario_id=scenario_id, variant=variant,
        category=S.CATEGORY_OF[scenario_id], label=S.LABEL_OF[scenario_id],
        text=request_text(network, initial),
        evidence_text=evidence_block(net, base_keys, initial),
        injected=injected, initial=initial, base_keys=base_keys, net=net, network_hash=h,
        base_load_mw=round(served_load_mw(base), 2), truth=truth,
    )


def build_requests(networks: List[str], scenario_ids: Optional[List[str]] = None) -> List[Request]:
    """Every instance of the given networks, in table order. ``scenario_ids`` filters by class."""
    keep = set(scenario_ids) if scenario_ids else None
    return [build_request(n, sid, v) for n in networks for sid, v in S.INSTANCES if keep is None or sid in keep]


def fresh_network(req: Request) -> pp.pandapowerNet:
    """A deep copy of the injected network for one method to work on."""
    return copy.deepcopy(req.net)

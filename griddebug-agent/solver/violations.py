"""Observe a network: what the solver says about it, and nothing else.

``observe(net, base)`` runs the AC power flow on a copy and returns a ``State``:
whether it converged, the buses outside the voltage band, the branches above
their rating, the buses that carry an in-service load and have no path to a
slack, and how many of those violations are *new*, that is, not already present
in the unmodified base network.

Why relative to a base. Two of the three IEEE cases shipped with pandapower
violate the fixed 0.95 to 1.05 p.u. band before anything is done to them
(IEEE-14 has three buses above 1.05, IEEE-57 has thirty-nine below 0.95). A
repair target of "zero violations" on those networks asks the method to fix
the base case rather than the injected fault, and on IEEE-57 makes the size of
the network look like the cause of every failure. So a violation counts against
a method only if the same bus or branch was inside its limits in the base
network. The absolute count is kept beside it.

A network that does not converge has no countable violations. That is a state
of its own, never a count of zero.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

import pandapower as pp

from config import MAX_LOADING_PERCENT, V_MAX_PU, V_MIN_PU
from solver.network import run_power_flow

Key = Tuple[str, int]  # ("bus", 7), ("line", 3), ("trafo", 0)


@dataclass
class State:
    converged: bool
    voltage: List[Dict[str, Any]] = field(default_factory=list)   # {bus, vm_pu, limit, kind}
    thermal: List[Dict[str, Any]] = field(default_factory=list)   # {element, index, loading_percent}
    islanded_load_buses: List[int] = field(default_factory=list)
    nan_buses: List[int] = field(default_factory=list)
    keys: FrozenSet[Key] = frozenset()
    new_keys: FrozenSet[Key] = frozenset()
    vm_min: Optional[float] = None
    vm_max: Optional[float] = None
    max_loading: Optional[float] = None

    @property
    def n_violations(self) -> Optional[int]:
        """Absolute count, or None when the state has no countable violations (not converged)."""
        return len(self.keys) if self.converged else None

    @property
    def n_new(self) -> Optional[int]:
        return len(self.new_keys) if self.converged else None

    @property
    def secure(self) -> bool:
        """Converged, no islanded load, no violation beyond the base network."""
        return self.converged and not self.islanded_load_buses and not self.nan_buses and len(self.new_keys) == 0

    @property
    def label(self) -> str:
        if not self.converged:
            return "not_converged"
        if self.islanded_load_buses:
            return "islanded_load"
        return "secure" if not self.new_keys else "violations"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "converged": self.converged,
            "label": self.label,
            "n_violations": self.n_violations,
            "n_new_violations": self.n_new,
            "n_voltage": len(self.voltage) if self.converged else None,
            "n_thermal": len(self.thermal) if self.converged else None,
            "voltage": self.voltage,
            "thermal": self.thermal,
            "new": sorted(f"{k}:{i}" for k, i in self.new_keys),
            "islanded_load_buses": self.islanded_load_buses,
            "nan_buses": self.nan_buses,
            "vm_min": self.vm_min,
            "vm_max": self.vm_max,
            "max_loading": self.max_loading,
            "secure": self.secure,
        }


def islanded_load_buses(net: pp.pandapowerNet) -> List[int]:
    """Buses with an in-service load and no path (through in-service branches) to any slack bus."""
    try:
        import networkx as nx
        from pandapower.topology import create_nxgraph

        g = create_nxgraph(net, respect_switches=True, include_out_of_service=False)
        slack = {int(b) for b in net.ext_grid.loc[net.ext_grid["in_service"], "bus"]}
        reach: Set[int] = set()
        for s in slack:
            if s in g:
                reach |= set(nx.descendants(g, s)) | {s}
        out: Set[int] = set()
        for _, row in net.load.iterrows():
            if bool(row.get("in_service", True)) and (float(row.get("p_mw", 0)) > 0 or float(row.get("q_mvar", 0)) > 0):
                b = int(row["bus"])
                if b not in reach:
                    out.add(b)
        return sorted(out)
    except Exception:
        return []


def _violations(net: pp.pandapowerNet) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Set[Key], List[int]]:
    voltage: List[Dict[str, Any]] = []
    thermal: List[Dict[str, Any]] = []
    keys: Set[Key] = set()
    nan_buses: List[int] = []
    res_bus = getattr(net, "res_bus", None)
    if res_bus is not None and len(res_bus):
        for idx, row in res_bus.iterrows():
            vm = row.get("vm_pu")
            if vm is None or vm != vm:
                nan_buses.append(int(idx))
                continue
            vm = float(vm)
            if vm < V_MIN_PU:
                voltage.append({"bus": int(idx), "vm_pu": round(vm, 4), "limit": V_MIN_PU, "kind": "under"})
                keys.add(("bus", int(idx)))
            elif vm > V_MAX_PU:
                voltage.append({"bus": int(idx), "vm_pu": round(vm, 4), "limit": V_MAX_PU, "kind": "over"})
                keys.add(("bus", int(idx)))
    for element in ("line", "trafo"):
        res = getattr(net, f"res_{element}", None)
        if res is None or not len(res) or "loading_percent" not in res.columns:
            continue
        for idx, row in res.iterrows():
            ld = row.get("loading_percent")
            if ld is None or ld != ld:
                continue
            if float(ld) > MAX_LOADING_PERCENT:
                thermal.append({"element": element, "index": int(idx), "loading_percent": round(float(ld), 1)})
                keys.add((element, int(idx)))
    return voltage, thermal, keys, nan_buses


def observe(net: pp.pandapowerNet, base_keys: Optional[FrozenSet[Key]] = None, *, in_place: bool = False) -> State:
    """Run the power flow (on a copy unless ``in_place``) and describe what the solver returned."""
    target = net if in_place else copy.deepcopy(net)
    converged = run_power_flow(target)
    if not converged:
        return State(converged=False)
    voltage, thermal, keys, nan_buses = _violations(target)
    islanded = islanded_load_buses(target)
    # a NaN voltage on a bus with no in-service load is an inert island: not a violation
    real_nan = [b for b in nan_buses if b in set(islanded)]
    base = base_keys or frozenset()
    res_bus = target.res_bus
    vals = [float(v) for v in res_bus["vm_pu"].tolist() if v == v]
    loads = []
    for element in ("line", "trafo"):
        res = getattr(target, f"res_{element}", None)
        if res is not None and len(res) and "loading_percent" in res.columns:
            loads += [float(v) for v in res["loading_percent"].tolist() if v == v]
    return State(
        converged=True,
        voltage=voltage,
        thermal=thermal,
        islanded_load_buses=islanded,
        nan_buses=real_nan,
        keys=frozenset(keys),
        new_keys=frozenset(keys - base),
        vm_min=round(min(vals), 4) if vals else None,
        vm_max=round(max(vals), 4) if vals else None,
        max_loading=round(max(loads), 1) if loads else None,
    )


def served_load_mw(net: pp.pandapowerNet) -> float:
    """Active demand actually served, in MW: in service and connected to a slack bus.

    Load sitting on an islanded bus is in service and is not being served. Counting it
    said "100 % of the demand is met" about a network whose repair had stranded five
    buses, which is the opposite of what the column is for.
    """
    df = getattr(net, "load", None)
    if df is None or not len(df):
        return 0.0
    stranded = set(islanded_load_buses(net))
    rows = df.loc[df["in_service"]]
    if stranded:
        rows = rows[~rows["bus"].astype(int).isin(stranded)]
    return float(rows["p_mw"].sum())


def base_violation_keys(net: pp.pandapowerNet) -> FrozenSet[Key]:
    """The violations the unmodified network already has; the floor every scenario is measured against."""
    st = observe(net)
    return st.keys if st.converged else frozenset()

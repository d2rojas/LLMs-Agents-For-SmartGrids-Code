"""Load a test network by name, and fingerprint one.

The networks are the IEEE cases shipped with pandapower (``pandapower.networks``).
They are library data rather than files in this repository, so the scenario
manifest under ``data/scenarios/`` records a content hash of every injected
network; a pandapower release that changes a case fails that check on load
instead of silently changing the benchmark.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import warnings
from typing import Any, Dict

import pandapower as pp
import pandapower.networks as pn

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", message=".*Voltage controlling elements.*")
logging.getLogger("pandapower").setLevel(logging.ERROR)

# The tables whose values define the network for the purpose of the benchmark.
_TABLES = ("bus", "line", "trafo", "gen", "sgen", "load", "shunt", "ext_grid", "switch")


# Branch ratings, the same rule as the power-flow case study (power-flow-agent/solver/ratings.py).
# The IEEE cases carry no usable line ratings (the 9900 MVA placeholder of MATPOWER becomes a
# max_i_ka that puts the base case at 1.5 % loading on IEEE-14), so no thermal scenario could
# ever overload a line. Every line is rated at RATING_FACTOR times its base-case current, with
# a floor of RATING_FLOOR_FRAC of the largest base current. Transformers keep their sn_mva:
# pandapower derives their impedance from it.
RATING_FACTOR = 1.25
RATING_FLOOR_FRAC = 0.05


def assign_line_ratings(net: pp.pandapowerNet, *, factor: float = RATING_FACTOR, floor_frac: float = RATING_FLOOR_FRAC) -> pp.pandapowerNet:
    import copy

    import numpy as np

    probe = copy.deepcopy(net)
    try:
        pp.runpp(probe)
    except Exception:
        return net
    if not len(probe.res_line):
        return net
    i_line = np.fmax(probe.res_line["i_from_ka"].values, probe.res_line["i_to_ka"].values)
    finite = [float(v) for v in i_line if v == v]
    i_max = max(finite) if finite else 0.0
    net.line["max_i_ka"] = [factor * max(float(i) if i == i else 0.0, floor_frac * i_max) for i in i_line]
    return net


def load_network(name: str, *, ratings: bool = True) -> pp.pandapowerNet:
    """A fresh copy of ``pandapower.networks.<name>()``, with line ratings by the shared rule."""
    fn = getattr(pn, name, None)
    if fn is None or not inspect.isfunction(fn):
        raise ValueError(f"unknown network {name!r}: not a function in pandapower.networks")
    net = fn()
    return assign_line_ratings(net) if ratings else net


def run_power_flow(net: pp.pandapowerNet) -> bool:
    """Run the AC power flow in place; True when it converged. Never raises."""
    try:
        pp.runpp(net)
        return bool(net.converged)
    except Exception:
        net.converged = False  # type: ignore[attr-defined]
        return False


def network_tables(net: pp.pandapowerNet) -> Dict[str, Any]:
    """The element tables as plain rows, rounded, for hashing and for the manifest."""
    out: Dict[str, Any] = {}
    for name in _TABLES:
        df = getattr(net, name, None)
        if df is None or len(df) == 0:
            out[name] = []
            continue
        rows = []
        for idx, row in df.iterrows():
            rec: Dict[str, Any] = {"index": int(idx)}
            for col in sorted(df.columns):
                v = row[col]
                if isinstance(v, float):
                    rec[col] = None if v != v else round(v, 8)
                elif hasattr(v, "item"):
                    try:
                        v2 = v.item()
                        rec[col] = None if isinstance(v2, float) and v2 != v2 else v2
                    except Exception:
                        rec[col] = str(v)
                elif isinstance(v, (bool, int, str)) or v is None:
                    rec[col] = v
                else:
                    rec[col] = str(v)
            rows.append(rec)
        out[name] = rows
    return out


def network_hash(net: pp.pandapowerNet) -> str:
    """sha256 prefix of the element tables; the same network hashes the same on any machine."""
    blob = json.dumps(network_tables(net), sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]

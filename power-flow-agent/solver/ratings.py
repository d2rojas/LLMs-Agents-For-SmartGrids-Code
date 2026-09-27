"""Branch thermal ratings and the loading definition used everywhere.

The MATPOWER files of the IEEE 14, 57, 118 and 300-bus cases carry no usable branch ratings
(rateA is 0 or the 9900 MVA placeholder), so "overloaded lines" could never be non-empty and
the N-1 scan could only count voltage violations. Every system therefore gets the same rule
at load time: the rating of a branch is RATING_FACTOR times its apparent-power flow in the
unperturbed base case (from side; hv side for transformers), with a floor of RATING_FLOOR_FRAC
of the largest base flow so lightly loaded branches do not get a near-zero rating. The rule
replaces the file's ratings on every system, the 30-bus one included, so all five are treated
alike; it is the usual convention for N-1 studies on these test cases.

Loading is then one definition for every method, tool and reference:
    loading_percent = 100 * sqrt(p_from_mw**2 + q_from_mvar**2) / rating_mva
computed on the from side after every solve (``apply_rating_loading``), which the no-tools
methods can reproduce from their own flows and the ``rating_mva`` column of the case tables.
Transformer ``sn_mva`` is never changed (pandapower derives the transformer impedance from it).
"""
from __future__ import annotations

import copy
import math
from typing import Any

import numpy as np

RATING_FACTOR = 1.25
RATING_FLOOR_FRAC = 0.05


def _finite(x: float) -> float:
    return float(x) if isinstance(x, (int, float)) and math.isfinite(float(x)) else 0.0


def assign_branch_ratings(net: Any, *, factor: float = RATING_FACTOR, floor_frac: float = RATING_FLOOR_FRAC) -> Any:
    """Add ``rating_mva`` to ``net.line`` and ``net.trafo`` from a base-case solve on a copy; also
    sets ``net.line.max_i_ka`` from the same rule so pandapower's own line loading agrees."""
    import pandapower as pp

    net2 = copy.deepcopy(net)
    try:
        pp.runpp(net2)
    except Exception:
        return net
    s_line = np.hypot(net2.res_line["p_from_mw"].values, net2.res_line["q_from_mvar"].values) if len(net2.res_line) else np.array([])
    has_trafo = hasattr(net2, "res_trafo") and len(net2.res_trafo) > 0
    s_trafo = np.hypot(net2.res_trafo["p_hv_mw"].values, net2.res_trafo["q_hv_mvar"].values) if has_trafo else np.array([])
    s_max = max([_finite(v) for v in list(s_line) + list(s_trafo)] or [0.0])
    floor = floor_frac * s_max

    def rating(s: float) -> float:
        return factor * max(_finite(s), floor)

    net.line["rating_mva"] = [rating(s) for s in s_line]
    if has_trafo:
        net.trafo["rating_mva"] = [rating(s) for s in s_trafo]
    if len(net2.res_line):
        i_line = np.fmax(net2.res_line["i_from_ka"].values, net2.res_line["i_to_ka"].values)
        i_max = max([_finite(v) for v in i_line] or [0.0])
        net.line["max_i_ka"] = [factor * max(_finite(i), floor_frac * i_max) for i in i_line]
    return net


def apply_rating_loading(net: Any) -> None:
    """Overwrite pandapower's loading_percent with the rating-based definition, after a solve."""
    if hasattr(net, "res_line") and len(net.res_line) and "rating_mva" in net.line.columns:
        s = np.hypot(net.res_line["p_from_mw"].values, net.res_line["q_from_mvar"].values)
        r = net.line["rating_mva"].values.astype(float)
        with np.errstate(divide="ignore", invalid="ignore"):
            net.res_line["loading_percent"] = np.where(r > 0, 100.0 * s / r, 0.0)
    if hasattr(net, "res_trafo") and len(net.res_trafo) and hasattr(net, "trafo") and "rating_mva" in net.trafo.columns:
        s = np.hypot(net.res_trafo["p_hv_mw"].values, net.res_trafo["q_hv_mvar"].values)
        r = net.trafo["rating_mva"].values.astype(float)
        with np.errstate(divide="ignore", invalid="ignore"):
            net.res_trafo["loading_percent"] = np.where(r > 0, 100.0 * s / r, 0.0)

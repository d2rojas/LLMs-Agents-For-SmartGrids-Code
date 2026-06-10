"""Topology edits on pandapower net tables only.

These operations intentionally DO NOT run power flow.
"""

from __future__ import annotations

from typing import Any

import math
import re


def _parse_bus_name_to_id(name: object) -> int | None:
    if name is None:
        return None
    s = str(name).strip()
    if not s:
        return None
    if re.fullmatch(r"[-+]?\d+", s):
        return int(s)
    return None


def _bus_display_id(net: Any, bus_idx: int) -> int:
    try:
        parsed = _parse_bus_name_to_id(net.bus.at[bus_idx, "name"])
        if parsed is not None:
            return int(parsed)
    except Exception:
        pass
    return int(bus_idx) + 1


def _resolve_bus_index(net: Any, bus_id: int) -> int:
    if hasattr(net, "bus") and "name" in net.bus.columns:
        matches = net.bus.index[net.bus["name"].astype(str) == str(bus_id)].tolist()
        if matches:
            return int(matches[0])
        for idx, name in net.bus["name"].items():
            parsed = _parse_bus_name_to_id(name)
            if parsed is not None and int(parsed) == int(bus_id):
                return int(idx)
    for idx in net.bus.index.tolist():
        if int(_bus_display_id(net, int(idx))) == int(bus_id):
            return int(idx)
    if bus_id in net.bus.index:
        return int(bus_id)
    raise ValueError(f"Invalid bus_id: {bus_id}")


def _find_line_or_trafo_between(net: Any, fb: int, tb: int) -> tuple[str, int] | None:
    if hasattr(net, "line") and len(net.line) > 0:
        for idx, row in net.line.iterrows():
            a, b = int(row["from_bus"]), int(row["to_bus"])
            if (a == fb and b == tb) or (a == tb and b == fb):
                return ("line", int(idx))

    if hasattr(net, "trafo") and len(net.trafo) > 0:
        for idx, row in net.trafo.iterrows():
            a, b = int(row["hv_bus"]), int(row["lv_bus"])
            if (a == fb and b == tb) or (a == tb and b == fb):
                return ("trafo", int(idx))

    return None


def _append_load_row(net: Any, bus_idx: int, p_mw: float, q_mvar: float) -> int:
    if not hasattr(net, "load"):
        raise ValueError("Current network has no load table")

    if len(net.load.index) == 0:
        new_idx = 0
    else:
        new_idx = int(max(net.load.index)) + 1

    # Fill all existing columns with safe defaults, then set required fields.
    net.load.loc[new_idx, :] = [math.nan] * len(net.load.columns)

    if "bus" in net.load.columns:
        net.load.at[new_idx, "bus"] = int(bus_idx)
    if "p_mw" in net.load.columns:
        net.load.at[new_idx, "p_mw"] = float(p_mw)
    if "q_mvar" in net.load.columns:
        net.load.at[new_idx, "q_mvar"] = float(q_mvar)
    if "in_service" in net.load.columns:
        net.load.at[new_idx, "in_service"] = True
    if "scaling" in net.load.columns:
        net.load.at[new_idx, "scaling"] = 1.0

    return new_idx


def modify_load(net: Any, bus_id: int, p_mw: float, q_mvar: float | None = None) -> None:
    """Modify load table only; do not solve power flow."""

    bus_idx = _resolve_bus_index(net, int(bus_id))
    if not hasattr(net, "load"):
        raise ValueError("Current network has no load table")

    q = float(q_mvar) if q_mvar is not None else 0.0
    rows = net.load.index[net.load["bus"] == bus_idx].tolist() if "bus" in net.load.columns else []

    if not rows:
        _append_load_row(net, bus_idx=bus_idx, p_mw=float(p_mw), q_mvar=q)
        return

    first = int(rows[0])
    if "p_mw" in net.load.columns:
        net.load.at[first, "p_mw"] = float(p_mw)
    if "q_mvar" in net.load.columns and q_mvar is not None:
        net.load.at[first, "q_mvar"] = float(q_mvar)

    # Keep one effective load row at target bus; zero out others to avoid double counting.
    for extra in rows[1:]:
        ex = int(extra)
        if "p_mw" in net.load.columns:
            net.load.at[ex, "p_mw"] = 0.0
        if "q_mvar" in net.load.columns and q_mvar is not None:
            net.load.at[ex, "q_mvar"] = 0.0


def disconnect_line(net: Any, from_bus: int, to_bus: int) -> None:
    """Set target line/trafo out of service in tables only; do not solve."""

    fb = _resolve_bus_index(net, int(from_bus))
    tb = _resolve_bus_index(net, int(to_bus))
    hit = _find_line_or_trafo_between(net, fb, tb)
    if hit is None:
        raise ValueError(f"No branch found between bus {from_bus} and bus {to_bus}")

    kind, idx = hit
    if kind == "line":
        net.line.at[idx, "in_service"] = False
    else:
        net.trafo.at[idx, "in_service"] = False


def reconnect_line(net: Any, from_bus: int, to_bus: int) -> None:
    """Set target line/trafo in service in tables only; do not solve."""

    fb = _resolve_bus_index(net, int(from_bus))
    tb = _resolve_bus_index(net, int(to_bus))
    hit = _find_line_or_trafo_between(net, fb, tb)
    if hit is None:
        raise ValueError(f"No branch found between bus {from_bus} and bus {to_bus}")

    kind, idx = hit
    if kind == "line":
        net.line.at[idx, "in_service"] = True
    else:
        net.trafo.at[idx, "in_service"] = True



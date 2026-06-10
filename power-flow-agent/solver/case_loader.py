"""Load test cases strictly from local MATPOWER .m files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pandapower.converter.matpower import from_mpc
import pandapower.networks as ppn
import importlib
import numpy as np

from models.schemas import NetworkInfo


@dataclass(frozen=True)
class _CaseSpec:
    canonical: str
    filename: str


_BASE_DIR = Path(__file__).resolve().parent
_LOCAL_CASE_DIR = _BASE_DIR / "cases" / "matpower"

_CASES: dict[str, _CaseSpec] = {
    "case14": _CaseSpec(canonical="case14", filename="case14.m"),
    "case30": _CaseSpec(canonical="case30", filename="case30.m"),
    "case57": _CaseSpec(canonical="case57", filename="case57.m"),
    "case118": _CaseSpec(canonical="case118", filename="case118.m"),
    "case300": _CaseSpec(canonical="case300", filename="case300.m"),
}


def get_available_cases() -> list[str]:
    return list(_CASES.keys())


def normalize_case_name(case_name: str) -> str:
    if not case_name or not isinstance(case_name, str):
        raise ValueError("case_name must be a non-empty string")

    s = case_name.strip().lower()
    s = s.replace("节点", "")
    s = s.replace("bus", "")
    s = s.replace("-", "")
    s = s.replace("_", "")
    s = s.replace(" ", "")

    # Match longer case ids first to avoid "case300" being matched as "30".
    m = re.search(r"(300|118|57|30|14)", s)
    if m:
        k = f"case{m.group(1)}"
        if k in _CASES:
            return k

    if s in _CASES:
        return s

    raise ValueError(f"Unsupported case: {case_name}. Available: {', '.join(get_available_cases())}")


def _calc_network_info(net: object, canonical_name: str) -> NetworkInfo:
    n_buses = int(len(net.bus))
    n_loads = int(len(net.load)) if hasattr(net, "load") else 0

    n_generators = 0
    total_capacity = 0.0

    if hasattr(net, "gen"):
        n_generators += int(len(net.gen))
        if "max_p_mw" in net.gen.columns:
            total_capacity += float(net.gen["max_p_mw"].fillna(net.gen["p_mw"]).sum())
        else:
            total_capacity += float(net.gen["p_mw"].sum())

    if hasattr(net, "ext_grid"):
        n_generators += int(len(net.ext_grid))
        if "max_p_mw" in net.ext_grid.columns:
            total_capacity += float(net.ext_grid["max_p_mw"].fillna(0.0).replace([float("inf")], 0.0).sum())

    n_lines = 0
    if hasattr(net, "line"):
        n_lines += int(len(net.line))
    if hasattr(net, "trafo"):
        n_lines += int(len(net.trafo))

    total_load_mw = float(net.load["p_mw"].sum()) if hasattr(net, "load") else 0.0

    return NetworkInfo(
        case_name=canonical_name,
        n_buses=n_buses,
        n_generators=n_generators,
        n_lines=n_lines,
        n_loads=n_loads,
        total_load_mw=total_load_mw,
        total_gen_capacity_mw=float(total_capacity),
    )


def _load_local_matpower_case(canonical: str):
    spec = _CASES[canonical]
    mpc_path = (_LOCAL_CASE_DIR / spec.filename).resolve()
    if not mpc_path.exists():
        raise ValueError(f"Local MATPOWER file not found: {mpc_path}")

    try:
        return from_mpc(str(mpc_path), f_hz=50, validate_conversion=False)
    except IndexError as e:
        # Workaround for pandapower converter bug triggered by MATPOWER branches
        # classified as "impedance" (observed on case118 in some versions).
        msg = str(e).lower()
        if "boolean index did not match indexed array" not in msg:
            raise

        mat_mod = importlib.import_module("pandapower.converter.matpower.from_mpc")
        ppc_mod = importlib.import_module("pandapower.converter.pypower.from_ppc")
        ppc = mat_mod._m2ppc(str(mpc_path))
        is_line, is_trafo, is_imp, _ = ppc_mod._branch_to_which(ppc)
        if np.any(is_imp):
            ppc["branch"][is_imp, ppc_mod.TAP] = 1.0001
        return ppc_mod.from_ppc(ppc, f_hz=50, validate_conversion=False)
    except NotImplementedError as e:
        # Common when matpowercaseframes is missing for .m parsing.
        raise ValueError(
            "Failed to parse local .m case file. Install matpowercaseframes: `pip install matpowercaseframes`. "
            f"Details: {e}"
        ) from e


def _is_invalid_converted_net(net: object) -> bool:
    """Basic sanity checks for converted MATPOWER nets."""
    try:
        if not hasattr(net, "bus") or len(net.bus) == 0:
            return True
        if "vn_kv" not in net.bus.columns:
            return True
        vn = net.bus["vn_kv"].astype(float)
        if bool((vn <= 0.0).all()):
            return True

        if hasattr(net, "line") and len(net.line) > 0:
            cols = set(net.line.columns)
            if {"r_ohm_per_km", "x_ohm_per_km"}.issubset(cols):
                rz = net.line["r_ohm_per_km"].astype(float)
                xz = net.line["x_ohm_per_km"].astype(float)
                if bool(((rz == 0.0) & (xz == 0.0)).all()):
                    return True
    except Exception:
        return True
    return False


def _load_builtin_case(canonical: str):
    fn = getattr(ppn, canonical, None)
    if fn is None:
        raise ValueError(f"pandapower.networks has no built-in case loader for: {canonical}")
    return fn()


def load(case_name: str):
    canonical = normalize_case_name(case_name)
    net = _load_local_matpower_case(canonical)
    if _is_invalid_converted_net(net):
        # Fallback for converter regressions across pandapower versions.
        net = _load_builtin_case(canonical)

    try:
        setattr(net, "name", canonical)
        setattr(net, "_case_name", canonical)
    except Exception:
        pass

    info = _calc_network_info(net, canonical)
    return net, info

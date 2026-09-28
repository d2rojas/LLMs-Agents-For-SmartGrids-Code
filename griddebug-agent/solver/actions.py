"""
Modification tools for the iterative debugger agent.

These represent realistic control-room corrective actions:
generation redispatch, load curtailment, voltage setpoint adjustment,
topology switching, and reactive compensation.
"""
from __future__ import annotations

from typing import Any

import pandapower as pp


TOOL_DEFINITIONS = [
    {
        "name": "adjust_generation",
        "description": "Redispatch: adjust a generator's real power (p_mw) or voltage setpoint (vm_pu). Use to fix power imbalance or voltage issues.",
        "parameters": {
            "gen_index": {"type": "integer", "description": "Index in the generator dataframe."},
            "gen_type": {"type": "string", "description": "'gen', 'sgen', or 'ext_grid'. Default 'gen'."},
            "p_mw_new": {"type": "number", "description": "New real power setpoint in MW (optional)."},
            "vm_pu_new": {"type": "number", "description": "New voltage setpoint in p.u. (optional)."},
        },
    },
    {
        "name": "curtail_load",
        "description": "Curtail a single load by a scale factor (0.0–1.0). Use for targeted load shedding at critical buses.",
        "parameters": {
            "load_index": {"type": "integer", "description": "Index in net.load."},
            "scale_factor": {"type": "number", "description": "Multiplier (e.g. 0.5 = 50% of original). 0.0 sheds completely."},
        },
    },
    {
        "name": "scale_all_loads",
        "description": "Global demand response: scale ALL loads by a factor (0.0–1.0). Use when system-wide generation is insufficient.",
        "parameters": {
            "factor": {"type": "number", "description": "Global multiplier (e.g. 0.8 = reduce all loads to 80%)."},
        },
    },
    {
        "name": "switch_element",
        "description": "Toggle any element in/out of service. Use for topology switching (lines/trafos) or shedding loads/gens.",
        "parameters": {
            "element_type": {"type": "string", "description": "One of 'line', 'trafo', 'gen', 'sgen', 'load', 'shunt'."},
            "element_index": {"type": "integer", "description": "Index in the respective dataframe."},
            "in_service": {"type": "boolean", "description": "True to connect, False to disconnect."},
        },
    },
    {
        "name": "add_shunt_compensation",
        "description": "Add reactive shunt compensation (capacitor/reactor) at a bus for voltage control. Positive q_mvar = capacitive (raises voltage).",
        "parameters": {
            "bus_index": {"type": "integer", "description": "Bus index where shunt is added."},
            "q_mvar": {"type": "number", "description": "Reactive power in Mvar. Positive=capacitive (raises V), negative=inductive (lowers V)."},
        },
    },
    {
        "name": "adjust_voltage_setpoint",
        "description": "Set the voltage setpoint (vm_pu) of a generator or external grid. Use for reactive power / voltage control.",
        "parameters": {
            "element_type": {"type": "string", "description": "'gen' or 'ext_grid'."},
            "element_index": {"type": "integer", "description": "Index in the respective dataframe."},
            "vm_pu_new": {"type": "number", "description": "New voltage magnitude setpoint in p.u. (e.g. 1.02)."},
        },
    },
]


class ModificationTools:
    """Unified modification tools for power system corrective actions."""

    TOOL_DEFINITIONS = TOOL_DEFINITIONS

    @staticmethod
    def adjust_generation(
        net: pp.pandapowerNet,
        gen_index: int,
        gen_type: str = "gen",
        p_mw_new: float | None = None,
        vm_pu_new: float | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Redispatch a generator's P or V setpoint."""
        gen_index = int(gen_index)
        gen_type = gen_type or kwargs.get("gen_type", "gen")
        p_mw_new = p_mw_new if p_mw_new is not None else kwargs.get("p_mw_new")
        vm_pu_new = vm_pu_new if vm_pu_new is not None else kwargs.get("vm_pu_new")

        df_map = {"gen": net.gen, "sgen": net.sgen, "ext_grid": net.ext_grid}
        if gen_type not in df_map:
            return {"error": f"Invalid gen_type '{gen_type}'. Must be 'gen', 'sgen', or 'ext_grid'."}
        df = df_map[gen_type]
        if gen_index not in df.index:
            return {"error": f"No {gen_type} at index {gen_index}."}

        old, new = {}, {}
        if p_mw_new is not None and "p_mw" in df.columns:
            old["p_mw"] = float(df.at[gen_index, "p_mw"])
            df.at[gen_index, "p_mw"] = float(p_mw_new)
            new["p_mw"] = float(p_mw_new)
        if vm_pu_new is not None and "vm_pu" in df.columns:
            old["vm_pu"] = float(df.at[gen_index, "vm_pu"])
            df.at[gen_index, "vm_pu"] = float(vm_pu_new)
            new["vm_pu"] = float(vm_pu_new)

        return {
            "action": "adjust_generation",
            "success": True,
            "gen_type": gen_type,
            "gen_index": gen_index,
            "old_state": old,
            "new_state": new,
        }

    @staticmethod
    def curtail_load(
        net: pp.pandapowerNet,
        load_index: int,
        scale_factor: float,
        **kwargs,
    ) -> dict[str, Any]:
        """Scale down a single load."""
        load_index = int(load_index)
        scale_factor = float(scale_factor if scale_factor is not None else kwargs.get("scale_factor", 0.5))
        if load_index not in net.load.index:
            return {"error": f"No load at index {load_index}."}
        if not (0.0 <= scale_factor <= 1.0):
            return {"error": "scale_factor must be in [0.0, 1.0]."}

        old_p = float(net.load.at[load_index, "p_mw"])
        old_q = float(net.load.at[load_index, "q_mvar"]) if "q_mvar" in net.load.columns else 0.0
        net.load.at[load_index, "p_mw"] = old_p * scale_factor
        if "q_mvar" in net.load.columns:
            net.load.at[load_index, "q_mvar"] = old_q * scale_factor
        if scale_factor == 0.0:
            net.load.at[load_index, "in_service"] = False

        return {
            "action": "curtail_load",
            "success": True,
            "load_index": load_index,
            "old_p_mw": round(old_p, 2),
            "new_p_mw": round(old_p * scale_factor, 2),
            "scale_factor": scale_factor,
        }

    @staticmethod
    def scale_all_loads(
        net: pp.pandapowerNet,
        factor: float = 0.8,
        **kwargs,
    ) -> dict[str, Any]:
        """Global demand response: scale all loads."""
        factor = float(factor if factor is not None else kwargs.get("factor", 0.8))
        if not (0.0 <= factor <= 2.0):
            return {"error": "factor must be in [0.0, 2.0]."}

        old_total = float(net.load["p_mw"].sum())
        net.load["p_mw"] *= factor
        if "q_mvar" in net.load.columns:
            net.load["q_mvar"] *= factor
        new_total = float(net.load["p_mw"].sum())

        return {
            "action": "scale_all_loads",
            "success": True,
            "factor": factor,
            "old_total_p_mw": round(old_total, 2),
            "new_total_p_mw": round(new_total, 2),
        }

    @staticmethod
    def switch_element(
        net: pp.pandapowerNet,
        element_type: str,
        element_index: int,
        in_service: bool,
        **kwargs,
    ) -> dict[str, Any]:
        """Toggle any element in/out of service."""
        element_type = element_type or kwargs.get("element_type", "line")
        element_index = int(element_index)
        in_service = bool(in_service if in_service is not None else kwargs.get("in_service", True))

        valid = {"line": net.line, "trafo": net.trafo, "gen": net.gen,
                 "sgen": net.sgen, "load": net.load}
        if hasattr(net, "shunt") and not net.shunt.empty:
            valid["shunt"] = net.shunt

        if element_type not in valid:
            return {"error": f"Invalid element_type '{element_type}'. Valid: {list(valid.keys())}"}
        df = valid[element_type]
        if element_index not in df.index:
            return {"error": f"No {element_type} at index {element_index}."}

        old_status = bool(df.at[element_index, "in_service"])
        df.at[element_index, "in_service"] = in_service

        return {
            "action": "switch_element",
            "success": True,
            "element_type": element_type,
            "element_index": element_index,
            "old_in_service": old_status,
            "new_in_service": in_service,
        }

    # Backward compat aliases used by _apply_automated_fix
    @staticmethod
    def toggle_element(net, element_type, element_index, in_service, **kw):
        return ModificationTools.switch_element(net, element_type, int(element_index), bool(in_service), **kw)

    @staticmethod
    def shed_load(net, load_index, scale_factor=0.0, **kw):
        return ModificationTools.curtail_load(net, int(load_index), float(scale_factor), **kw)

    @staticmethod
    def add_shunt_compensation(
        net: pp.pandapowerNet,
        bus_index: int,
        q_mvar: float,
        **kwargs,
    ) -> dict[str, Any]:
        """Add a shunt capacitor/reactor at a bus for voltage control."""
        bus_index = int(bus_index)
        q_mvar = float(q_mvar if q_mvar is not None else kwargs.get("q_mvar", 10.0))

        if bus_index not in net.bus.index:
            return {"error": f"No bus at index {bus_index}."}

        vn_kv = float(net.bus.at[bus_index, "vn_kv"])
        # pandapower shunt: q_mvar > 0 = capacitive (generates reactive power)
        pp.create_shunt(net, bus=bus_index, q_mvar=-q_mvar, p_mw=0.0, vn_kv=vn_kv,
                        name=f"compensator_bus{bus_index}")

        return {
            "action": "add_shunt_compensation",
            "success": True,
            "bus_index": bus_index,
            "q_mvar_added": q_mvar,
            "message": f"Added {q_mvar} Mvar {'capacitive' if q_mvar > 0 else 'inductive'} shunt at bus {bus_index}",
        }

    # Backward compat alias
    @staticmethod
    def add_reactive_compensation(net, bus_index, q_mvar, **kw):
        return ModificationTools.add_shunt_compensation(net, int(bus_index), float(q_mvar), **kw)

    @staticmethod
    def adjust_voltage_setpoint(
        net: pp.pandapowerNet,
        element_type: str,
        element_index: int,
        vm_pu_new: float,
        **kwargs,
    ) -> dict[str, Any]:
        """Set the voltage magnitude setpoint of a gen or ext_grid."""
        element_type = element_type or kwargs.get("element_type", "gen")
        element_index = int(element_index)
        vm_pu_new = float(vm_pu_new if vm_pu_new is not None else kwargs.get("vm_pu_new", 1.0))

        df_map = {"gen": net.gen, "ext_grid": net.ext_grid}
        if element_type not in df_map:
            return {"error": f"element_type must be 'gen' or 'ext_grid', got '{element_type}'."}
        df = df_map[element_type]
        if element_index not in df.index:
            return {"error": f"No {element_type} at index {element_index}."}

        old_vm = float(df.at[element_index, "vm_pu"])
        df.at[element_index, "vm_pu"] = vm_pu_new

        return {
            "action": "adjust_voltage_setpoint",
            "success": True,
            "element_type": element_type,
            "element_index": element_index,
            "old_vm_pu": round(old_vm, 4),
            "new_vm_pu": round(vm_pu_new, 4),
        }

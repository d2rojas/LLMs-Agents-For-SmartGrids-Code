import json
from typing import Any
import pandas as pd
import pandapower as pp

class GridActions:
    """
    Action space tools for the GridDebugAgent to modify the power network.
    These represent realistic control room actions like topological switching,
    redispatch, and load shedding.
    """

    @staticmethod
    def adjust_generation(net: pp.pandapowerNet, gen_index: int, gen_type: str = "gen", p_mw_new: float = None, vm_pu_new: float = None) -> dict[str, Any]:
        """
        Adjust the real power output (p_mw) or voltage setpoint (vm_pu) of a generator.
        
        Args:
            net: pandapower network.
            gen_index: The index of the generator in the respective dataframe.
            gen_type: The type of generator ("gen", "sgen", or "ext_grid").
            p_mw_new: New real power setpoint in MW (if applicable).
            vm_pu_new: New voltage setpoint in p.u. (if applicable).
        """
        df_map = {"gen": net.gen, "sgen": net.sgen, "ext_grid": net.ext_grid}
        if gen_type not in df_map:
            return {"error": f"Invalid gen_type '{gen_type}'. Must be 'gen', 'sgen', or 'ext_grid'."}
        
        df = df_map[gen_type]
        if gen_index not in df.index:
            return {"error": f"No {gen_type} found at index {gen_index}."}
        
        old_state = {}
        new_state = {}
        
        if p_mw_new is not None and "p_mw" in df.columns:
            old_state["p_mw"] = df.at[gen_index, "p_mw"]
            df.at[gen_index, "p_mw"] = p_mw_new
            new_state["p_mw"] = p_mw_new
            
        if vm_pu_new is not None and "vm_pu" in df.columns:
            old_state["vm_pu"] = df.at[gen_index, "vm_pu"]
            df.at[gen_index, "vm_pu"] = vm_pu_new
            new_state["vm_pu"] = vm_pu_new
            
        return {
            "action": "adjust_generation",
            "success": True,
            "gen_type": gen_type,
            "gen_index": gen_index,
            "old_state": old_state,
            "new_state": new_state,
            "message": f"Successfully updated {gen_type} {gen_index}"
        }

    @staticmethod
    def curtail_load(net: pp.pandapowerNet, load_index: int, scale_factor: float) -> dict[str, Any]:
        """
        Shed or curtail load by a completely scaling down its p_mw and q_mvar.
        
        Args:
            net: pandapower network.
            load_index: The index of the load in net.load.
            scale_factor: Multiplier for the load (e.g., 0.5 cuts load in half, 0.0 turns it off).
        """
        if getattr(net, "load", None) is None or load_index not in net.load.index:
            return {"error": f"No load found at index {load_index}."}
            
        if scale_factor < 0.0 or scale_factor > 1.0:
            return {"error": "Scale factor must be between 0.0 and 1.0 (e.g. 0.8 to reduce to 80%)."}
            
        old_p = net.load.at[load_index, "p_mw"]
        old_q = net.load.at[load_index, "q_mvar"] if "q_mvar" in net.load.columns else 0.0
        
        new_p = old_p * scale_factor
        new_q = old_q * scale_factor
        
        net.load.at[load_index, "p_mw"] = new_p
        if "q_mvar" in net.load.columns:
            net.load.at[load_index, "q_mvar"] = new_q
            
        if scale_factor == 0.0:
            net.load.at[load_index, "in_service"] = False
            
        return {
            "action": "curtail_load",
            "success": True,
            "load_index": load_index,
            "old_p_mw": old_p,
            "new_p_mw": new_p,
            "scale_factor_applied": scale_factor,
            "message": f"Successfully curtailed load {load_index} to {scale_factor * 100}%"
        }

    @staticmethod
    def switch_line(net: pp.pandapowerNet, line_index: int, in_service: bool) -> dict[str, Any]:
        """
        Connect or disconnect a transmission line.
        
        Args:
            net: pandapower network.
            line_index: The index of the line in net.line.
            in_service: True to connect, False to disconnect.
        """
        if getattr(net, "line", None) is None or line_index not in net.line.index:
            return {"error": f"No line found at index {line_index}."}
            
        old_status = net.line.at[line_index, "in_service"]
        net.line.at[line_index, "in_service"] = in_service
        
        return {
            "action": "switch_line",
            "success": True,
            "line_index": line_index,
            "old_status": bool(old_status),
            "new_status": in_service,
            "message": f"Line {line_index} in_service set to {in_service}"
        }

    @staticmethod
    def switch_shunt(net: pp.pandapowerNet, shunt_index: int, in_service: bool) -> dict[str, Any]:
        """
        Connect or disconnect a shunt element (capacitor/reactor).
        
        Args:
            net: pandapower network.
            shunt_index: The index of the shunt in net.shunt.
            in_service: True to connect, False to disconnect.
        """
        if getattr(net, "shunt", None) is None or shunt_index not in net.shunt.index:
            return {"error": f"No shunt found at index {shunt_index}."}
            
        old_status = net.shunt.at[shunt_index, "in_service"]
        net.shunt.at[shunt_index, "in_service"] = in_service
        
        return {
            "action": "switch_shunt",
            "success": True,
            "shunt_index": shunt_index,
            "old_status": bool(old_status),
            "new_status": in_service,
            "message": f"Shunt {shunt_index} in_service set to {in_service}"
        }

    TOOL_DEFINITIONS = [
        {
            "name": "adjust_generation",
            "description": "Adjust the real power output (p_mw) or voltage setpoint (vm_pu) of a generator (redispatch). Use this to fix generation deficits or excessive voltages.",
            "parameters": {
                "gen_index": {"type": "integer", "description": "The index of the generator dataframe."},
                "gen_type": {"type": "string", "description": "The type of generator ('gen', 'sgen', or 'ext_grid').", "default": "gen"},
                "p_mw_new": {"type": "number", "description": "New real power setpoint in MW (optional)."},
                "vm_pu_new": {"type": "number", "description": "New voltage setpoint in p.u. (optional)."}
            }
        },
        {
            "name": "curtail_load",
            "description": "Shed or curtail load by scaling down its real and reactive power. Use this during emergencies (load shedding) when generation is insufficient.",
            "parameters": {
                "load_index": {"type": "integer", "description": "The index of the load in net.load."},
                "scale_factor": {"type": "number", "description": "Multiplier for the load (e.g., 0.8 reduces to 80% of original, 0.0 disconnects it completely). Must be between 0.0 and 1.0."}
            }
        },
        {
            "name": "switch_line",
            "description": "Topologically connect or disconnect a transmission line to redirect power flow. Use this to relieve thermal congestion.",
            "parameters": {
                "line_index": {"type": "integer", "description": "The index of the line in net.line."},
                "in_service": {"type": "boolean", "description": "True to connect, False to disconnect."}
            }
        },
        {
            "name": "switch_shunt",
            "description": "Connect or disconnect a shunt element. Use this for voltage control.",
            "parameters": {
                "shunt_index": {"type": "integer", "description": "The index of the shunt in net.shunt."},
                "in_service": {"type": "boolean", "description": "True to connect, False to disconnect."}
            }
        }
    ]

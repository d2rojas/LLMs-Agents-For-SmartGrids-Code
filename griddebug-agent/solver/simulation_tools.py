"""Simulation tools: the AC power flow on the current network, and an N-1 what-if on a copy.

The short-circuit, OPF, DC power flow and snapshot tools of the original project are not part of
the design (OPF would solve the repair for the method; the others were never used to repair) and
live in git history.
"""
from __future__ import annotations

import copy

import pandas as pd
import pandapower as pp
from solver.diagnostic_tools import DiagnosticTools


TOOL_DEFINITIONS = [
    {
        "name": "run_power_flow",
        "description": "Run the AC power flow (Newton-Raphson) on the current network. Returns whether it converged. Run it after every change; the results tables are only valid for the network as it was at the last run.",
        "parameters": {},
    },
    {
        "name": "run_n1_contingency",
        "description": "What-if: take one line or one transformer out of service on a copy of the network, run the power flow there and report its violations. The current network is not changed. Pass line_index or trafo_index.",
        "parameters": {
            "line_index": {"type": "integer", "description": "Line index to take out of service on the copy."},
            "trafo_index": {"type": "integer", "description": "Transformer index to take out of service on the copy."},
        },
    },
]


class SimulationTools:
    TOOL_DEFINITIONS = TOOL_DEFINITIONS

    @staticmethod
    def run_power_flow(net: pp.pandapowerNet, **kwargs) -> dict:
        try:
            pp.runpp(net)
            converged = bool(net.converged)
            return {"converged": converged, "message": f"AC power flow (Newton-Raphson) {'converged' if converged else 'did not converge'}."}
        except pp.LoadflowNotConverged:
            net.converged = False
            return {"converged": False, "message": "AC power flow did not converge (LoadflowNotConverged)."}
        except Exception as e:
            net.converged = False
            return {"converged": False, "message": str(e), "error": str(e)}

    @staticmethod
    def run_n1_contingency(
        net: pp.pandapowerNet,
        line_index: int | None = None,
        trafo_index: int | None = None,
        **kwargs,
    ) -> dict:
        line_index = line_index if line_index is not None else kwargs.get("line_index")
        trafo_index = trafo_index if trafo_index is not None else kwargs.get("trafo_index")
        if line_index is None and trafo_index is None:
            return {"error": "Provide line_index or trafo_index for N-1 contingency."}
        net_copy = copy.deepcopy(net)
        element = "unknown"
        try:
            if line_index is not None:
                if line_index not in net_copy.line.index:
                    return {"error": f"Line index {line_index} not in network."}
                net_copy.line.at[line_index, "in_service"] = False
                element = f"line_{line_index}"
            else:
                if trafo_index not in net_copy.trafo.index:
                    return {"error": f"Trafo index {trafo_index} not in network."}
                net_copy.trafo.at[trafo_index, "in_service"] = False
                element = f"trafo_{trafo_index}"
            pp.runpp(net_copy)
            converged = bool(net_copy.converged)
            
            result = {
                "element_out": element,
                "converged": converged,
                "message": f"N-1 ({element} out): power flow {'converged' if converged else 'did not converge'}.",
            }
            
            if converged:
                violations = DiagnosticTools.check_voltage_violations(net_copy)
                overloads = DiagnosticTools.check_overloads(net_copy)
                # Filter out disconnected buses (0.0 pu or NaN voltage)
                under = [v for v in violations.get("undervoltage_buses", []) if v.get("vm_pu", 0) > 0.01]
                over = [v for v in violations.get("overvoltage_buses", []) if v.get("vm_pu", 0) > 0.01]
                result["voltage_violations"] = len(under) + len(over)
                result["undervoltage_buses"] = under
                result["overvoltage_buses"] = over
                result["overloaded_lines"] = overloads.get("overloaded_lines", [])
                result["overloaded_trafos"] = overloads.get("overloaded_trafos", [])
                
            return result
        except pp.LoadflowNotConverged:
            return {
                "element_out": element,
                "converged": False,
                "message": f"N-1 ({element} out): power flow did not converge.",
            }
        except Exception as e:
            return {"error": str(e), "element_out": element}

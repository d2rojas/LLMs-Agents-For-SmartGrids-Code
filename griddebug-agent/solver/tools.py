"""The tool catalogue every grounded method calls, and the dispatcher that runs it.

Twenty tools in four kinds, one list, one schema builder, one dispatcher. Every
method with tools receives this exact catalogue with the same schemas; the
methods without tools receive the same catalogue rendered as text, so what a
method may do is never a difference between rows.

    query        read the network and the last power-flow results
    simulation   run the power flow; an N-1 what-if on a copy
    diagnostic   the violation checks the harness itself uses
    action       change the network: redispatch, curtail, switch, compensate, setpoints

``ToolDispatcher`` executes a call on one network and keeps the log the
verification gate and the scorer read: every call with its arguments, its
output, its kind and its position, so "was the power flow run after the last
action" and "does this number appear in a tool output" are questions the log
answers.
"""

from __future__ import annotations

import copy
import json
import time
from typing import Any, Dict, List, Optional, Tuple

import pandapower as pp

from solver.actions import ModificationTools
from solver.diagnostic_tools import DiagnosticTools
from solver.query_tools import QueryTools
from solver.simulation_tools import SimulationTools

KINDS: Dict[str, str] = {}
for _t in QueryTools.TOOL_DEFINITIONS:
    KINDS[_t["name"]] = "query"
for _t in SimulationTools.TOOL_DEFINITIONS:
    KINDS[_t["name"]] = "simulation"
for _t in DiagnosticTools.TOOL_DEFINITIONS:
    KINDS[_t["name"]] = "diagnostic"
for _t in ModificationTools.TOOL_DEFINITIONS:
    KINDS[_t["name"]] = "action"

CATALOGUE: List[Dict[str, Any]] = (
    list(QueryTools.TOOL_DEFINITIONS)
    + list(SimulationTools.TOOL_DEFINITIONS)
    + list(DiagnosticTools.TOOL_DEFINITIONS)
    + list(ModificationTools.TOOL_DEFINITIONS)
)
ACTION_TOOLS = tuple(t["name"] for t in ModificationTools.TOOL_DEFINITIONS)
CHECK_TOOLS = ("check_overloads", "check_voltage_violations", "find_disconnected_areas")

# Arguments a tool needs; the original schemas listed none as required and the
# models sent empty calls that failed at run time.
REQUIRED: Dict[str, List[str]] = {
    "adjust_generation": ["gen_index"],
    "curtail_load": ["load_index", "scale_factor"],
    "scale_all_loads": ["factor"],
    "switch_element": ["element_type", "element_index", "in_service"],
    "add_shunt_compensation": ["bus_index", "q_mvar"],
    "adjust_voltage_setpoint": ["element_type", "element_index", "vm_pu_new"],
}


def openai_schemas() -> List[Dict[str, Any]]:
    """The catalogue as OpenAI function-calling tool schemas."""
    out = []
    for t in CATALOGUE:
        out.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": {"type": "object", "properties": t.get("parameters", {}), "required": REQUIRED.get(t["name"], [])},
            },
        })
    return out


def catalogue_text() -> str:
    """The same catalogue as text, for the methods that receive no tools and for the planner."""
    lines = []
    for kind in ("query", "simulation", "diagnostic", "action"):
        lines.append(f"### {kind} tools")
        for t in CATALOGUE:
            if KINDS[t["name"]] != kind:
                continue
            params = t.get("parameters", {})
            sig = ", ".join(
                f"{k}: {v.get('type', 'any')}" + (" (required)" if k in REQUIRED.get(t["name"], []) else "")
                for k, v in params.items()
            )
            lines.append(f"- {t['name']}({sig}): {t['description']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _jsonable(obj: Any) -> Any:
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        return json.loads(json.dumps(obj, default=str))


class ToolDispatcher:
    """Runs tool calls on one network and logs them.

    ``log`` entries: ``{n, name, kind, args, output, ok, latency_s}``. ``n``
    is the 1-based position of the call in the run.
    """

    def __init__(self, net: pp.pandapowerNet, *, max_calls: Optional[int] = None, base_keys: Optional[Any] = None):
        self.net = net
        self.max_calls = max_calls
        # the violations the base network already has: the check tools mark each one
        # ``in_base`` and count the new ones, so every method reads the same floor
        self.base_keys = frozenset(base_keys or ())
        self.log: List[Dict[str, Any]] = []
        self._fns = {
            "get_network_summary": lambda a: QueryTools.get_network_summary(self.net),
            "get_bus_data": lambda a: QueryTools.get_bus_data(self.net, **a),
            "get_line_data": lambda a: QueryTools.get_line_data(self.net, **a),
            "get_gen_data": lambda a: QueryTools.get_gen_data(self.net, **a),
            "get_voltage_profile": lambda a: QueryTools.get_voltage_profile(self.net),
            "get_loading_profile": lambda a: QueryTools.get_loading_profile(self.net),
            "get_power_balance": lambda a: QueryTools.get_power_balance(self.net),
            "get_line_results": lambda a: QueryTools.get_line_results(self.net, **a),
            "get_bus_results": lambda a: QueryTools.get_bus_results(self.net, **a),
            "run_power_flow": lambda a: SimulationTools.run_power_flow(self.net),
            "run_n1_contingency": lambda a: SimulationTools.run_n1_contingency(self.net, **a),
            "run_full_diagnostics": lambda a: DiagnosticTools.run_full_diagnostics(self.net),
            "check_overloads": lambda a: DiagnosticTools.check_overloads(self.net, **a),
            "check_voltage_violations": lambda a: DiagnosticTools.check_voltage_violations(self.net, **a),
            "find_disconnected_areas": lambda a: DiagnosticTools.find_disconnected_areas(self.net),
            "adjust_generation": lambda a: ModificationTools.adjust_generation(self.net, **a),
            "curtail_load": lambda a: ModificationTools.curtail_load(self.net, **a),
            "scale_all_loads": lambda a: ModificationTools.scale_all_loads(self.net, **a),
            "switch_element": lambda a: ModificationTools.switch_element(self.net, **a),
            "add_shunt_compensation": lambda a: ModificationTools.add_shunt_compensation(self.net, **a),
            "adjust_voltage_setpoint": lambda a: ModificationTools.adjust_voltage_setpoint(self.net, **a),
        }
        assert set(self._fns) == set(KINDS), "catalogue and dispatcher disagree"

    @property
    def n_calls(self) -> int:
        return len(self.log)

    @property
    def exhausted(self) -> bool:
        return self.max_calls is not None and self.n_calls >= self.max_calls

    def call(self, name: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        args = dict(args or {})
        t0 = time.time()
        if self.exhausted:
            out: Dict[str, Any] = {"error": f"tool budget exhausted ({self.max_calls} calls); write the final answer"}
            ok = False
        elif name not in self._fns:
            out, ok = {"error": f"unknown tool {name!r}"}, False
        else:
            missing = [k for k in REQUIRED.get(name, []) if k not in args]
            if missing:
                out, ok = {"error": f"{name}: missing required argument(s) {missing}"}, False
            else:
                try:
                    out = _jsonable(self._fns[name](args))
                    out = self._annotate(name, out)
                    ok = not (isinstance(out, dict) and "error" in out)
                except Exception as e:  # a tool must never take the run down
                    out, ok = {"error": f"{type(e).__name__}: {e}"}, False
        entry = {
            "n": len(self.log) + 1,
            "name": name,
            "kind": KINDS.get(name, "unknown"),
            "args": args,
            "output": out,
            "ok": ok,
            "latency_s": round(time.time() - t0, 4),
        }
        self.log.append(entry)
        return out

    def _annotate(self, name: str, out: Any) -> Any:
        """Make the check tools report what the task counts, and nothing louder than that.

        The repair target is relative to the base network: a bus or branch that was already
        outside its limits before the fault is not the method's job, and the request says so.
        The tools used to answer with a ``total_violations`` that included those, and the
        smoke test of 2026-09-28 showed the consequence: on the healthy control network
        gpt-4o-mini read "3 violations", curtailed loads and moved generators for twenty
        calls, and left the network worse than it found it. A tool whose headline number
        contradicts the task is a defect of the harness, not a failure of the model.

        So the new-and-counting ones come first, the pre-existing ones are summarized as
        context, and no field carries a total that mixes the two.
        """
        if not isinstance(out, dict) or "error" in out:
            return out
        if name == "check_voltage_violations":
            new_v, base_v = [], []
            for key, kind in (("undervoltage_buses", "under"), ("overvoltage_buses", "over")):
                for v in out.get(key, []) or []:
                    rec = {"bus": int(v["bus"]), "vm_pu": v.get("vm_pu"), "limit": v.get("limit"), "kind": kind}
                    (base_v if ("bus", int(v["bus"])) in self.base_keys else new_v).append(rec)
            return {
                "converged": out.get("converged"),
                "limits_pu": {"min": out.get("v_min_pu_global"), "max": out.get("v_max_pu_global")},
                "new_violations": new_v,
                "n_new_violations": len(new_v),
                "pre_existing_in_base": {"n": len(base_v), "buses": [v["bus"] for v in base_v]},
                "note": "Only new_violations count against the repair. The buses under pre_existing_in_base were "
                        "already outside their limits in the unmodified network and are not yours to fix.",
            }
        if name == "check_overloads":
            new_o, base_o = [], []
            for key, el, idk in (("overloaded_lines", "line", "line_index"), ("overloaded_trafos", "trafo", "trafo_index")):
                for v in out.get(key, []) or []:
                    rec = {"element": el, "index": int(v[idk]), "loading_percent": v.get("loading_percent")}
                    if el == "line":
                        rec["from_bus"], rec["to_bus"] = v.get("from_bus"), v.get("to_bus")
                    (base_o if (el, int(v[idk])) in self.base_keys else new_o).append(rec)
            return {
                "converged": out.get("converged"),
                "threshold_percent": out.get("threshold_percent"),
                "new_overloads": new_o,
                "n_new_overloads": len(new_o),
                "pre_existing_in_base": {"n": len(base_o), "elements": [f"{v['element']} {v['index']}" for v in base_o]},
                "note": "Only new_overloads count against the repair. The elements under pre_existing_in_base were "
                        "already above their rating in the unmodified network and are not yours to fix.",
            }
        return out

    # what the gate asks the log
    def last_index(self, kind: Optional[str] = None, names: Optional[Tuple[str, ...]] = None) -> int:
        """1-based position of the last call of a kind or name set, 0 if none."""
        n = 0
        for e in self.log:
            if (kind is None or e["kind"] == kind) and (names is None or e["name"] in names):
                n = e["n"]
        return n

    def snapshot(self) -> pp.pandapowerNet:
        return copy.deepcopy(self.net)

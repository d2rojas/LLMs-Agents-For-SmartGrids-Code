"""The conventional-automation row: rules and a fixed policy, no language model.

The rule engine of ``solver/rules.py`` classifies the evidence; a fixed policy
maps what it finds to actions from the same catalogue the agents use, verifies
with the power flow after each one, and stops when the network is secure or
the budget is spent. The diagnosis is the rule engine's classification mapped
onto the fault types of the answer contract. Everything it reports comes from
tool outputs, so it is traceable by construction; when it cannot reach a secure
point it says so, which is the honest floor every model-backed row has to beat.

The policy, in the order it is tried on each pass:

1. not converged, generators out of service        -> switch them back in
2. not converged, or islanded load                  -> switch back in the out-of-service branches
3. not converged, still                             -> scale all loads down by 20 %, repeatedly
4. converged, islanded load                         -> reconnect the out-of-service branches at those buses
5. new thermal overloads                            -> restore any out-of-service branch; else curtail the
                                                       largest load at the branch's ends to 80 %
6. new under-voltages                               -> 10 Mvar capacitive shunt at the worst new bus; after
                                                       two shunts on a bus, curtail its load to 80 %
7. new over-voltages                                -> lower the highest generator or slack setpoint by 0.02

Each numbered step is one rule; a rule fires only if its condition holds on the
current solver state, and the pass repeats until secure or out of budget.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Set

import pandapower as pp

from methods.answer import parse_answer
from methods.common import Context, MethodRun
from solver.evidence import EvidenceCollector
from solver.rules import RuleEngine
from solver.tools import ToolDispatcher
from solver.violations import State, observe

SHUNT_MVAR = 10.0
CURTAIL = 0.8
LOAD_SCALE = 0.8
SETPOINT_STEP = 0.02


def _out_of_service(net: pp.pandapowerNet, element: str) -> List[int]:
    df = getattr(net, element)
    return [int(i) for i in df.index if not bool(df.at[i, "in_service"])] if len(df) else []


def _branches_at(net: pp.pandapowerNet, buses: Set[int], out_only: bool = True) -> List[Dict[str, Any]]:
    out = []
    for el, (a, b) in (("line", ("from_bus", "to_bus")), ("trafo", ("hv_bus", "lv_bus"))):
        df = getattr(net, el)
        for i in df.index:
            if (int(df.at[i, a]) in buses or int(df.at[i, b]) in buses) and (not out_only or not bool(df.at[i, "in_service"])):
                out.append({"element_type": el, "element_index": int(i)})
    return out


def _largest_load_at(net: pp.pandapowerNet, buses: List[int]) -> Optional[int]:
    best, best_p = None, -1.0
    for i, row in net.load.iterrows():
        if int(row["bus"]) in buses and bool(row["in_service"]) and float(row["p_mw"]) > best_p:
            best, best_p = int(i), float(row["p_mw"])
    return best


def _diagnosis(net: pp.pandapowerNet, initial: State, rules: List[str], evidence: Any) -> Dict[str, Any]:
    """The rule engine's classification, as a fault type of the contract, with the components it points at."""
    gens_out = _out_of_service(net, "gen")
    lines_out = _out_of_service(net, "line")
    trafos_out = _out_of_service(net, "trafo")
    ratio = (evidence.total_load_p_mw / evidence.input_gen_capacity_mw) if evidence.input_gen_capacity_mw else None
    if gens_out and len(gens_out) == len(net.gen):
        return {"fault_type": "generation_loss", "components": {"gen": gens_out}}
    if initial.islanded_load_buses:
        return {"fault_type": "islanding", "components": {"bus": list(initial.islanded_load_buses), "line": lines_out}}
    if trafos_out:
        return {"fault_type": "trafo_outage", "components": {"trafo": trafos_out}}
    if lines_out:
        return {"fault_type": "line_outage", "components": {"line": lines_out}}
    if "nonconvergence" in rules and ratio is not None and ratio > 1.5:
        return {"fault_type": "load_increase", "components": {"load": [int(i) for i in net.load.index]}}
    if "overvoltage" in rules and float(net.ext_grid["vm_pu"].max()) > 1.05:
        return {"fault_type": "voltage_setpoint", "components": {"ext_grid": [int(i) for i in net.ext_grid.index]}}
    if "undervoltage" in rules and ("reactive_deficit" in rules):
        return {"fault_type": "reactive_load", "components": {"bus": [v["bus"] for v in initial.voltage if v["kind"] == "under"][:3]}}
    if "line_overload" in rules or "trafo_overload" in rules:
        return {"fault_type": "limit_derating", "components": {"line": [t["index"] for t in initial.thermal if t["element"] == "line"]}}
    if "nonconvergence" in rules:
        return {"fault_type": "impedance_fault", "components": {}}
    if "undervoltage" in rules:
        return {"fault_type": "load_increase", "components": {"load": [int(i) for i in net.load.index]}}
    return {"fault_type": "none", "components": {}}


def run_rule_based(ctx: Context) -> MethodRun:
    t0 = time.time()
    net = ctx.net
    d = ToolDispatcher(net, max_calls=ctx.max_tool_calls, base_keys=ctx.base_keys)
    evidence = EvidenceCollector().collect(net)
    fired = [r.rule_name for r in RuleEngine().evaluate(evidence)]
    initial = observe(net, ctx.base_keys)
    diagnosis = _diagnosis(net, initial, fired, evidence)
    actions: List[Dict[str, Any]] = []
    shunts_on: Dict[int, int] = {}
    scale_steps = 0
    tried: Set[str] = set()

    def act(name: str, args: Dict[str, Any]) -> bool:
        key = name + json.dumps(args, sort_keys=True)
        if key in tried or d.exhausted:
            return False
        tried.add(key)
        out = d.call(name, args)
        actions.append({"tool": name, "args": args})
        return not (isinstance(out, dict) and "error" in out)

    state = initial
    while not d.exhausted:
        d.call("run_power_flow", {})
        state = observe(net, ctx.base_keys)
        if state.secure:
            break
        acted = False
        if not state.converged:
            for g in _out_of_service(net, "gen"):
                acted |= act("switch_element", {"element_type": "gen", "element_index": g, "in_service": True})
            if not acted:
                for br in _branches_at(net, set(int(b) for b in net.bus.index)):
                    acted |= act("switch_element", {**br, "in_service": True})
                    if acted:
                        break
            if not acted and scale_steps < 8:
                scale_steps += 1
                acted = act("scale_all_loads", {"factor": LOAD_SCALE}) if scale_steps == 1 else act("scale_all_loads", {"factor": LOAD_SCALE, "_step": scale_steps})
        else:
            d.call("check_voltage_violations", {})
            d.call("check_overloads", {})
            d.call("find_disconnected_areas", {})
            if state.islanded_load_buses:
                for br in _branches_at(net, set(state.islanded_load_buses)):
                    acted |= act("switch_element", {**br, "in_service": True})
                if not acted:
                    ld = _largest_load_at(net, state.islanded_load_buses)
                    if ld is not None:
                        acted = act("curtail_load", {"load_index": ld, "scale_factor": 0.0})
            new_thermal = [t for t in state.thermal if (t["element"], t["index"]) in state.new_keys]
            new_under = [v for v in state.voltage if v["kind"] == "under" and ("bus", v["bus"]) in state.new_keys]
            new_over = [v for v in state.voltage if v["kind"] == "over" and ("bus", v["bus"]) in state.new_keys]
            if not acted and new_thermal:
                for br in _branches_at(net, set(int(b) for b in net.bus.index)):
                    acted |= act("switch_element", {**br, "in_service": True})
                    if acted:
                        break
                if not acted:
                    worst = max(new_thermal, key=lambda t: t["loading_percent"])
                    df = getattr(net, worst["element"])
                    a, b = ("from_bus", "to_bus") if worst["element"] == "line" else ("hv_bus", "lv_bus")
                    ends = [int(df.at[worst["index"], a]), int(df.at[worst["index"], b])]
                    ld = _largest_load_at(net, ends)
                    if ld is not None:
                        acted = act("curtail_load", {"load_index": ld, "scale_factor": CURTAIL})
                    if not acted:
                        acted = act("scale_all_loads", {"factor": LOAD_SCALE, "_step": scale_steps + 1})
                        scale_steps += 1
            if not acted and new_under:
                worst = min(new_under, key=lambda v: v["vm_pu"])
                bus = int(worst["bus"])
                if shunts_on.get(bus, 0) < 2:
                    shunts_on[bus] = shunts_on.get(bus, 0) + 1
                    acted = act("add_shunt_compensation", {"bus_index": bus, "q_mvar": SHUNT_MVAR, "_n": shunts_on[bus]})
                if not acted:
                    ld = _largest_load_at(net, [bus])
                    if ld is not None:
                        acted = act("curtail_load", {"load_index": ld, "scale_factor": CURTAIL})
            if not acted and new_over:
                highest = max(list(net.ext_grid.index), key=lambda i: float(net.ext_grid.at[i, "vm_pu"]))
                vm = float(net.ext_grid.at[highest, "vm_pu"])
                acted = act("adjust_voltage_setpoint", {"element_type": "ext_grid", "element_index": int(highest), "vm_pu_new": round(vm - SETPOINT_STEP, 3)})
                if not acted and len(net.gen):
                    hg = max(list(net.gen.index), key=lambda i: float(net.gen.at[i, "vm_pu"]))
                    vg = float(net.gen.at[hg, "vm_pu"])
                    acted = act("adjust_voltage_setpoint", {"element_type": "gen", "element_index": int(hg), "vm_pu_new": round(vg - SETPOINT_STEP, 3)})
        if not acted:
            break  # no rule applies: stop and declare

    # clean the private bookkeeping keys out of the reported actions
    for a in actions:
        a["args"] = {k: v for k, v in a["args"].items() if not k.startswith("_")}
    if not d.exhausted:
        d.call("run_power_flow", {})
    state = observe(net, ctx.base_keys)
    remaining = ([] if state.converged else ["power flow does not converge"]) + [f"load on islanded bus {b}" for b in state.islanded_load_buses] \
        + [f"bus {v['bus']} at {v['vm_pu']} p.u." for v in state.voltage if ("bus", v["bus"]) in state.new_keys] \
        + [f"{t['element']} {t['index']} at {t['loading_percent']} %" for t in state.thermal if (t["element"], t["index"]) in state.new_keys]
    status = "repaired" if state.secure else ("not_repaired" if actions else "cannot_repair")
    if d.exhausted and not state.secure:
        status = "not_repaired"
    obj = {
        "diagnosis": {**diagnosis, "explanation": "rule engine: " + (", ".join(fired) if fired else "no rule triggered")},
        "actions": actions,
        "final_state": {"converged": state.converged, "n_new_violations": state.n_new, "islanded_load_buses": state.islanded_load_buses},
        "status": status,
        "remaining_violations": remaining,
        "summary": f"Rules fired: {', '.join(fired) if fired else 'none'}. Actions applied: "
                   + (", ".join(sorted({a['tool'] for a in actions})) if actions else "none") + ". "
                   + ("The network is secure." if state.secure else "Violations remain; see remaining_violations."),
    }
    answer_text = json.dumps(obj, indent=2)
    trace = {"case_study": "griddebug", "method": "rule_based", "model": ctx.spec.key, "request_id": ctx.request_id, "status": "ok",
             "error": None, "answer": answer_text, "messages": [], "rounds": [{"round": 1, "role": "harness", "llm": None, "tools": list(d.log)}],
             "n_llm_calls": 0, "n_tool_calls": d.n_calls, "prompt_tokens": 0, "completion_tokens": 0, "wall_time_s": round(time.time() - t0, 3),
             "rules_fired": fired, "harness_declared": None, "system_prompt_hash": None}
    return MethodRun(method="rule_based", answer_text=answer_text, answer=parse_answer(answer_text), final_net=net, tool_log=d.log,
                     trace=trace, budget_exhausted=d.exhausted, n_tool_calls=d.n_calls, wall_time_s=round(time.time() - t0, 3))

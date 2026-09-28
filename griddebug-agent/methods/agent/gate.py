"""The verification gate: six conditions on the final answer, from the agent's own evidence.

The gate sees the network the agent left behind, the tool log, and the text
the agent wrote. It never sees the injected fault or a reference repair; that
is what makes it a deployable component rather than an evaluation artifact,
and it fixes what it can and cannot catch. It cannot tell a wrong diagnosis
from a right one; it can tell a claim of repair the solver contradicts, a
number no tool produced, an action taken after the last power flow, and a
load left on an island.

    G1  converged      the harness re-runs the AC power flow on the final network and it converges
    G2  no islanded load   no in-service load sits on a bus without a path to a slack bus
    G3  secure or declared   zero violations beyond the base network, or the answer declares what remains
    G4  currency       the last power-flow run came after the last action
    G5  traceable      every number in the answer appears in a tool output or in the evidence
    G6  consistent     the answer's status and final_state agree with what the solver found

``check`` returns one record per condition plus ``passed``, and the state the
harness observed, which is logged as a tool call so its numbers are traceable.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

import pandapower as pp

from methods.answer import Answer
from solver.tools import ACTION_TOOLS
from solver.violations import Key, State, observe

CONDITION_ORDER = ("converged", "no_islanded_load", "secure_or_declared", "currency", "traceable", "consistent")
CONDITION_LABELS = {
    "converged": "G1", "no_islanded_load": "G2", "secure_or_declared": "G3",
    "currency": "G4", "traceable": "G5", "consistent": "G6",
}
CONDITION_DESCRIPTIONS = {
    "converged": "the AC power flow, re-run by the harness on the final network, converges",
    "no_islanded_load": "no in-service load sits on a bus with no path to a slack bus",
    "secure_or_declared": "no violation beyond those of the base network, or the answer lists what remains and does not claim a repair",
    "currency": "the last power-flow run came after the last action; nothing was changed after the last verification",
    "traceable": "every number in the answer appears in a tool output or in the evidence the method received",
    "consistent": "status and final_state in the answer agree with the solver's final state",
}
MAX_VERIFICATION_ATTEMPTS = 2

_NUM = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])")


def numbers_in(text: str) -> List[str]:
    return _NUM.findall(text or "")


def _numbers_of_output(obj: Any, acc: Set[str]) -> None:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        acc.add(repr(float(obj)))
    elif isinstance(obj, str):
        for n in numbers_in(obj):
            acc.add(repr(float(n)))
    elif isinstance(obj, dict):
        for v in obj.values():
            _numbers_of_output(v, acc)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _numbers_of_output(v, acc)


def supported(num_text: str, pool: Set[float]) -> bool:
    """A number as written is supported if some pool number rounds to it at the decimals written."""
    try:
        v = float(num_text)
    except ValueError:
        return False
    decimals = len(num_text.split(".")[1]) if "." in num_text else 0
    tol = 0.5 * 10 ** (-decimals) + 1e-9
    for p in pool:
        if abs(round(p, decimals) - v) <= tol or abs(p - v) <= tol:
            return True
    return False


def traceability(answer: Answer, tool_log: Iterable[Dict[str, Any]], evidence_text: str, request_text: str = "") -> Tuple[int, int, List[str]]:
    """(numbers checked, untraceable, the untraceable ones). Component indices in the diagnosis are not numbers to trace."""
    pool_repr: Set[str] = set()
    for e in tool_log:
        _numbers_of_output(e.get("output"), pool_repr)
        _numbers_of_output(e.get("args"), pool_repr)
    for n in numbers_in(evidence_text) + numbers_in(request_text):
        pool_repr.add(repr(float(n)))
    pool = {float(x) for x in pool_repr}
    texts = [answer.summary, answer.explanation] + list(answer.remaining)
    checked: List[str] = []
    for t in texts:
        checked += numbers_in(t)
    bad = [n for n in checked if not supported(n, pool)]
    return len(checked), len(bad), bad


def check(
    answer: Answer,
    final_net: pp.pandapowerNet,
    base_keys: FrozenSet[Key],
    tool_log: List[Dict[str, Any]],
    evidence_text: str,
    request_text: str = "",
) -> Tuple[Dict[str, Any], State]:
    state = observe(final_net, base_keys)
    results: Dict[str, Dict[str, Any]] = {}

    results["converged"] = {"passed": state.converged, "detail": "converged" if state.converged else "the final network does not converge"}
    results["no_islanded_load"] = {
        "passed": state.converged and not state.islanded_load_buses,
        "detail": ("no islanded load" if not state.islanded_load_buses else f"load on islanded bus(es) {state.islanded_load_buses}") if state.converged else "not assessable: not converged",
    }
    remaining = sorted(f"{k} {i}" for k, i in state.new_keys) if state.converged else []
    if state.converged and not state.new_keys and not state.islanded_load_buses:
        results["secure_or_declared"] = {"passed": True, "detail": "secure: no violation beyond the base network"}
    elif answer.declares_failure and (answer.remaining or not state.converged):
        results["secure_or_declared"] = {"passed": True, "detail": f"not secure, and declared as such ({answer.status})"}
    else:
        results["secure_or_declared"] = {
            "passed": False,
            "detail": ("not secure and presented as repaired: " if answer.claims_repaired else "not secure and not declared: ")
                      + (", ".join(remaining) if remaining else ("not converged" if not state.converged else "islanded load")),
        }

    last_action = max((e["n"] for e in tool_log if e.get("name") in ACTION_TOOLS), default=0)
    last_pf = max((e["n"] for e in tool_log if e.get("name") == "run_power_flow"), default=0)
    if last_action == 0:
        results["currency"] = {"passed": True, "detail": "no action was taken"}
    elif last_pf > last_action:
        results["currency"] = {"passed": True, "detail": f"power flow run (call {last_pf}) after the last action (call {last_action})"}
    else:
        results["currency"] = {"passed": False, "detail": f"the last action (call {last_action}) was not followed by run_power_flow"}

    n_checked, n_bad, bad = traceability(answer, tool_log, evidence_text, request_text)
    results["traceable"] = {"passed": n_bad == 0, "detail": f"{n_checked} numbers checked, {n_bad} unsupported" + (f": {bad[:6]}" if bad else ""), "n_numbers": n_checked, "n_untraceable": n_bad}

    problems: List[str] = []
    if not answer.json_ok:
        problems.append("no JSON answer")
    else:
        if answer.claimed_converged is not None and bool(answer.claimed_converged) != state.converged:
            problems.append(f"final_state.converged={answer.claimed_converged} but the solver says {state.converged}")
        if answer.claims_repaired and not state.secure:
            problems.append("status repaired but the network is not secure")
        if state.converged and answer.claimed_new_violations is not None and answer.claimed_new_violations != state.n_new:
            problems.append(f"final_state.n_new_violations={answer.claimed_new_violations} but the solver counts {state.n_new}")
        if answer.status is None:
            problems.append("status missing")
    results["consistent"] = {"passed": not problems, "detail": "; ".join(problems) if problems else "status and final_state agree with the solver"}

    report = {
        "conditions": {k: results[k] for k in CONDITION_ORDER},
        "passed": all(results[k]["passed"] for k in CONDITION_ORDER),
        "failed": [k for k in CONDITION_ORDER if not results[k]["passed"]],
        "state": state.as_dict(),
    }
    return report, state


def verdict_text(report: Dict[str, Any]) -> str:
    """The failed conditions, as the retry message hands them to the model."""
    lines = []
    for k in report["failed"]:
        c = report["conditions"][k]
        lines.append(f"- {CONDITION_LABELS[k]} {k}: {c['detail']}")
    st = report["state"]
    lines.append(f"- solver state now: converged={st['converged']}, new violations={st['n_new_violations']}, "
                 f"islanded load buses={st['islanded_load_buses']}" + (f", remaining: {', '.join(st['new'])}" if st.get("new") else ""))
    return "\n".join(lines)

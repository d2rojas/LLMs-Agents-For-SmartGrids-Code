"""Seeded natural-language power-flow requests with deterministic ground truth.

Each `Request` pairs a natural-language instruction with the exact ordered tool
calls it is meant to trigger (`intended_calls`, using the tool names and argument
names of `agent/tools.py`) and with the result of executing those calls through the
real `ToolDispatcher` on a seed-perturbed case (`ground_truth`). This separates
*formulation correctness* (did the agent call the right tools with the right
arguments) from *numerical correctness* (does the reported number match the solver).

Bus ids in request text and in tool arguments are MATPOWER 1-based display ids,
which is what `_resolve_bus_index` in `solver/power_flow.py` expects.

Difficulties. `DIFFICULTIES` is the default balanced mix (plain / parameterized /
multistep / ambiguous), whose ground truth always converges. The fifth level,
`"stress"`, is opt-in (`difficulties=["stress"]`, `--difficulty stress`) so the
default request set and its ids stay reproducible. Stress requests are *meant* to
break the solver, so the verification gate has something to catch: (a) loads raised
to 3-6x nominal until Newton-Raphson diverges, (b) a branch whose removal isolates a
bus, (c) a benign step followed by a breaking one plus a report. Each stress item
carries `expected_outcome` in {"non_converged", "islanded", "converged"}, chosen by
actually running PandaPower on the seed-perturbed case at generation time
(`STRESS_VERIFY_K`), and `compute_ground_truth` records the observed outcome
instead of treating a failed solve as an error.

CLI:
    python -m evaluation.requests --case case14 --n 40 --seed 0 --out evaluation/requests_case14.jsonl
    python -m evaluation.requests --case case30 --n 10 --seed 0 --difficulty stress
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import random
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.tools import TOOLS, ToolContext, build_default_dispatcher
from solver.schemas import SessionState
from solver import case_loader
from solver.power_flow import _bus_display_id, run_power_flow
from solver.power_flow import disconnect_line as _pf_disconnect_line
from solver.power_flow import modify_bus_load as _pf_modify_bus_load
from solver.power_flow import reconnect_line as _pf_reconnect_line

DIFFICULTIES: tuple[str, ...] = ("plain", "parameterized", "multistep", "ambiguous")
STRESS_DIFFICULTY = "stress"
ALL_DIFFICULTIES: tuple[str, ...] = DIFFICULTIES + (STRESS_DIFFICULTY,)
EXPECTED_OUTCOMES: tuple[str, ...] = ("converged", "non_converged", "islanded")
THRESHOLDS_PERCENT: tuple[int, ...] = (80, 90, 100)
N1_TOP_K_CHOICES: tuple[int, ...] = (3, 5, 8)
N1_CRITERIA: tuple[str, ...] = ("max_violations", "max_overload", "min_voltage")
TOOL_NAMES: frozenset[str] = frozenset(t["name"] for t in TOOLS)

# Stress template: load factors tried in ascending order, how many load buses may be
# combined before giving up, and the perturbation strength used to verify the outcome.
STRESS_FACTORS: tuple[int, ...] = (3, 4, 5, 6)
STRESS_MAX_BUSES = 5
STRESS_START_POOL = 6  # the first stressed bus is drawn from the N largest loads
STRESS_VERIFY_K = 1  # paper setting; ground truth at another k may differ marginally

# Perturbation strength per unit of k: loads and generator setpoints are scaled by a
# factor drawn uniformly from [1 - 0.1*k, 1 + 0.1*k] (k=1 -> +/-10 %).
PERTURB_FRACTION_PER_K = 0.10


@dataclass
class Request:
    id: str
    case_name: str
    seed: int
    difficulty: str
    text: str
    intended_calls: list[dict[str, Any]]
    notes: str = ""
    # What the request asks to be reported; drives `ground_truth["answer"]`.
    query: dict[str, Any] = field(default_factory=dict)
    # Outcome the generator intends for the final solver state (see EXPECTED_OUTCOMES).
    # "converged" for the four regular templates; stress items are verified with PandaPower.
    expected_outcome: str = "converged"
    ground_truth: Optional[dict[str, Any]] = None


# --------------------------------------------------------------------------- perturbation


def perturb_network(net: Any, *, seed: int, k: int = 1) -> None:
    """Deterministically perturb loads and generator setpoints in place.

    Uses `random.Random(seed)` so the same seed always yields the same network.
    The slack (`ext_grid`) is left untouched so the case stays balanced.
    """
    rng = random.Random(int(seed))
    span = PERTURB_FRACTION_PER_K * max(int(k), 0)
    if hasattr(net, "load") and len(net.load) > 0:
        for idx in net.load.index.tolist():
            factor = rng.uniform(1.0 - span, 1.0 + span)
            net.load.at[idx, "p_mw"] = float(net.load.at[idx, "p_mw"]) * factor
            net.load.at[idx, "q_mvar"] = float(net.load.at[idx, "q_mvar"]) * factor
    if hasattr(net, "gen") and len(net.gen) > 0:
        for idx in net.gen.index.tolist():
            factor = rng.uniform(1.0 - span, 1.0 + span)
            net.gen.at[idx, "p_mw"] = float(net.gen.at[idx, "p_mw"]) * factor


# --------------------------------------------------------------------------- case facts


@dataclass(frozen=True)
class _CaseFacts:
    case_name: str
    n_buses: int
    bus_ids: tuple[int, ...]
    base_load_mw: dict[int, float]  # display bus id -> nominal active load
    safe_lines: tuple[tuple[int, int], ...]  # (from, to) display ids; removal keeps the grid connected
    # Nominal reactive load per display bus id (stress template scales P and Q together).
    base_load_mvar: dict[int, float] = field(default_factory=dict)
    # Branches (lines AND transformers) whose removal splits the grid:
    # (from, to, "line"|"trafo", buses that lose their path to the slack).
    unsafe_branches: tuple[tuple[int, int, str, tuple[int, ...]], ...] = ()

    @property
    def load_buses(self) -> tuple[int, ...]:
        return tuple(sorted(b for b, p in self.base_load_mw.items() if p > 0.0))

    def load_buses_by_size(self) -> tuple[int, ...]:
        """Load buses from the largest nominal active load to the smallest."""
        return tuple(sorted(self.load_buses, key=lambda b: (-self.base_load_mw[b], b)))


def _component_labels(n_nodes: int, edges: list[tuple[int, int]], skip: int = -1) -> list[int]:
    """Connected-component label per node (0..n_comp-1), optionally ignoring edge `skip`."""
    adj: dict[int, set[int]] = {i: set() for i in range(n_nodes)}
    for j, (a, b) in enumerate(edges):
        if j == skip:
            continue
        adj[a].add(b)
        adj[b].add(a)
    labels = [-1] * n_nodes
    comps = 0
    for start in range(n_nodes):
        if labels[start] >= 0:
            continue
        labels[start] = comps
        stack = [start]
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if labels[v] < 0:
                    labels[v] = comps
                    stack.append(v)
        comps += 1
    return labels


def _n_components(n_nodes: int, edges: list[tuple[int, int]], skip: int = -1) -> int:
    labels = _component_labels(n_nodes, edges, skip)
    return (max(labels) + 1) if labels else 0


_BASE_NET_CACHE: dict[str, Any] = {}


def _load_base_net(case_name: str) -> Any:
    """Unperturbed pandapower net for `case_name` (cached; callers must deepcopy before mutating)."""
    canonical = case_loader.normalize_case_name(case_name)
    if canonical not in _BASE_NET_CACHE:
        net, _ = case_loader.load(canonical)
        _BASE_NET_CACHE[canonical] = net
    return _BASE_NET_CACHE[canonical]


def _net_graph(net: Any) -> tuple[list[int], dict[int, int], dict[int, int], list[tuple[int, int]], list[tuple[str, int, int]]]:
    """(bus index list, index->position, index->display id, in-service edges, edge labels)."""
    index_list = [int(i) for i in net.bus.index.tolist()]
    pos = {idx: k for k, idx in enumerate(index_list)}
    display = {idx: int(_bus_display_id(net, idx)) for idx in index_list}
    edges: list[tuple[int, int]] = []
    labels: list[tuple[str, int, int]] = []
    for _, row in net.line.iterrows():
        if bool(row.get("in_service", True)):
            a, b = int(row["from_bus"]), int(row["to_bus"])
            edges.append((pos[a], pos[b]))
            labels.append(("line", display[a], display[b]))
    if hasattr(net, "trafo") and len(net.trafo) > 0:
        for _, row in net.trafo.iterrows():
            if bool(row.get("in_service", True)):
                a, b = int(row["hv_bus"]), int(row["lv_bus"])
                edges.append((pos[a], pos[b]))
                labels.append(("trafo", display[a], display[b]))
    return index_list, pos, display, edges, labels


def _slack_positions(net: Any, pos: dict[int, int]) -> set[int]:
    out: set[int] = set()
    if hasattr(net, "ext_grid") and len(net.ext_grid) > 0:
        for _, row in net.ext_grid.iterrows():
            if bool(row.get("in_service", True)):
                out.add(pos[int(row["bus"])])
    return out


def _isolated_buses(net: Any) -> set[int]:
    """Display ids of buses with no in-service path to any slack (`ext_grid`) bus.

    pandapower solves such buses as out of service (NaN voltage), so a converged
    solve can still describe a split grid; this is what `expected_outcome == "islanded"` means.
    """
    index_list, pos, display, edges, _ = _net_graph(net)
    labels = _component_labels(len(index_list), edges)
    slack_labels = {labels[p] for p in _slack_positions(net, pos)}
    return {display[idx] for idx in index_list if labels[pos[idx]] not in slack_labels}


def _classify_outcome(converged: bool, new_isolated: set[int] | list[int]) -> str:
    if not converged:
        return "non_converged"
    if new_isolated:
        return "islanded"
    return "converged"


def _connected_without(n_nodes: int, edges: list[tuple[int, int]], skip: int) -> bool:
    """True if removing edge `skip` does not split the grid further than it already is.

    Some MATPOWER cases (case118 as loaded here) contain more than one connected
    component in the base graph, so requiring full connectivity would leave no safe line.
    """
    return _n_components(n_nodes, edges, skip) == _n_components(n_nodes, edges)


def _case_facts(case_name: str) -> _CaseFacts:
    net = _load_base_net(case_name)
    canonical = case_loader.normalize_case_name(case_name)
    index_list, pos, display, edges, edge_labels = _net_graph(net)

    base_load: dict[int, float] = {}
    base_load_q: dict[int, float] = {}
    for _, row in net.load.iterrows():
        b = display[int(row["bus"])]
        base_load[b] = base_load.get(b, 0.0) + float(row["p_mw"])
        base_load_q[b] = base_load_q.get(b, 0.0) + float(row["q_mvar"])

    line_edge_ids = [(j, (fb, tb)) for j, (kind, fb, tb) in enumerate(edge_labels) if kind == "line"]
    safe = tuple(
        (fb, tb) for edge_idx, (fb, tb) in line_edge_ids if _connected_without(len(index_list), edges, edge_idx)
    )

    # Branches whose removal splits the grid (lines and transformers alike), with the
    # buses that thereby lose their path to the slack.
    n_base = _n_components(len(index_list), edges)
    base_labels = _component_labels(len(index_list), edges)
    slack_pos = _slack_positions(net, pos)
    base_isolated = {display[idx] for idx in index_list if base_labels[pos[idx]] not in {base_labels[p] for p in slack_pos}}
    unsafe: list[tuple[int, int, str, tuple[int, ...]]] = []
    for j, (kind, fb, tb) in enumerate(edge_labels):
        if _n_components(len(index_list), edges, j) <= n_base:
            continue
        labels = _component_labels(len(index_list), edges, j)
        slack_labels = {labels[p] for p in slack_pos}
        isolated = sorted({display[idx] for idx in index_list if labels[pos[idx]] not in slack_labels} - base_isolated)
        unsafe.append((fb, tb, kind, tuple(isolated)))

    return _CaseFacts(
        case_name=canonical,
        n_buses=len(index_list),
        bus_ids=tuple(sorted(display.values())),
        base_load_mw=base_load,
        safe_lines=safe,
        base_load_mvar=base_load_q,
        unsafe_branches=tuple(unsafe),
    )


# --------------------------------------------------------------------------- text helpers

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
         "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def _num_words(n: int) -> str:
    n = int(n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else "-" + _ONES[n % 10])
    rest = n % 100
    return _ONES[n // 100] + " hundred" + ("" if rest == 0 else " " + _num_words(rest))


def _fmt_mw(p: float) -> str:
    return f"{p:g}"


def _case_phrase(rng: random.Random, facts: _CaseFacts) -> str:
    n = facts.n_buses
    return rng.choice([facts.case_name, f"the IEEE {n}-bus system", f"the {n}-bus test case ({facts.case_name})"])


def _call(tool: str, **args: Any) -> dict[str, Any]:
    assert tool in TOOL_NAMES, tool
    return {"tool": tool, "args": dict(args)}


@dataclass
class _Op:
    clause: str
    calls: list[dict[str, Any]]
    query: dict[str, Any]
    notes: str = ""


# --------------------------------------------------------------------------- operations

def _pick_load_bus_and_mw(rng: random.Random, facts: _CaseFacts, *, seeded: bool) -> tuple[int, float]:
    buses = facts.load_buses
    bus = rng.choice(buses) if seeded else buses[0]
    base = facts.base_load_mw[bus]
    p = round(base * rng.uniform(0.5, 1.5), 1) if seeded else round(base, 1)
    return bus, float(p)


def _pick_line(rng: random.Random, facts: _CaseFacts, *, seeded: bool) -> tuple[int, int]:
    return rng.choice(facts.safe_lines) if seeded else facts.safe_lines[0]


def op_run_pf() -> _Op:
    return _Op("run the AC power flow", [_call("run_powerflow")], {"kind": "powerflow_summary"})


def op_modify_load(bus: int, p_mw: float, *, bus_text: Optional[str] = None, value_text: Optional[str] = None) -> _Op:
    bus_text = bus_text or f"bus {bus}"
    value_text = value_text or f"{_fmt_mw(p_mw)} MW"
    return _Op(
        f"set the active load at {bus_text} to {value_text}",
        [_call("modify_load", bus_id=int(bus), p_mw=float(p_mw))],
        {"kind": "powerflow_summary"},
    )


def op_disconnect(fb: int, tb: int, *, fb_text: Optional[str] = None, tb_text: Optional[str] = None, what: str = "line") -> _Op:
    fb_text = fb_text or f"bus {fb}"
    tb_text = tb_text or f"bus {tb}"
    return _Op(
        f"disconnect the {what} between {fb_text} and {tb_text}",
        [_call("disconnect_line", from_bus=int(fb), to_bus=int(tb))],
        {"kind": "powerflow_summary"},
    )


def op_reconnect(fb: int, tb: int) -> _Op:
    return _Op(
        f"reconnect the line between bus {fb} and bus {tb}",
        [_call("reconnect_line", from_bus=int(fb), to_bus=int(tb))],
        {"kind": "powerflow_summary"},
    )


def op_worst_voltage(*, run_pf: bool) -> _Op:
    clause = "report the bus with the lowest voltage magnitude"
    if run_pf:
        clause = "run the power flow, then " + clause
    return _Op(clause, [_call("run_powerflow")] if run_pf else [], {"kind": "worst_voltage_bus"})


def op_overloads(threshold: int, *, run_pf: bool, threshold_text: Optional[str] = None) -> _Op:
    threshold_text = threshold_text or f"{threshold}%"
    clause = f"list every line whose loading is above {threshold_text}"
    if run_pf:
        clause = "run the power flow, then " + clause
    return _Op(
        clause,
        [_call("run_powerflow")] if run_pf else [],
        {"kind": "overloads_above", "threshold_percent": int(threshold)},
    )


def op_n1(top_k: int = 5, criteria: str = "max_violations", *, explicit: bool) -> _Op:
    if explicit:
        clause = f"run an N-1 contingency analysis ranked by {criteria.replace('_', ' ')} and report the {top_k} worst outages"
        calls = [_call("run_n1_contingency", top_k=int(top_k), criteria=str(criteria))]
    else:
        clause = "run an N-1 contingency analysis and report the worst single outage"
        calls = [_call("run_n1_contingency")]
    return _Op(clause, calls, {"kind": "n1_worst_outage", "top_k": int(top_k), "criteria": str(criteria)})


# --------------------------------------------------------------------------- templates

def _join(case_phrase: str, ops: list[_Op]) -> str:
    clauses = [o.clause for o in ops]
    if not clauses:
        return f"Load {case_phrase}."
    if len(clauses) == 1:
        return f"Load {case_phrase} and {clauses[0]}."
    if len(clauses) == 2:
        return f"Load {case_phrase}, {clauses[0]}, then {clauses[1]}."
    body = ", ".join(clauses[:-1])
    return f"Load {case_phrase}, {body}, and finally {clauses[-1]}."


def _assemble(rng: random.Random, facts: _CaseFacts, ops: list[_Op], notes: list[str]) -> tuple[str, list, dict, str]:
    calls: list[dict[str, Any]] = [_call("load_case", case_name=facts.case_name)]
    for o in ops:
        calls.extend(o.calls)
    query = ops[-1].query if ops else {"kind": "network_info"}
    all_notes = [n for n in notes if n] + [o.notes for o in ops if o.notes]
    return _join(_case_phrase(rng, facts), ops), calls, query, " ".join(all_notes)


def _template_plain(rng: random.Random, facts: _CaseFacts) -> tuple[str, list, dict, str]:
    kind = rng.choice(["load", "pf", "modify_load", "disconnect", "worst_voltage", "overloads", "n1"])
    ops: list[_Op] = []
    notes: list[str] = []
    if kind == "pf":
        ops = [op_run_pf()]
    elif kind == "modify_load":
        bus, p = _pick_load_bus_and_mw(rng, facts, seeded=False)
        ops = [op_modify_load(bus, p)]
        notes = ["Plain template uses the first load bus at its nominal MW value."]
    elif kind == "disconnect":
        fb, tb = _pick_line(rng, facts, seeded=False)
        ops = [op_disconnect(fb, tb)]
    elif kind == "worst_voltage":
        ops = [op_worst_voltage(run_pf=True)]
    elif kind == "overloads":
        ops = [op_overloads(100, run_pf=True)]
    elif kind == "n1":
        ops = [op_n1(explicit=False)]
        notes = ["Default N-1 arguments (top_k=5, criteria=max_violations) are acceptable."]
    return _assemble(rng, facts, ops, notes)


def _template_parameterized(rng: random.Random, facts: _CaseFacts) -> tuple[str, list, dict, str]:
    kind = rng.choice(["modify_load", "disconnect", "overloads", "n1"])
    if kind == "modify_load":
        bus, p = _pick_load_bus_and_mw(rng, facts, seeded=True)
        ops = [op_modify_load(bus, p)]
    elif kind == "disconnect":
        fb, tb = _pick_line(rng, facts, seeded=True)
        ops = [op_disconnect(fb, tb)]
    elif kind == "overloads":
        ops = [op_overloads(rng.choice(THRESHOLDS_PERCENT), run_pf=True)]
    else:
        ops = [op_n1(rng.choice(N1_TOP_K_CHOICES), rng.choice(N1_CRITERIA), explicit=True)]
    return _assemble(rng, facts, ops, [])


def _template_multistep(rng: random.Random, facts: _CaseFacts) -> tuple[str, list, dict, str]:
    n_ops = rng.randint(2, 4)
    ops: list[_Op] = []
    disconnected: list[tuple[int, int]] = []
    for _ in range(n_ops - 1):
        choices = ["modify_load", "disconnect"] + (["reconnect"] if disconnected else [])
        kind = rng.choice(choices)
        if kind == "modify_load":
            bus, p = _pick_load_bus_and_mw(rng, facts, seeded=True)
            ops.append(op_modify_load(bus, p))
        elif kind == "disconnect":
            candidates = [l for l in facts.safe_lines if l not in disconnected] or list(facts.safe_lines)
            fb, tb = rng.choice(candidates)
            disconnected.append((fb, tb))
            ops.append(op_disconnect(fb, tb))
        else:
            fb, tb = disconnected.pop(rng.randrange(len(disconnected)))
            ops.append(op_reconnect(fb, tb))
    final = rng.choice(["worst_voltage", "overloads", "n1"])
    if final == "worst_voltage":
        last = op_worst_voltage(run_pf=True)
        last.clause = "re" + last.clause
    elif final == "overloads":
        last = op_overloads(rng.choice(THRESHOLDS_PERCENT), run_pf=True)
        last.clause = "re" + last.clause
    else:
        last = op_n1(rng.choice(N1_TOP_K_CHOICES), rng.choice(N1_CRITERIA), explicit=True)
    ops.append(last)
    notes = [
        "modify_load/disconnect_line/reconnect_line already recompute the power flow; the explicit "
        "run_powerflow mirrors the wording ('rerun') and is idempotent. Operations must be applied in the stated order."
    ]
    return _assemble(rng, facts, ops, notes)


def _template_ambiguous(rng: random.Random, facts: _CaseFacts) -> tuple[str, list, dict, str]:
    kind = rng.choice(["modify_load", "disconnect", "overloads"])
    if kind == "modify_load":
        bus, p = _pick_load_bus_and_mw(rng, facts, seeded=True)
        noise = rng.choice(["words", "mva", "zero_based", "one_based", "kw_thousands", "lower_mw"])
        if noise == "words":
            op = op_modify_load(bus, p, bus_text=f"bus {_num_words(bus)}")
            note = f"Intended reading: 'bus {_num_words(bus)}' is MATPOWER bus {bus}."
        elif noise == "mva":
            op = op_modify_load(bus, p, value_text=f"{_fmt_mw(p)} MVA")
            note = f"Intended reading: 'MVA' is a unit slip for MW; set active power p_mw={_fmt_mw(p)} and leave q_mvar unchanged."
        elif noise == "zero_based":
            op = op_modify_load(bus, p, bus_text=f"bus {bus - 1} (0-based)")
            note = f"Intended reading: 0-based index {bus - 1} is MATPOWER bus {bus}; tool arguments use MATPOWER 1-based ids, so bus_id={bus}."
        elif noise == "one_based":
            op = op_modify_load(bus, p, bus_text=f"bus {bus} (1-based)")
            note = f"Intended reading: the '(1-based)' hint is redundant; bus_id={bus}."
        elif noise == "kw_thousands":
            op = op_modify_load(bus, p, value_text=f"{int(round(p * 1000)):,} kw")
            note = f"Intended reading: '{int(round(p * 1000)):,} kw' is {_fmt_mw(p)} MW (thousands separator, lowercase unit); p_mw={_fmt_mw(p)}."
        else:
            op = op_modify_load(bus, p, value_text=f"{_fmt_mw(p)} mw")
            note = f"Intended reading: lowercase 'mw' means MW; p_mw={_fmt_mw(p)}."
        ops = [op]
    elif kind == "disconnect":
        fb, tb = _pick_line(rng, facts, seeded=True)
        noise = rng.choice(["words", "zero_based", "one_based"])
        if noise == "words":
            op = op_disconnect(fb, tb, fb_text=f"bus {_num_words(fb)}", tb_text=f"bus {_num_words(tb)}")
            note = f"Intended reading: spelled-out bus numbers are MATPOWER buses {fb} and {tb}."
        elif noise == "zero_based":
            op = op_disconnect(fb, tb, fb_text=f"bus {fb - 1}", tb_text=f"bus {tb - 1} (0-based)")
            note = (
                f"Intended reading: the '(0-based)' hint applies to both ids; 0-based {fb - 1}-{tb - 1} is "
                f"MATPOWER line {fb}-{tb}, so from_bus={fb}, to_bus={tb}."
            )
        else:
            op = op_disconnect(fb, tb, fb_text=f"bus {fb}", tb_text=f"bus {tb} (1-based)")
            note = f"Intended reading: the '(1-based)' hint is redundant; from_bus={fb}, to_bus={tb}."
        ops = [op]
    else:
        t = rng.choice(THRESHOLDS_PERCENT)
        noise = rng.choice(["words", "lower_pct"])
        if noise == "words":
            op = op_overloads(t, run_pf=True, threshold_text=f"{_num_words(t)} percent")
            note = f"Intended reading: '{_num_words(t)} percent' is a loading threshold of {t}%."
        else:
            op = op_overloads(t, run_pf=True, threshold_text=f"{t} pct of rating")
            note = f"Intended reading: '{t} pct of rating' is loading_percent > {t}."
        ops = [op]
    return _assemble(rng, facts, ops, [note])


_TEMPLATES = {
    "plain": _template_plain,
    "parameterized": _template_parameterized,
    "multistep": _template_multistep,
    "ambiguous": _template_ambiguous,
}


# --------------------------------------------------------------------------- stress template


class _StressVerifier:
    """Runs candidate operations with PandaPower on the seed-perturbed case.

    Mirrors what `compute_ground_truth` will do (same perturbation, same solver
    functions the `ToolDispatcher` calls) so the `expected_outcome` written into a
    stress request is the outcome the ground truth will observe at `k`.
    """

    def __init__(self, case_name: str, *, seed: int, k: int) -> None:
        net = copy.deepcopy(_load_base_net(case_name))
        perturb_network(net, seed=seed, k=k)
        self._net = net
        self.base_isolated = _isolated_buses(net)
        self.n_solves = 0

    def outcome(self, ops: list[_Op]) -> tuple[str, list[int]]:
        """(expected_outcome, newly isolated display ids) after applying `ops` in order."""
        net = copy.deepcopy(self._net)
        for op in ops:
            for call in op.calls:
                _apply_call_to_net(net, call)
        final = run_power_flow(net)
        self.n_solves += 1
        new_isolated = sorted(_isolated_buses(net) - self.base_isolated)
        return _classify_outcome(bool(final.converged), new_isolated), new_isolated


def _apply_call_to_net(net: Any, call: dict[str, Any]) -> None:
    """Apply one mutating intended call directly with the solver functions (no dispatcher)."""
    tool, args = str(call["tool"]), dict(call.get("args") or {})
    if tool == "modify_load":
        _pf_modify_bus_load(net, bus_id=int(args["bus_id"]), p_mw=float(args["p_mw"]),
                            q_mvar=None if args.get("q_mvar") is None else float(args["q_mvar"]))
    elif tool == "disconnect_line":
        _pf_disconnect_line(net, from_bus=int(args["from_bus"]), to_bus=int(args["to_bus"]))
    elif tool == "reconnect_line":
        _pf_reconnect_line(net, from_bus=int(args["from_bus"]), to_bus=int(args["to_bus"]))
    # load_case / run_powerflow / read-only tools: nothing to apply, the final solve follows.


def _fmt_factor(f: int) -> str:
    return f"{_num_words(f)} times its nominal value"


def op_stress_load(facts: _CaseFacts, bus: int, factor: int) -> _Op:
    """Raise the load at `bus` to `factor` x nominal, scaling P and Q together (constant power factor).

    Text and tool arguments use the same 1-decimal values so the verifier executes exactly
    what the request asks for. Buses with non-positive nominal Q are scaled on P only.
    """
    p = round(facts.base_load_mw[bus] * factor, 1)
    q_nom = float(facts.base_load_mvar.get(bus, 0.0))
    if q_nom > 0.0:
        q = round(q_nom * factor, 1)
        return _Op(
            f"increase the load at bus {bus} to {_fmt_mw(p)} MW and {_fmt_mw(q)} Mvar ({_fmt_factor(factor)})",
            [_call("modify_load", bus_id=int(bus), p_mw=float(p), q_mvar=float(q))],
            {"kind": "powerflow_summary"},
        )
    return _Op(
        f"increase the active load at bus {bus} to {_fmt_mw(p)} MW ({_fmt_factor(factor)})",
        [_call("modify_load", bus_id=int(bus), p_mw=float(p))],
        {"kind": "powerflow_summary"},
    )


def _stress_overload_ops(
    rng: random.Random, facts: _CaseFacts, verifier: _StressVerifier, prefix: list[_Op], *, k: int
) -> tuple[list[_Op], str, str]:
    """Kind (a): scale one or several loads until Newton-Raphson stops converging.

    Ladder (deterministic per rng): the first bus is drawn from the `STRESS_START_POOL`
    largest loads, further buses are added from the largest remaining load down. For
    each bus count 1..STRESS_MAX_BUSES the top factor (x6) is tried first; once it fails,
    the smallest failing factor in STRESS_FACTORS is kept. Every candidate is executed
    on the perturbed case (after `prefix`), so the returned outcome is the observed one.
    """
    used = {int(c["args"]["bus_id"]) for op in prefix for c in op.calls if c["tool"] == "modify_load"}
    ordered = [b for b in facts.load_buses_by_size() if b not in used]
    if not ordered:
        ordered = list(facts.load_buses_by_size())
    start = rng.choice(ordered[: min(STRESS_START_POOL, len(ordered))])
    order = [start] + [b for b in ordered if b != start]
    top = STRESS_FACTORS[-1]
    for nb in range(1, min(STRESS_MAX_BUSES, len(order)) + 1):
        buses = order[:nb]
        ops = [op_stress_load(facts, b, top) for b in buses]
        outcome, _ = verifier.outcome(prefix + ops)
        if outcome == "converged":
            continue
        factor = top
        for f in STRESS_FACTORS[:-1]:
            cand = [op_stress_load(facts, b, f) for b in buses]
            out_f, _ = verifier.outcome(prefix + cand)
            if out_f != "converged":
                ops, outcome, factor = cand, out_f, f
                break
        buses_txt = ", ".join(str(b) for b in buses)
        note = (
            f"Stress (load ramp): the load at bus{'es' if nb > 1 else ''} {buses_txt} is raised to {factor}x nominal "
            f"(P and Q scaled together). The Newton-Raphson power flow should not converge; verified with PandaPower on "
            f"the seed-perturbed case (k={k}). Expected outcome: {outcome}. A correct answer reports the failure and no voltages or flows."
        )
        return ops, outcome, note
    # Ladder exhausted: keep the mildest candidate and say honestly that it converges.
    ops = [op_stress_load(facts, start, top)]
    note = (
        f"Stress (load ramp) at bus {start} x{top}: PandaPower still converges on this seed-perturbed case (k={k}) even after "
        f"combining up to {STRESS_MAX_BUSES} buses; the request stays a heavy-load case. Expected outcome: converged."
    )
    return ops, "converged", note


def _stress_island_ops(
    rng: random.Random, facts: _CaseFacts, verifier: _StressVerifier, prefix: list[_Op], *, k: int
) -> tuple[list[_Op], str, str]:
    """Kind (b): disconnect a branch that is NOT in `safe_lines`, so part of the grid loses its slack."""
    already = {tuple(sorted((int(c["args"]["from_bus"]), int(c["args"]["to_bus"]))))
               for op in prefix for c in op.calls if c["tool"] == "disconnect_line"}
    candidates = [b for b in facts.unsafe_branches if tuple(sorted((b[0], b[1]))) not in already] or list(facts.unsafe_branches)
    fb, tb, kind, isolated = rng.choice(candidates)
    op = op_disconnect(fb, tb, what="transformer branch" if kind == "trafo" else "line")
    outcome, observed = verifier.outcome(prefix + [op])
    iso = observed or list(isolated)
    iso_txt = ", ".join(str(b) for b in iso) if iso else "part of the grid"
    plural = len(iso) > 1
    if outcome == "islanded":
        what_happens = (
            f"bus{'es' if plural else ''} {iso_txt} become{'' if plural else 's'} isolated (no path to the slack); PandaPower solves "
            f"the remaining grid with the isolated bus{'es' if plural else ''} out of service, so no voltage exists for {iso_txt}"
        )
    elif outcome == "non_converged":
        what_happens = f"bus{'es' if plural else ''} {iso_txt} become{'' if plural else 's'} isolated and the remaining grid does not converge"
    else:
        what_happens = "the grid splits into islands that each keep a slack, and the power flow still converges"
    note = (
        f"Stress (islanding): branch {fb}-{tb} ({kind}) is the only connection of bus{'es' if plural else ''} {iso_txt}; "
        f"disconnecting it splits the grid and {what_happens}. Verified with PandaPower on the seed-perturbed case (k={k}). "
        f"Expected outcome: {outcome}. A correct answer reports the split instead of quoting a voltage for the isolated bus."
    )
    return [op], outcome, note


def _template_stress(rng: random.Random, facts: _CaseFacts, *, seed: int, k: int = STRESS_VERIFY_K) -> tuple[str, list, dict, str, str]:
    """Requests whose intended operations break the solver or split the grid.

    Kinds (chosen per seed): ``overload`` (a), ``island`` (b, only for cases with an
    unsafe branch), ``multistep`` (c: one benign modification, then a breaking one,
    then "report the worst voltage" / "list overloads"). Returns the usual 4-tuple plus
    the verified ``expected_outcome``.
    """
    has_island = bool(facts.unsafe_branches)
    kind = rng.choice(["overload", "multistep"] + (["island"] if has_island else []))
    verifier = _StressVerifier(facts.case_name, seed=seed, k=k)
    prefix: list[_Op] = []
    notes: list[str] = []
    if kind == "multistep":
        if rng.random() < 0.5:
            bus, p = _pick_load_bus_and_mw(rng, facts, seeded=True)
            prefix = [op_modify_load(bus, p)]
        else:
            fb, tb = _pick_line(rng, facts, seeded=True)
            prefix = [op_disconnect(fb, tb)]
        # 2:1 toward the load ramp: islanding already has its own kind above.
        breaking = rng.choice(["overload", "overload"] + (["island"] if has_island else []))
    else:
        breaking = kind
    if breaking == "island":
        ops, expected, note = _stress_island_ops(rng, facts, verifier, prefix, k=k)
    else:
        ops, expected, note = _stress_overload_ops(rng, facts, verifier, prefix, k=k)
    all_ops = prefix + ops
    if kind == "multistep":
        if rng.random() < 0.5:
            last = op_worst_voltage(run_pf=True)
        else:
            last = op_overloads(rng.choice(THRESHOLDS_PERCENT), run_pf=True)
        last.clause = "re" + last.clause
        all_ops.append(last)
        notes.append(
            "Stress (multi-step): the first modification is benign, the second is the breaking one; operations must be applied "
            "in the stated order and the final report must reflect the broken state (mutating tools already recompute the power flow; "
            "the explicit run_powerflow mirrors 'rerun' and is idempotent)."
        )
    notes.append(note)
    text, calls, query, notes_str = _assemble(rng, facts, all_ops, notes)
    return text, calls, query, notes_str, expected


# --------------------------------------------------------------------------- public API

def generate_requests(
    case_name: str,
    n: int,
    seed: int,
    difficulties: Optional[list[str]] = None,
) -> list[Request]:
    """Generate `n` requests, cycling through `difficulties` so they stay balanced.

    Fully reproducible for the same arguments; `ground_truth` is left as None
    (fill it with `compute_ground_truth`). The default mix is `DIFFICULTIES`; pass
    `difficulties=["stress"]` (or include it) to get solver-breaking requests, whose
    `expected_outcome` is verified with PandaPower at generation time (k=STRESS_VERIFY_K).
    """
    diffs = list(difficulties) if difficulties else list(DIFFICULTIES)
    unknown = set(diffs) - set(ALL_DIFFICULTIES)
    if unknown:
        raise ValueError(f"Unknown difficulties: {sorted(unknown)}. Allowed: {list(ALL_DIFFICULTIES)}")

    facts = _case_facts(case_name)
    rng = random.Random(int(seed))
    out: list[Request] = []
    for i in range(int(n)):
        difficulty = diffs[i % len(diffs)]
        req_seed = rng.randrange(1, 2**31 - 1)
        if difficulty == STRESS_DIFFICULTY:
            text, calls, query, notes, expected = _template_stress(random.Random(req_seed), facts, seed=req_seed)
        else:
            text, calls, query, notes = _TEMPLATES[difficulty](random.Random(req_seed), facts)
            expected = "converged"
        out.append(
            Request(
                id=f"{facts.case_name}-{difficulty}-{i:03d}-s{seed}",
                case_name=facts.case_name,
                seed=req_seed,
                difficulty=difficulty,
                text=text,
                intended_calls=calls,
                notes=notes,
                query=query,
                expected_outcome=expected,
            )
        )
    return out


def _bus_id_of(entry: dict[str, Any]) -> int:
    return int(entry["bus_id"])


def _num(x: Any, ndigits: int) -> Optional[float]:
    """Rounded float, or None for NaN/inf (isolated buses have no solved voltage)."""
    v = float(x)
    return round(v, ndigits) if math.isfinite(v) else None


def _answer(query: dict[str, Any], pf: Optional[dict[str, Any]], n1_report: Optional[dict[str, Any]],
            network_info: Optional[dict[str, Any]]) -> Any:
    kind = query.get("kind", "network_info")
    if kind == "network_info" or pf is None:
        return network_info
    if not pf.get("converged"):
        return {"converged": False}
    if kind == "worst_voltage_bus":
        solved = [b for b in pf["bus_voltages"] if math.isfinite(float(b["vm_pu"]))]
        worst = min(solved, key=lambda b: float(b["vm_pu"]))
        return {"bus_id": int(worst["bus_id"]), "vm_pu": round(float(worst["vm_pu"]), 6)}
    if kind == "overloads_above":
        thr = float(query["threshold_percent"])
        lines = [
            {"line_id": int(l["line_id"]), "from_bus": int(l["from_bus"]), "to_bus": int(l["to_bus"]),
             "loading_percent": round(float(l["loading_percent"]), 4)}
            for l in pf["line_flows"] if float(l["loading_percent"]) > thr
        ]
        return {"threshold_percent": thr, "lines": lines}
    if kind == "n1_worst_outage":
        if not n1_report or not n1_report.get("results"):
            return {"worst": None, "ranking": []}
        rank = [
            {"from_bus": int(r["from_bus"]), "to_bus": int(r["to_bus"]), "branch_type": r["branch_type"],
             "converged": bool(r["converged"]), "n_voltage_violations": int(r["n_voltage_violations"]),
             "n_thermal_violations": int(r["n_thermal_violations"]), "score": round(float(r["score"]), 4)}
            for r in n1_report["results"]
        ]
        return {"criteria": n1_report.get("criteria"), "top_k": n1_report.get("top_k"), "worst": rank[0], "ranking": rank}
    # powerflow_summary
    return {
        "converged": True,
        "total_load_mw": round(float(pf["total_load_mw"]), 4),
        "total_generation_mw": round(float(pf["total_generation_mw"]), 4),
        "total_loss_mw": round(float(pf["total_loss_mw"]), 4),
        "n_voltage_violations": len(pf["voltage_violations"]),
        "n_thermal_violations": len(pf["thermal_violations"]),
    }


def _describe_outcome(outcome: str, isolated: list[int]) -> str:
    if outcome == "non_converged":
        return "The Newton-Raphson power flow did not converge for the requested state; no bus voltages or line flows exist."
    if outcome == "islanded":
        iso = ", ".join(str(b) for b in isolated)
        return (
            f"The requested state splits the grid: bus{'es' if len(isolated) > 1 else ''} {iso} "
            f"{'have' if len(isolated) > 1 else 'has'} no path to the slack and {'are' if len(isolated) > 1 else 'is'} "
            f"solved as out of service (no voltage); the remaining grid converged."
        )
    return "The power flow converged."


def compute_ground_truth(req: Request, *, k: int = 1) -> dict[str, Any]:
    """Execute `req.intended_calls` on a fresh, seed-perturbed case and return a JSON-serializable dict.

    The case is perturbed (`perturb_network`, seed=req.seed) right after `load_case`. After all
    calls, the final network state is re-solved directly to snapshot voltages, flows and violations.

    A non-converged or islanded final state is a *valid* ground truth (stress items): the dict
    then carries ``converged=False`` and/or ``island=True`` with ``isolated_buses``, its
    ``expected_outcome`` is the observed classification ("non_converged" | "islanded" |
    "converged"), ``outcome_matches_request`` says whether it equals ``req.expected_outcome``,
    and ``answer`` describes the outcome. Voltages/flows of isolated elements are ``None``.
    """
    ctx = ToolContext(session=SessionState())
    dispatcher = build_default_dispatcher(ctx)
    tool_errors: list[dict[str, Any]] = []
    network_info: Optional[dict[str, Any]] = None
    n1_report: Optional[dict[str, Any]] = None
    executed: list[str] = []
    base_isolated: set[int] = set()

    def _load_and_perturb(case_name: str) -> dict[str, Any]:
        nonlocal base_isolated
        out = json.loads(dispatcher.dispatch("load_case", {"case_name": case_name}))
        perturb_network(ctx.net, seed=req.seed, k=k)
        base_isolated = _isolated_buses(ctx.net)
        return out

    for call in req.intended_calls:
        tool, args = str(call["tool"]), dict(call.get("args") or {})
        if tool == "load_case":
            out = _load_and_perturb(str(args.get("case_name", req.case_name)))
            network_info = out if "error" not in out else None
        else:
            if ctx.net is None:
                network_info = _load_and_perturb(req.case_name)
            out = json.loads(dispatcher.dispatch(tool, args))
        executed.append(tool)
        if isinstance(out, dict) and out.get("error"):
            tool_errors.append({"tool": tool, "args": args, **{k_: v for k_, v in out.items() if k_ != "figure_json"}})
        if tool == "run_n1_contingency" and isinstance(out, dict) and "n1_report" in out:
            n1_report = out["n1_report"]

    if ctx.net is None:
        network_info = _load_and_perturb(req.case_name)

    final = run_power_flow(ctx.net, config=ctx.solver_config).model_dump()
    converged = bool(final["converged"])
    isolated = sorted(_isolated_buses(ctx.net) - base_isolated)
    outcome = _classify_outcome(converged, isolated)
    violations: list[dict[str, Any]] = [
        {"type": str(v["violation_type"].value if hasattr(v["violation_type"], "value") else v["violation_type"]),
         "bus_id": int(v["bus_id"]), "vm_pu": _num(v["vm_pu"], 6)}
        for v in final["voltage_violations"]
    ] + [
        {"type": "thermal", "line_id": int(t["line_id"]), "from_bus": int(t["from_bus"]), "to_bus": int(t["to_bus"]),
         "loading_percent": _num(t["loading_percent"], 4)}
        for t in final["thermal_violations"]
    ]
    answer = _answer(req.query, final, n1_report, network_info)
    if outcome != "converged":
        outcome_info = {
            "expected_outcome": outcome,
            "converged": converged,
            "island": bool(isolated),
            "isolated_buses": isolated,
            "description": _describe_outcome(outcome, isolated),
        }
        answer = {**(answer if isinstance(answer, dict) else {"value": answer}), **outcome_info}
    return {
        "converged": converged,
        "island": bool(isolated),
        "isolated_buses": isolated,
        "expected_outcome": outcome,
        "outcome_matches_request": outcome == str(req.expected_outcome),
        "perturbation": {"seed": int(req.seed), "k": int(k), "fraction_per_k": PERTURB_FRACTION_PER_K},
        "executed_tools": executed,
        "tool_errors": tool_errors,
        "network_info": network_info,
        "bus_vm_pu": {str(int(b["bus_id"])): _num(b["vm_pu"], 6) for b in final["bus_voltages"]},
        "line_flows": [
            {"line_id": int(l["line_id"]), "from_bus": int(l["from_bus"]), "to_bus": int(l["to_bus"]),
             "p_from_mw": _num(l["p_from_mw"], 4), "loading_percent": _num(l["loading_percent"], 4)}
            for l in final["line_flows"]
        ],
        "violations": violations,
        "answer": answer,
    }


def to_jsonl(requests: list[Request], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        for r in requests:
            fh.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")


def from_jsonl(path: str | Path) -> list[Request]:
    out: list[Request] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(Request(**json.loads(line)))
    return out


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate seeded NL power-flow requests with ground truth.")
    parser.add_argument("--case", default="case14")
    parser.add_argument("--n", type=int, default=40)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--k", type=int, default=1, help="perturbation strength (paper uses k=1)")
    parser.add_argument("--difficulty", dest="difficulties", action="append", choices=ALL_DIFFICULTIES, default=[],
                        help=f"repeatable; default mix is {list(DIFFICULTIES)}; '{STRESS_DIFFICULTY}' is opt-in")
    parser.add_argument("--out", default=None, help="default: evaluation/requests_<case>.jsonl")
    parser.add_argument("--no-ground-truth", action="store_true")
    args = parser.parse_args(argv)

    reqs = generate_requests(args.case, args.n, args.seed, args.difficulties or None)
    if not args.no_ground_truth:
        for r in reqs:
            r.ground_truth = compute_ground_truth(r, k=int(args.k))
    out = Path(args.out) if args.out else PROJECT_ROOT / "benchmarks" / f"requests_{reqs[0].case_name if reqs else args.case}.jsonl"
    to_jsonl(reqs, out)
    n_err = sum(1 for r in reqs if r.ground_truth and r.ground_truth["tool_errors"])
    n_stress = sum(1 for r in reqs if r.difficulty == STRESS_DIFFICULTY)
    msg = f"Wrote {len(reqs)} requests to {out} ({n_err} with tool errors)"
    if n_stress:
        n_fail = sum(1 for r in reqs if r.difficulty == STRESS_DIFFICULTY and r.expected_outcome != "converged")
        n_match = sum(1 for r in reqs if r.difficulty == STRESS_DIFFICULTY and r.ground_truth and r.ground_truth["outcome_matches_request"])
        msg += f"; stress: {n_fail}/{n_stress} expected to fail, {n_match}/{n_stress} ground truths match the expected outcome"
    print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

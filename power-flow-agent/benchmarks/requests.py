"""Seeded natural-language power-flow requests with deterministic ground truth.

Each `Request` pairs a natural-language instruction with the exact ordered tool
calls it is meant to trigger (`intended_calls`, using the tool names and argument
names of `llm/tools.py`) and with the result of executing those calls through the
real `ToolDispatcher` on a seed-perturbed case (`ground_truth`). This separates
*formulation correctness* (did the agent call the right tools with the right
arguments) from *numerical correctness* (does the reported number match the solver).

Bus ids in request text and in tool arguments are MATPOWER 1-based display ids,
which is what `_resolve_bus_index` in `solver/power_flow.py` expects.

CLI:
    python -m benchmarks.requests --case case14 --n 40 --seed 0 --out benchmarks/requests_case14.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from llm.tools import TOOLS, ToolContext, build_default_dispatcher
from models.schemas import SessionState
from solver import case_loader
from solver.power_flow import _bus_display_id, run_power_flow

DIFFICULTIES: tuple[str, ...] = ("plain", "parameterized", "multistep", "ambiguous")
THRESHOLDS_PERCENT: tuple[int, ...] = (80, 90, 100)
N1_TOP_K_CHOICES: tuple[int, ...] = (3, 5, 8)
N1_CRITERIA: tuple[str, ...] = ("max_violations", "max_overload", "min_voltage")
TOOL_NAMES: frozenset[str] = frozenset(t["name"] for t in TOOLS)

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

    @property
    def load_buses(self) -> tuple[int, ...]:
        return tuple(sorted(b for b, p in self.base_load_mw.items() if p > 0.0))


def _connected_without(n_nodes: int, edges: list[tuple[int, int]], skip: int) -> bool:
    adj: dict[int, set[int]] = {i: set() for i in range(n_nodes)}
    for j, (a, b) in enumerate(edges):
        if j == skip:
            continue
        adj[a].add(b)
        adj[b].add(a)
    seen = {0}
    stack = [0]
    while stack:
        u = stack.pop()
        for v in adj[u]:
            if v not in seen:
                seen.add(v)
                stack.append(v)
    return len(seen) == n_nodes


def _case_facts(case_name: str) -> _CaseFacts:
    net, _ = case_loader.load(case_name)
    canonical = case_loader.normalize_case_name(case_name)
    index_list = [int(i) for i in net.bus.index.tolist()]
    pos = {idx: k for k, idx in enumerate(index_list)}
    display = {idx: int(_bus_display_id(net, idx)) for idx in index_list}

    base_load: dict[int, float] = {}
    for _, row in net.load.iterrows():
        b = display[int(row["bus"])]
        base_load[b] = base_load.get(b, 0.0) + float(row["p_mw"])

    edges: list[tuple[int, int]] = []
    line_edge_ids: list[tuple[int, tuple[int, int]]] = []
    for _, row in net.line.iterrows():
        if not bool(row.get("in_service", True)):
            continue
        a, b = int(row["from_bus"]), int(row["to_bus"])
        line_edge_ids.append((len(edges), (display[a], display[b])))
        edges.append((pos[a], pos[b]))
    if hasattr(net, "trafo") and len(net.trafo) > 0:
        for _, row in net.trafo.iterrows():
            if bool(row.get("in_service", True)):
                edges.append((pos[int(row["hv_bus"])], pos[int(row["lv_bus"])]))

    safe = tuple(
        (fb, tb) for edge_idx, (fb, tb) in line_edge_ids if _connected_without(len(index_list), edges, edge_idx)
    )
    return _CaseFacts(
        case_name=canonical,
        n_buses=len(index_list),
        bus_ids=tuple(sorted(display.values())),
        base_load_mw=base_load,
        safe_lines=safe,
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


def op_disconnect(fb: int, tb: int, *, fb_text: Optional[str] = None, tb_text: Optional[str] = None) -> _Op:
    fb_text = fb_text or f"bus {fb}"
    tb_text = tb_text or f"bus {tb}"
    return _Op(
        f"disconnect the line between {fb_text} and {tb_text}",
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


# --------------------------------------------------------------------------- public API

def generate_requests(
    case_name: str,
    n: int,
    seed: int,
    difficulties: Optional[list[str]] = None,
) -> list[Request]:
    """Generate `n` requests, cycling through `difficulties` so they stay balanced.

    Fully reproducible for the same arguments; `ground_truth` is left as None
    (fill it with `compute_ground_truth`).
    """
    diffs = list(difficulties) if difficulties else list(DIFFICULTIES)
    unknown = set(diffs) - set(DIFFICULTIES)
    if unknown:
        raise ValueError(f"Unknown difficulties: {sorted(unknown)}. Allowed: {list(DIFFICULTIES)}")

    facts = _case_facts(case_name)
    rng = random.Random(int(seed))
    out: list[Request] = []
    for i in range(int(n)):
        difficulty = diffs[i % len(diffs)]
        req_seed = rng.randrange(1, 2**31 - 1)
        text, calls, query, notes = _TEMPLATES[difficulty](random.Random(req_seed), facts)
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
            )
        )
    return out


def _bus_id_of(entry: dict[str, Any]) -> int:
    return int(entry["bus_id"])


def _answer(query: dict[str, Any], pf: Optional[dict[str, Any]], n1_report: Optional[dict[str, Any]],
            network_info: Optional[dict[str, Any]]) -> Any:
    kind = query.get("kind", "network_info")
    if kind == "network_info" or pf is None:
        return network_info
    if not pf.get("converged"):
        return {"converged": False}
    if kind == "worst_voltage_bus":
        worst = min(pf["bus_voltages"], key=lambda b: float(b["vm_pu"]))
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


def compute_ground_truth(req: Request, *, k: int = 1) -> dict[str, Any]:
    """Execute `req.intended_calls` on a fresh, seed-perturbed case and return a JSON-serializable dict.

    The case is perturbed (`perturb_network`, seed=req.seed) right after `load_case`. After all
    calls, the final network state is re-solved directly to snapshot voltages, flows and violations.
    """
    ctx = ToolContext(session=SessionState())
    dispatcher = build_default_dispatcher(ctx)
    tool_errors: list[dict[str, Any]] = []
    network_info: Optional[dict[str, Any]] = None
    n1_report: Optional[dict[str, Any]] = None
    executed: list[str] = []

    def _load_and_perturb(case_name: str) -> dict[str, Any]:
        out = json.loads(dispatcher.dispatch("load_case", {"case_name": case_name}))
        perturb_network(ctx.net, seed=req.seed, k=k)
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
    violations: list[dict[str, Any]] = [
        {"type": str(v["violation_type"].value if hasattr(v["violation_type"], "value") else v["violation_type"]),
         "bus_id": int(v["bus_id"]), "vm_pu": round(float(v["vm_pu"]), 6)}
        for v in final["voltage_violations"]
    ] + [
        {"type": "thermal", "line_id": int(t["line_id"]), "from_bus": int(t["from_bus"]), "to_bus": int(t["to_bus"]),
         "loading_percent": round(float(t["loading_percent"]), 4)}
        for t in final["thermal_violations"]
    ]
    return {
        "converged": converged,
        "perturbation": {"seed": int(req.seed), "k": int(k), "fraction_per_k": PERTURB_FRACTION_PER_K},
        "executed_tools": executed,
        "tool_errors": tool_errors,
        "network_info": network_info,
        "bus_vm_pu": {str(int(b["bus_id"])): round(float(b["vm_pu"]), 6) for b in final["bus_voltages"]},
        "line_flows": [
            {"line_id": int(l["line_id"]), "from_bus": int(l["from_bus"]), "to_bus": int(l["to_bus"]),
             "p_from_mw": round(float(l["p_from_mw"]), 4), "loading_percent": round(float(l["loading_percent"]), 4)}
            for l in final["line_flows"]
        ],
        "violations": violations,
        "answer": _answer(req.query, final, n1_report, network_info),
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
    parser.add_argument("--difficulty", dest="difficulties", action="append", choices=DIFFICULTIES, default=[])
    parser.add_argument("--out", default=None, help="default: benchmarks/requests_<case>.jsonl")
    parser.add_argument("--no-ground-truth", action="store_true")
    args = parser.parse_args(argv)

    reqs = generate_requests(args.case, args.n, args.seed, args.difficulties or None)
    if not args.no_ground_truth:
        for r in reqs:
            r.ground_truth = compute_ground_truth(r, k=int(args.k))
    out = Path(args.out) if args.out else PROJECT_ROOT / "benchmarks" / f"requests_{reqs[0].case_name if reqs else args.case}.jsonl"
    to_jsonl(reqs, out)
    n_err = sum(1 for r in reqs if r.ground_truth and r.ground_truth["tool_errors"])
    print(f"Wrote {len(reqs)} requests to {out} ({n_err} with tool errors)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

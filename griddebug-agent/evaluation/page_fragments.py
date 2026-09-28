"""This case study's contribution to the shared evaluation site.

The chrome lives in ``visuals/shell.py`` at the repository root; this module
writes only content. Every fact is read from the code at build time: the
method registry, the gate's condition table, the frozen scenario manifest, the
prompt builders, the tool catalogue and the result files. Nothing on the page
is typed by hand twice.

Usage (from griddebug-agent/):
    .venv/bin/python -m evaluation.page_fragments /tmp/fragments.json

Normally invoked by ``python -m visuals.build`` from the repository root.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT.parent))  # so `visuals` is importable

from visuals.shell import E, card, chip, diagram_row, kv, note, pipeline, prompt_block, table, verdict  # noqa: E402

import methods  # noqa: E402
from config import ALL_NETWORKS, MAX_LLM_CALLS, MAX_LOADING_PERCENT, MAX_TOOL_CALLS, NETWORK_LABELS, NETWORKS, SCENARIO_TIMEOUT_S, V_MAX_PU, V_MIN_PU  # noqa: E402

CASE_ID = "griddebug"
CASE_TITLE = "GridDebug"

DIAGRAMS: Dict[str, Dict[str, Any]] = {
    "rule_based": {"steps": [("failed network", "input"), ("rule engine", "code"), ("fixed policy + power flow", "solver"), ("template answer", "out")],
                   "note": "No language model. Rules classify the evidence, a fixed policy acts, the power flow verifies, inside the same budget."},
    "llm_only_structured": {"steps": [("failed network", "input"), ("LLM writes the actions", "llm"), ("harness applies them once", "solver")],
                            "note": "One call, no tools. The model reads the evidence and writes the actions and the state it expects; the solver checks afterwards."},
    "llm_only_cot": {"steps": [("failed network", "input"), ("LLM reasons, then writes", "llm"), ("harness applies them once", "solver")],
                     "note": "One added reasoning section. Identical to the method on its left in every other respect."},
    "plan_act_nogate": {"steps": [("failed network", "input"), ("LLM writes the whole plan", "plan"), ("harness runs every step", "solver"), ("LLM writes the answer", "llm")],
                        "note": "Plans once. The whole sequence of tool calls is committed before any result comes back."},
    "react_nogate": {"steps": [("failed network", "input"), ("LLM decides a tool call", "llm"), ("tool runs on the network", "solver"), ("LLM writes the answer", "llm")],
                     "loop": 2, "note": f"Up to {MAX_LLM_CALLS} model calls and {MAX_TOOL_CALLS} tool calls. The model sees every result; nothing checks the answer."},
    "griddebug": {"steps": [("failed network", "input"), ("LLM decides a tool call", "llm"), ("tool runs on the network", "solver"), ("gate G1-G7", "gate")],
                  "loop": 2, "branch": ("report", "escalate"),
                  "note": "The same loop, then six conditions on the answer. A claim the solver contradicts leaves as an escalation, not as a repair."},
}

ROWS: Tuple[Dict[str, str], ...] = (
    {"block": "Conventional workflow", "name": "rule_based", "label": "Rule engine + fixed policy", "llm": "no", "tools": "the same catalogue, directly", "gate": "none",
     "isolates": "no language model anywhere. The rule engine classifies the evidence and a fixed policy acts; what conventional automation already achieves, and where it stops."},
    {"block": "LLM-only prompting", "name": "llm_only_structured", "label": "Structured prompting", "llm": "yes", "tools": "none", "gate": "none",
     "isolates": "the language model on its own. It receives the evidence and the action catalogue as text and writes the actions; the harness applies them once."},
    {"block": "LLM-only prompting", "name": "llm_only_cot", "label": "Chain-of-thought prompting", "llm": "yes", "tools": "none", "gate": "none",
     "isolates": "one added prompt section asking for step-by-step reasoning before the answer. Same input, same budget, same contract as the row above."},
    {"block": "Multi-step agents", "name": "plan_act_nogate", "label": "Plan-and-Act, no gate", "llm": "yes", "tools": "the catalogue, through function calling", "gate": "none",
     "isolates": "solver access through a plan. One call emits the whole sequence, executed without the model seeing the results in between."},
    {"block": "Multi-step agents", "name": "react_nogate", "label": "ReAct, no gate", "llm": "yes", "tools": "the catalogue, through function calling", "gate": "none",
     "isolates": "iteration. The model sees each tool output and may call again, inside the same budget as the row above and the row below."},
    {"block": "Multi-step agents", "name": "griddebug", "label": "GridDebugAgent, solver-grounded", "llm": "yes", "tools": "the catalogue, through function calling", "gate": "seven conditions on the answer",
     "isolates": "the verification gate, and nothing else. Same tools, same budget and same scenarios as ReAct, so any difference between the two rows is the gate."},
)

COLUMNS: Tuple[Dict[str, str], ...] = (
    {"group": "Task utility", "name": "Diagnosis", "what": "the fault type and at least one injected component named in the answer match what the scenario injected", "why": "whether the initiating event was understood, not just the symptom (the formulation column of this case study)"},
    {"group": "Task utility", "name": "Repaired", "what": "the harness's own power flow on the final network converges, no load is islanded, no violation beyond the base network", "why": "the paper's repair definition, made relative to the base network"},
    {"group": "Task utility", "name": "Improved", "what": "converged and fewer new violations than at the start, or a solution where there was none", "why": "partial repairs, honestly reported, are worth something"},
    {"group": "Task utility", "name": "Load served", "what": "the active demand still in service after the repair, against the base network's demand",
     "why": "a network with every load curtailed is secure; without this column the table would call that a repair"},
    {"group": "Task utility", "name": "Violations", "what": "new violations before and after, over scenarios converged at both ends", "why": "a non-converged state is never a count of zero"},
    {"group": "Solver-grounded correctness", "name": "Solved", "what": "repaired, claimed as repaired, every number traceable, final_state consistent with the solver", "why": "the end-to-end verdict, and the first of the three exclusive outcomes"},
    {"group": "Solver-grounded correctness", "name": "Escalated", "what": "the method declared not_repaired or cannot_repair, listing what remains, or the harness had to write the answer", "why": "the second outcome: how much work goes back to a person"},
    {"group": "Solver-grounded correctness", "name": "Wrong, unflagged", "what": "a repair claim the solver contradicts, or an unsupported number, presented as valid", "why": "the third outcome, and the quantity a solver-grounded design exists to drive to zero. The three add up to 100 %"},
    {"group": "Solver-grounded correctness", "name": "Feasible", "what": "the final power flow converges", "why": "the solver status column of the other case studies"},
    {"group": "Solver-grounded correctness", "name": "Traceable", "what": "every number in the answer appears in a tool output or in the evidence", "why": "the reported numbers have an origin that can be checked"},
    {"group": "Cost and operation", "name": "Tokens", "what": "prompt and completion tokens per scenario", "why": "what the architecture costs to run"},
    {"group": "Cost and operation", "name": "Cost, Time", "what": "dollars for the whole run set, and wall time per scenario", "why": "the operating cost of each architecture, on the same scenarios"},
)


# ------------------------------------------------------------------ data


def manifest() -> Optional[Dict[str, Any]]:
    from evaluation.scenarios import manifest as M

    return M.load_manifest()


def method_dirs() -> List[Path]:
    root = PROJECT_ROOT / "results"
    dirs = [p.parent for p in root.glob("*/*/*/*/summary.json")] if root.is_dir() else []
    return sorted(dirs, key=lambda d: (d.parts[-3], d.parts[-4]), reverse=True)


def read_summary(d: Path) -> List[Dict[str, str]]:
    f = d / "summary.csv"
    with f.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh)) if f.exists() else []


def read_header(d: Path) -> Dict[str, Any]:
    return json.loads((d / "summary.json").read_text(encoding="utf-8"))


def sample_request() -> Any:
    from evaluation.requests import build_request

    return build_request("case14", "line_contingency_overload")


# ------------------------------------------------------------------ tabs


def S_N() -> int:
    from evaluation.scenarios import N_INSTANCES

    return N_INSTANCES


def tab_home() -> str:
    m = manifest()
    n_inst = len(m["entries"]) if m else 0
    body = [
        card(
            "The task",
            "<p>A power flow on an IEEE test network has failed or produced limit violations: a line is out, loads have grown, "
            "a generator is gone, a setpoint is wrong. Somebody has to say what happened and bring the network back to a secure "
            "operating point with the actions a control room has: redispatch, curtailment, switching, compensation, setpoints. "
            "Today that somebody is an engineer with a simulator. This case study asks what happens when it is a language model, "
            "and measures six ways of doing it on the same faults.</p>",
            pipeline(
                [("Failed network", "injected fault, solver evidence"),
                 ("Diagnose", "the event, not the symptom"),
                 ("Act", "actions from one catalogue"),
                 ("Verify", "power flow, then G1-G7 (gated row)"),
                 ("Report", "diagnosis, actions, state")],
                loop=(3, 1, "one retry, then escalate"),
            ),
            "<p class='muted' style='text-align:center'>Fig. 1. The pipeline every method is measured on. Only the solver-grounded method has "
            "the Verify stage; the others go from Act to Report.</p>",
        ),
        card(
            "What counts as secure, and why it is relative to the base network",
            f"<p>Limits are the same for everyone: bus voltages within [{V_MIN_PU:.2f}, {V_MAX_PU:.2f}] p.u., lines and transformers at or below "
            f"{MAX_LOADING_PERCENT:.0f} % of their rating, the power flow converged, and no in-service load on a bus without a path to a slack bus.</p>"
            "<p>Two of the three IEEE cases shipped with pandapower violate that band before anything is done to them: IEEE-14 has nine buses above "
            "1.05 p.u. and IEEE-57 thirty-nine below 0.95 p.u. A target of zero violations on those networks would ask the method to fix the base "
            "case instead of the injected fault, and would make network size look like the cause of every failure. So a violation counts only if the "
            "same bus or branch was inside its limits in the unmodified network. The evidence every method receives lists the base violations "
            "apart, and the check tools mark each one <code>in_base</code>. The absolute count is kept beside it.</p>"
            "<p>Line ratings follow the rule of the power-flow case study: every line is rated at 1.25 times its base-case current, with a floor of "
            "5 % of the largest. The MATPOWER placeholder ratings put the IEEE-14 base case at 1.5 % loading, so no thermal fault could ever "
            "overload a line before this rule.</p>",
        ),
        "<div class='grid g3'>"
        + card("What a correct answer needs",
               "<ul><li><b>The diagnosis:</b> the fault type and the components that were changed, not the buses that show the symptom.</li>"
               "<li><b>A secure network:</b> converged, no islanded load, no new violation, verified by the harness's own power flow.</li>"
               "<li><b>An honest report:</b> status and final state that agree with the solver, numbers that come from a tool output.</li></ul>")
        + card("What can go wrong",
               "<ul><li>A repair claimed after actions that were never verified.</li><li>A number quoted from before the last action.</li>"
               "<li>Shunts and switches piled on until the budget runs out.</li><li>A load left on an island with a NaN voltage nobody reads.</li>"
               "<li>A right repair of the wrong fault, with the base network's violations blamed on the method.</li></ul>")
        + card("What is expected of the gated row",
               f"<p>Every answer passes six verification conditions or leaves as an escalation with what remains listed. The target: "
               f"{verdict('solved')} + {verdict('escalated')} = 100 %, {verdict('wrong')} = 0.</p>")
        + "</div>",
        card("Identical for every method",
             chip(f"{len(NETWORKS)} IEEE networks") + chip(f"{S_N()} scenarios per network, from 13 fault classes") + chip("one request template")
             + chip("one evidence block") + chip("one tool catalogue") + chip(f"{MAX_LLM_CALLS} model calls, {MAX_TOOL_CALLS} tool calls, {SCENARIO_TIMEOUT_S:.0f} s per scenario")
             + chip("temperature 0") + chip("one answer contract") + chip("one scorer") + chip("every message kept in the trace")),
    ]
    return "".join(body)


def tab_methods() -> str:
    rows = []
    last = ""
    for r in ROWS:
        block = "" if r["block"] == last else f"<b>{E(r['block'])}</b>"
        last = r["block"]
        rows.append([f"<span class='muted'>{block}</span>", f"<b>{E(r['label'])}</b><div class='muted'><code>{E(r['name'])}</code></div>",
                     E(r["llm"]), E(r["tools"]), E(r["gate"]), E(r["isolates"])])
    return "".join([
        card("Six ways to repair the same fault",
             diagram_row([{"title": r["label"], "subtitle": ("no LLM" if r["llm"] == "no" else "LLM only, no tools" if r["tools"] == "none" else "LLM + solver"),
                           **DIAGRAMS[r["name"]]} for r in ROWS])),
        card("Six methods, one factor apart",
             "<p>One conventional workflow with no language model, and five ways of using one. Each row adds a single capability to the row above "
             "it: a language model, then a reasoning section, then access to the solver, then iteration, then verification.</p>",
             table(["Block", "Method", "LLM", "Tools", "Gate", "What it adds over the row above"], rows),
             note("<b>The step the design rests on is the last one.</b> ReAct and GridDebugAgent receive the same tools, the same budget and the "
                  "same scenarios. The only difference is that GridDebugAgent's answer has to pass the verification gate before anyone sees it.", "info")),
        card(
            "Where this design leaves Section 6.4 as submitted",
            "<p>Section 6.4 describes verification <b>inside</b> the loop: the agent re-runs the power flow and checks the "
            "violations before its next step, and the harness re-runs PandaPower at scoring time so a fabricated repair does "
            "not count. It describes no gate on the answer and no way for the agent to escalate. Section 2, on the other "
            "hand, states the rule the whole paper turns on: a reported number passes an explicit verification before it is "
            "surfaced. On GridDebugAgent the two sections disagree, and this implementation resolves them in favour of "
            "Section 2.</p>",
            table(
                ["Section 6.4 as submitted", "what runs here", "why"],
                [
                    ["verification inside the loop only; no answer gate, no escalation",
                     "the same loop, then G1-G7 on the final answer, one retry, then a declared failure",
                     "the row is otherwise not solver-grounded in the sense Section 2 claims, and R3.2 and R4.3 ask for "
                     "verification as a factor that can be isolated, which needs the ungated twin <code>react_nogate</code>"],
                    ["the rule engine's classification is fed into the agent's prompt",
                     "the rule engine is the deterministic row's policy and reaches no method with a language model",
                     "otherwise every row is rules plus a model, and the non-LLM baseline R4.5 asks for does not exist as a "
                     "separate arm"],
                    ["five tool categories, memory management among them",
                     "four kinds, 21 tools; snapshots, OPF, short circuit and DC flow are out",
                     "OPF would solve the repair for the method; the snapshots were used three times in 447 calls and leaked "
                     "state between scenarios through a module-level dictionary"],
                    ["GPT-4o, temperature 0.3, max 50 iterations",
                     f"gpt-4o-mini and gpt-5.6-sol, temperature 0, {MAX_LLM_CALLS} model calls and {MAX_TOOL_CALLS} tool calls",
                     "temperature 0 for reproducibility, the two models the advisor fixed for the main table, and one budget "
                     "shared by the three loop rows so the comparison is matched"],
                    ["one agent against one diagnosis-only baseline",
                     "six methods, the same six as every other case study",
                     "R3.2, R4.3 and R4.5"],
                ],
            ),
            note("Section 6.4 has to be rewritten around this design; the numbers it prints today come from a run that is "
                 "not reproducible from the repository, which is the finding of the September audit. That rewrite is the "
                 "editor's work, not this case study's.", "warn"),
        ),
        side_by_side(),
        card("What the original GridDebugAgent was, and what changed",
             "<p>The code behind the submitted table had one architecture: a ReAct loop with OpenAI function calling, gpt-4o at temperature 0.3, "
             "up to 30 model calls, no verification of the answer, and a baseline that only diagnosed and never acted. It is the <code>react_nogate</code> "
             "row here, with the model, the budget and the tracing made explicit. The rule engine that used to feed hints into the agent's prompt is now "
             "the policy of the <code>rule_based</code> row and reaches no other method: every model-backed row sees the same evidence and nothing "
             "else. The snapshot, OPF, short-circuit and DC tools are out of the catalogue: OPF would solve the repair for the method, and the others "
             "were never used to repair.</p>"),
    ])



# ---------------------------------------------------- the same fault, every method


SBS_METHODS = [r["name"] for r in ROWS]
SBS_PER_NETWORK = 3          # scenarios shown per system, as in the power-flow case study
_SBS_TEXT = 1200             # characters kept of a tool output
_SBS_SAY = 1000              # characters kept of what the model said


def _sbs_clip(s: Any, n: int) -> str:
    t = s if isinstance(s, str) else json.dumps(s, indent=1, ensure_ascii=False)
    t = t or ""
    return t if len(t) <= n else t[:n] + "\n… (" + str(len(t) - n) + " more characters, in the trace file)"


def _sbs_digest(o: Any) -> str:
    """One line a control-room reader can scan, from whatever the tool returned."""
    if not isinstance(o, dict):
        return _sbs_clip(o, 120)
    p: List[str] = []
    if "converged" in o:
        p.append("converged" if o["converged"] else "DID NOT CONVERGE")
    if "n_new_violations" in o:
        p.append(f"{o['n_new_violations']} new violation(s)")
    if "n_new_overloads" in o:
        p.append(f"{o['n_new_overloads']} new overload(s)")
    if "success" in o:
        p.append("applied" if o["success"] else "REFUSED")
    stranded = o.get("islanded_load_buses_after")
    if isinstance(stranded, list) and stranded:
        p.append("strands load on bus " + ", ".join(str(b) for b in stranded))
    if o.get("error"):
        p.append("error: " + _sbs_clip(o["error"], 90))
    if not p:
        return " · ".join(f"{k}={_sbs_clip(v, 60)}" for k, v in list(o.items())[:3])
    return " · ".join(p)


def _sbs_runs() -> Tuple[str, List[Path]]:
    """The newest run set that has the most methods: (tag, its method folders)."""
    groups: Dict[Tuple[str, str], List[Path]] = {}
    for d in method_dirs():
        tag = d.name.split("__")[1] if "__" in d.name else ""
        groups.setdefault((d.parts[-3], tag), []).append(d)
    if not groups:
        return "", []
    (date, tag), _ = max(groups.items(), key=lambda kv: (len({p.name.split("__")[0] for p in kv[1]}), kv[0][0]))
    return tag, [d for (dt, tg), ds in groups.items() if dt == date and tg == tag for d in ds]


def _sbs_pick(rows: List[Dict[str, str]]) -> List[str]:
    """Up to three scenarios, from different categories, preferring the ones the methods disagree on."""
    seen: Dict[str, str] = {}
    for r in rows:
        seen.setdefault(r.get("category", ""), r["request_id"])
    order = ["contingency", "voltage", "thermal", "nonconvergence", "normal"]
    out = [seen[c] for c in order if c in seen]
    out += [rid for rid in (r["request_id"] for r in rows) if rid not in out]
    return out[:SBS_PER_NETWORK]


def _sbs_trace(d: Path, row: Dict[str, str]) -> Optional[Dict[str, Any]]:
    stem = f"{int(row['nn']):02d}_{row['request_id']}"
    p = d / "traces" / f"{stem}.json"
    if not p.is_file():
        return None
    t = json.loads(p.read_text(encoding="utf-8"))
    steps = []
    for i, rd in enumerate(t.get("rounds") or [], 1):
        llm = rd.get("llm") or {}
        tools = []
        for x in rd.get("tools") or []:
            tools.append({"name": x.get("name"), "kind": x.get("kind"),
                          "args": ", ".join(f"{k}={_sbs_clip(v, 60)}" for k, v in (x.get("args") or {}).items()),
                          "says": _sbs_digest(x.get("output")), "raw": _sbs_clip(x.get("output"), _SBS_TEXT),
                          "bad": x.get("ok") is False or (isinstance(x.get("output"), dict)
                                                          and (x["output"].get("success") is False or x["output"].get("converged") is False))})
        steps.append({"n": i, "say": _sbs_clip(llm.get("content") or "", _SBS_SAY),
                      "acted": any(x.get("kind") == "action" for x in rd.get("tools") or []), "tools": tools})
    msgs = t.get("messages") or []
    user = next((m.get("content") for m in msgs if m.get("role") == "user"), None)
    return {
        "outcome": row.get("outcome", ""), "steps": steps,
        "llm_calls": t.get("n_llm_calls"), "tool_calls": t.get("n_tool_calls"),
        "tokens": (t.get("prompt_tokens") or 0) + (t.get("completion_tokens") or 0),
        "seconds": round(float(t.get("wall_time_s") or 0), 1),
        "final": ("did not converge" if row.get("final_converged") != "True"
                  else "secure" if row.get("final_secure") == "True" else f"{row.get('final_n_new')} new violation(s)"),
        "islanded": row.get("final_islanded") if row.get("final_islanded") not in ("", "[]", None) else "",
        "attempts": [{"n": g.get("attempt"), "passed": bool(g.get("passed")), "failed": g.get("failed") or []}
                     for g in (t.get("gate_history") or [])],
        "gate": (None if not t.get("gate") else
                 {"passed": bool(t["gate"].get("passed")), "failed": t["gate"].get("failed") or [],
                  "attempts": len(t.get("gate_history") or [])}),
        "budget": bool(t.get("budget_exhausted")), "declared": t.get("harness_declared") or "",
        "answer": _sbs_clip(t.get("answer") or "not stored", 3000),
        "user": _sbs_clip(user or (t.get("request") or {}).get("text") or "not stored", 2500),
        "sys_hash": t.get("system_prompt_hash") or "",
    }


def _sbs_lines(t: Dict[str, Any]) -> str:
    """One log line per thing that happened, tagged the way the power-flow page tags them."""
    out: List[str] = []

    def ln(kind: str, summary: str, full: str = "") -> None:
        out.append(f"<div class='gln' data-full=\"{E(full or summary)}\"><span class='gk {kind}'>{kind}</span>"
                   f"<span class='gs'>{E(summary)}</span></div>")

    # the deterministic row and Plan-and-Act both commit to everything before seeing a result
    planning = t.get("method") in ("plan_act_nogate", "rule_based")
    for i, st in enumerate(t["steps"]):
        kind = "plan" if (planning and i == 0) else "model"
        if st["say"]:
            ln(kind, st["say"].replace("\n", " ")[:400], st["say"])
        elif st["tools"]:
            ln(kind, (("the fixed policy, as tool calls" if t.get("method") == "rule_based" else "the whole plan, as tool calls")
                      if kind == "plan" else f"no words, called {len(st['tools'])} tool(s)"),
               "The model returned tool calls and no text.")
        for x in st["tools"]:
            call = f"{x['name']}({x['args']})"
            ln("solver", f"{call} → {x['says']}", f"{call}\n\n{x['raw']}")
    attempts = t.get("attempts") or []
    for j, a in enumerate(attempts):
        ln("gate", (f"attempt {a['n']}: " + ("passed all seven conditions" if a["passed"]
                                             else "failed on " + ", ".join(a["failed"]))),
           "The harness re-ran the power flow on the final network and checked the answer against it.\n"
           + ("passed" if a["passed"] else "failed: " + ", ".join(a["failed"])))
        if not a["passed"] and j + 1 < len(attempts):
            ln("retry", "sent back to the model with what failed, one retry inside the same budget",
               "The gate returns its verdict to the model and asks for a corrected answer. "
               "The retry spends a call from the same budget the ungated rows have.")
    if not attempts and t["gate"]:
        g = t["gate"]
        ln("gate", "passed all seven conditions" if g["passed"] else "failed on " + ", ".join(g["failed"]))
    if t["budget"]:
        ln("status", "tool or model budget exhausted")
    if t["declared"]:
        ln("status", "the harness wrote the answer: " + t["declared"])
    ln("final", (t["answer"].replace("\n", " ")[:400] or "no answer"), t["answer"])
    return "".join(out)


def side_by_side() -> str:
    tag, dirs = _sbs_runs()
    if not dirs:
        return card("The same fault under each method, step by step",
                    "<p class='muted'>No run yet. This section fills itself from the trace files as soon as one exists.</p>")
    data: Dict[str, Dict[str, Dict[str, Any]]] = {}
    labels: Dict[str, List[List[str]]] = {}
    for d in dirs:
        case, method = d.parts[-4], d.name.split("__")[0]
        rows = read_summary(d)
        if not rows:
            continue
        wanted = labels.get(case)
        if wanted is None:
            picked = _sbs_pick(rows)
            labels[case] = [[r["request_id"], f"{r['scenario_id']}-v{r['variant']} · {r['category']}"]
                            for r in rows if r["request_id"] in picked]
            wanted = labels[case]
        for rid, _lab in wanted:
            row = next((r for r in rows if r["request_id"] == rid), None)
            if not row:
                continue
            tr = _sbs_trace(d, row)
            if tr:
                tr["method"] = method
                data.setdefault(case, {}).setdefault(rid, {})[method] = tr
    if not data:
        return card("The same fault under each method, step by step",
                    "<p class='muted'>The runs exist but stored no traces.</p>")

    cases = sorted(data, key=lambda c: int(c.replace("ieee", "")))
    blocks: List[str] = []
    for case in cases:
        for rid, per in data[case].items():
            cols = []
            for r in ROWS:
                t = per.get(r["name"])
                if not t:
                    cols.append(f"<div class='gcol'><h4>{E(r['label'])}</h4>"
                                "<div class='gmeta'>no stored trace for this scenario</div></div>")
                    continue
                verdict_cls = {"solved": "ok", "escalated": "esc"}.get(t["outcome"], "bad")
                cols.append(
                    f"<div class='gcol'><h4>{E(r['label'])} <span class='tag {verdict_cls}'>{E(t['outcome'].replace('_', ' '))}</span></h4>"
                    f"<details class='gpr'><summary>prompt sent to this method for this scenario</summary>"
                    f"<div class='gprb'><pre>{E(t['user'])}</pre>"
                    + (f"<p class='muted'>system prompt hash {E(t['sys_hash'])}, shown in full in the Prompts tab</p>" if t["sys_hash"]
                       else "<p class='muted'>no system prompt: this method uses no language model</p>")
                    + "</div></details>"
                    f"<div class='gmeta'><b>{len(t['steps'])}</b> steps · <b>{t['llm_calls'] or 0}</b> model calls · "
                    f"<b>{t['tool_calls'] or 0}</b> tool calls · {t['tokens']} tokens · {t['seconds']} s<br>"
                    f"final network: {E(t['final'])}"
                    + (f" · <b>load stranded on {E(t['islanded'])}</b>" if t["islanded"] else "") + "</div>"
                    f"<div class='glog'>{_sbs_lines(t)}</div></div>")
            blocks.append(f"<div class='gex' data-case='{E(case)}' data-scn='{E(rid)}'><div class='gcols'>{''.join(cols)}</div></div>")

    sysopts = "".join(f"<option value='{E(c)}'>{E(NETWORK_LABELS.get('case' + c.replace('ieee', ''), c))}</option>" for c in cases)
    which = "the run set of the paper" if not tag else f"run set <code>{E(tag)}</code>"
    return card(
        "The same fault under each method, step by step",
        f"<p>Real runs, not scored here: {which}, {SBS_PER_NETWORK} of the twenty scenarios per system, every method, on "
        "the model each run used. Each column is the log of what the method said, what it called and what the solver "
        "returned; click a line to expand it, and open the prompt it received. The verdicts of these runs are on the "
        "results pages, where scores belong.</p>"
        "<style>"
        ".gctl{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:10px 0 12px;font-size:12.5px;color:#64748b}"
        ".gctl select{font:inherit;font-size:13px;padding:3px 7px;border:1px solid #e3e7ee;border-radius:8px;background:#fff;color:#0f172a}"
        ".gex{display:none}.gex.on{display:block}"
        ".gcols{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;align-items:start;overflow-x:auto}"
        "@media(max-width:1200px){.gcols{grid-auto-flow:column;grid-auto-columns:minmax(300px,1fr);grid-template-columns:none}}"
        ".gcol{background:#fff;border:1px solid #e3e7ee;border-radius:10px;min-width:0;overflow:hidden}"
        ".gcol>h4{margin:0;padding:8px 10px;font-size:12.5px;border-bottom:1px solid #e3e7ee;background:#f8fafc}"
        ".gmeta{padding:6px 10px;font-size:11px;color:#64748b;border-bottom:1px solid #e3e7ee}.gmeta b{color:#0f172a}"
        ".gpr{border-bottom:1px solid #e3e7ee}.gpr>summary{padding:6px 10px;font-size:11px;color:#2f5fd0;cursor:pointer}"
        ".gprb{padding:0 10px 8px}.gprb pre{white-space:pre-wrap;word-break:break-word;background:#f8fafc;border:1px solid #e3e7ee;"
        "border-radius:7px;padding:8px 10px;font-size:11px;margin:0 0 6px;max-height:240px;overflow:auto}"
        ".glog{font:11.5px/1.4 'JetBrains Mono',ui-monospace,Menlo,monospace;max-height:60vh;overflow:auto}"
        ".gln{display:grid;grid-template-columns:44px 1fr;gap:6px;padding:4px 8px;border-bottom:1px solid #f0f2f5;cursor:pointer}"
        ".gln:hover{background:#f8fafc}.gk{font-weight:600;font-size:10.5px}"
        ".gk.model{color:#2f5fd0}.gk.solver{color:#0f8f84}.gk.plan{color:#6d4fc4}.gk.gate{color:#c99a06}"
        ".gk.retry{color:#b45309}.gk.final{color:#2f5fd0}.gk.status{color:#64748b}"
        ".gs{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
        ".gln.open .gs{white-space:pre-wrap;overflow:visible;word-break:break-word}"
        "</style>"
        "<div class='gctl'><label>System <select id='gsys'>" + sysopts + "</select></label>"
        "<label>Scenario <select id='gscn'></select></label>"
        "<span class='muted'>every line is tagged: plan, model, solver, gate, retry, status, final.</span></div>"
        + "".join(blocks)
        + "<script>window.GEX=" + json.dumps(labels, ensure_ascii=False) + ";</script>")


def tab_scenarios() -> str:
    from evaluation import scenarios as S

    m = manifest()
    if not m:
        return card("Scenarios", "<p class='muted'>No manifest frozen yet: run <code>run.py freeze-scenarios</code>.</p>")
    ent = m["entries"]
    shown = [n for n in ALL_NETWORKS if any(e["network"] == n for e in ent.values())]
    head = (["#", "scenario", "category", "injected fault"]
            + [NETWORK_LABELS[n] + ("" if n in NETWORKS else " <span class='muted'>(not in the plan yet)</span>") for n in shown])
    rows = []
    for i, (sid, v) in enumerate(S.INSTANCES, 1):
        nvar = S.VARIANTS_OF[sid]
        name = f"<code>{E(sid)}</code>" + (f"<span class='muted'> · v{v}</span>" if nvar > 1 else "")
        cells = [f"<b>{i}</b>", f"{name}<div class='muted'>{E(S.LABEL_OF[sid])}</div>", E(S.CATEGORY_OF[sid]), E(S.FAULT_TYPE_OF[sid])]
        for n in shown:
            e = ent.get(S.instance_id(n, sid, v))
            if e is None:
                cells.append("<span class='muted'>—</span>")
                continue
            st = e["initial_state"]
            k = {"not_converged": "bad", "islanded_load": "warn", "violations": "warn", "secure": "ok"}[st]
            extra = "" if e["initial_n_new_violations"] is None else f" {e['initial_n_new_violations']} new"
            comps = ", ".join(f"{t} {x[:3]}{'…' if len(x) > 3 else ''}" for t, x in e["injected"]["components"].items())
            cells.append(chip(st.replace("_", " ") + extra, k) + f"<div class='muted'>{E(comps)}</div>")
        rows.append(cells)
    base = {n: len(ent[S.instance_id(n, "normal_operation", 0)]["base_violations"]) for n in shown
            if S.instance_id(n, "normal_operation", 0) in ent}
    by_cat: Dict[str, int] = {}
    for sid, _v in S.INSTANCES:
        by_cat[S.CATEGORY_OF[sid]] = by_cat.get(S.CATEGORY_OF[sid], 0) + 1

    body = [
        card(
            f"{S.N_INSTANCES} scenarios per network, built from {len(S.SCENARIOS)} fault classes",
            f"<p><b>A run poses {S.N_INSTANCES} scenarios on each network, and every method answers the same "
            f"{S.N_INSTANCES}.</b> They come from thirteen fault classes, the taxonomy of the submitted paper. "
            f"Six classes are posed once, because they perturb the whole network and there is only one way to do it; "
            f"seven can place their fault at different points and are posed twice, at two different points. "
            f"6 × 1 + 7 × 2 = {S.N_INSTANCES}. By failure mode: "
            + ", ".join(f"{k} {c}" for k, c in sorted(by_cat.items(), key=lambda kv: -kv[1]))
            + ".</p>"
            "<p>Two things were fixed with respect to the submitted set. The two contingency classes now take the worst N-1 "
            "element out of service, where they used to run the analysis and leave the network untouched; and every scenario "
            "carries two labels, the category the generator set out to cause and the state the solver measured on the injected "
            f"network relative to the base. Frozen on {E(str(m.get('frozen_at_utc'))[:10])} with pandapower {E(m.get('pandapower'))}; "
            "each injected network has a content hash and a run refuses to start on a scenario whose hash changed.</p>",
            table(head, rows),
            "<p class='muted'>Base networks already violate the band at: "
            + ", ".join(f"{NETWORK_LABELS[n]} {k}" for n, k in base.items())
            + " element(s). Those never count against a method.</p>",
        ),
        card(
            "What a variant changes, and what it never changes",
            "<p>Posing a class twice moves the fault, it does not make it harder. Each class ranks the places it could "
            "strike, by base loading, by hop distance from the slack bus, or by how bad the outage is, and takes the first "
            "or the second. The two scenarios of one class are therefore the same kind of fault at two different points, "
            "which is what separates a method that handles line outages from one that memorized a line.</p>",
            table(
                ["class", "scenarios", "what the second one moves"],
                [[f"<code>{E(sid)}</code>", str(S.VARIANTS_OF[sid]),
                  E(S.VARIES_BY[sid]) if sid in S.VARIES_BY
                  else f"<span class='muted'>{E(S.POSED_ONCE.get(sid, 'posed once'))}</span>"]
                 for sid, _v in S.INSTANCES if _v == 0],
                escape=False,
            ),
            note("The ranking is a property of the network, so the second scenario of a class means the same thing on every "
                 "system: the second worst place for that fault. Nothing is drawn at random and no seed is stored; the same "
                 "code on the same pandapower version produces the same twenty scenarios, which is what the content hashes "
                 "pin. In the results they are told apart by the suffix <code>v0</code> and <code>v1</code>.", "info"),
        ),
        card(
            "Where a stress set would go",
            "<p>The other case studies add a set of requests built to be unanswerable, so the escalation column measures "
            "something on ordinary days. Here the ordinary set already contains scenarios no method can make secure with the "
            "catalogue, a line with near-zero impedance cannot be restored by any action in it, so the escalation column has "
            "content without a separate set. A stress set is not planned.</p>"),
    ]
    return "".join(body)


BLOCKS: Dict[str, Tuple[str, str, str]] = {
    "sys_agent": ("#2f5fd0", "system · agent role and workflow", "methods/_shared/agent_system_prompt.txt"),
    "sys_llm": ("#2f5fd0", "system · role, no tools", "methods/_shared/llm_only_system_prompt.txt"),
    "sys_plan": ("#6d4fc4", "system · planner", "methods/plan_act_nogate/plan_system_prompt.txt"),
    "rules": ("#6d4fc4", "system · shared rules", "methods/_shared/common_rules.txt"),
    "contract": ("#0f8f84", "system · answer contract", "methods/_shared/output_contract.txt"),
    "u_req": ("#c99a06", "user · the request", "evaluation/requests.py::request_text"),
    "u_evid": ("#c99a06", "user · evidence block (system data)", "solver/evidence.py::EvidenceReport.to_text + base violations"),
    "u_cat": ("#0f8f84", "user · action catalogue as text", "solver/tools.py::catalogue_text"),
    "u_reason": ("#c0392b", "user · reasoning instructions", "methods/llm_only_cot/reasoning_section.txt"),
    "tools": ("#0f8f84", "tool schemas (function calling)", "solver/tools.py::openai_schemas"),
    "retry": ("#d53f3f", "user · gate verdict on the retry", "methods/_shared/gate_retry_instruction.txt + gate.verdict_text"),
}


def _block(kind: str, text: str, collapse: bool = False) -> str:
    color, label, src = BLOCKS[kind]
    if collapse and len(text) > 1500:
        return prompt_block(label, f"<details><summary>show the {len(text):,} characters</summary><pre>{E(text)}</pre></details>", color=color, source=src, pre=False)
    return prompt_block(label, text, color=color, source=src)


def tab_prompts() -> str:
    from solver.tools import catalogue_text, openai_schemas

    req = sample_request()
    legend = " ".join(f"<span class='chip' style=\"background:{c};color:#fff\">{E(l)}</span>" for c, l, _ in BLOCKS.values())
    mth_options = "".join(f"<option value='{E(c['folder'])}'{' selected' if c['folder'] == 'griddebug' else ''}>{E(c['folder'])}</option>" for c in methods.cards())
    body = [card("What the model receives, block by block",
                 "<p>Shown on one scenario, the IEEE-14 line contingency. Pick a method. Every fixed sentence is a file under <code>methods/</code>; "
                 "the blocks built at run time (the request, the evidence, the catalogue) say which function produces them. The system prompt's hash "
                 "is stamped on every run's config.</p>"
                 f"<div style='margin:8px 0'>{legend}</div>"
                 f"<div style='margin-top:10px'><label>Method <select id='mth'>{mth_options}</select></label></div>")]
    for c in methods.cards():
        name = c["folder"]
        inner = [f"<h2>{E(name)} <span class='muted'>runner: {E(c['runner_name'])}</span></h2>", f"<p class='muted'>{E(c['description'])}</p>"]
        if c["kind"] == "deterministic":
            inner.append("<p>No language model, so no prompt. The rule engine reads the evidence and the policy calls the tools directly.</p>")
        else:
            if c["kind"] == "llm_only":
                inner += ["<h3>System prompt</h3>", _block("sys_llm", methods.read_text("_shared/llm_only_system_prompt.txt"))]
            elif c.get("architecture") == "plan_act":
                inner += ["<h3>Planner system prompt (first call)</h3>", _block("sys_plan", methods.read_text("plan_act_nogate/plan_system_prompt.txt")),
                          _block("rules", methods.read_text("_shared/common_rules.txt")), _block("u_cat", catalogue_text(), collapse=True),
                          "<h3>Answer system prompt (second call)</h3>", _block("sys_agent", methods.read_text("_shared/agent_system_prompt.txt"))]
            else:
                inner += ["<h3>System prompt</h3>", _block("sys_agent", methods.read_text("_shared/agent_system_prompt.txt"))]
            inner += [_block("rules", methods.read_text("_shared/common_rules.txt")), _block("contract", methods.read_text("_shared/output_contract.txt"))]
            inner += ["<h3>User message</h3>", _block("u_req", req.text), _block("u_evid", req.evidence_text, collapse=True)]
            if c["kind"] == "llm_only":
                inner.append(_block("u_cat", catalogue_text(), collapse=True))
                if c.get("strategy") == "cot":
                    inner.append(_block("u_reason", methods.read_text("llm_only_cot/reasoning_section.txt")))
            else:
                inner.append(_block("tools", json.dumps(openai_schemas(), indent=1), collapse=True))
            if c.get("gate"):
                inner.append(_block("retry", methods.read_text("_shared/gate_retry_instruction.txt") + "\n\n<the failed conditions and the solver state, from methods/agent/gate.py::verdict_text>"))
        body.append(f"<div class='card pm' data-mth='{E(name)}'>" + "".join(inner) + "</div>")
    return "".join(body)


def tab_tools() -> str:
    from solver.tools import CATALOGUE, KINDS, REQUIRED

    rows = []
    for t in CATALOGUE:
        params = ", ".join(f"{k}" + ("*" if k in REQUIRED.get(t["name"], []) else "") for k in t.get("parameters", {}))
        rows.append([f"<code>{E(t['name'])}</code>", E(KINDS[t["name"]]), E(params or "—"), E(t["description"])])
    return "".join([
        card("One catalogue, identical for every method that has tools",
             f"<p>{len(CATALOGUE)} tools in four kinds, one dispatcher, one log. The three agent methods receive these exact schemas; the two prompting "
             "methods receive the same catalogue rendered as text, so what a method may do is never a difference between rows. The dispatcher counts "
             "every call against the budget, refuses calls past it, and records position, arguments and output, which is what the gate reads.</p>",
             table(["tool", "kind", "arguments (* required)", "what it does"], rows),
             note("The check tools mark every violation <code>in_base</code> when the unmodified network already had it, and return the count of new "
                  "ones, so a method never has to reconstruct the floor by hand.", "info")),
        card("The solver behind it",
             "<p>pandapower's Newton-Raphson AC power flow on the IEEE 14, 30 and 57-bus cases, with the line-rating rule of the power-flow case "
             "study. The harness runs the same solver on the final network to score: a method's own <code>run_power_flow</code> is evidence for the "
             "method, never the source of a verdict.</p>"),
    ])


def tab_gate() -> str:
    from methods.agent import gate as G

    rows = [[f"<b>{E(G.CONDITION_LABELS[k])}</b>", f"<code>{E(k)}</code>", E(G.CONDITION_DESCRIPTIONS[k])] for k in G.CONDITION_ORDER]
    last = ""
    crow = []
    for c in COLUMNS:
        grp = "" if c["group"] == last else f"<b>{E(c['group'])}</b>"
        last = c["group"]
        crow.append([f"<span class='muted'>{grp}</span>", f"<b>{E(c['name'])}</b>", E(c["what"]), f"<span class='muted'>{E(c['why'])}</span>"])
    return "".join([
        card("The verification gate",
             "<p>Six conditions on the final answer, evaluated from the agent's own evidence: the network it left behind, its tool log, the text it "
             "wrote. It never sees the injected fault or a reference repair. When one fails the verdict goes back to the model once, inside the same "
             "budget; if the second attempt fails too, the harness replaces the answer with a declared failure that claims no repair and carries no "
             "unsupported number, and the scenario counts as escalated.</p>",
             table(["", "condition", "what it checks"], rows),
             f"<p class='muted'>Attempts before a declared failure: {G.MAX_VERIFICATION_ATTEMPTS}.</p>"),
        card("What the gate catches and what it cannot",
             "<div class='grid g2'><div><h3>It catches</h3><ul><li>a repair claimed while the solver's final network still violates a limit or does not converge</li>"
             "<li>a load left on an islanded bus</li><li>an action taken after the last power flow, so the reported numbers are stale</li>"
             "<li>a number that appears in no tool output</li><li>a final_state that contradicts the solver</li>"
             "<li>an action claimed that errored, and an action taken and not reported</li></ul></div>"
             "<div><h3>It cannot catch</h3><ul><li>a wrong diagnosis. A network can be made secure by curtailing loads without ever naming the line that "
             "was lost; the gate passes it and the diagnosis column says the fault was not understood.</li>"
             "<li>a repair that is secure but crude. Shedding every load is secure, and the smoke test showed a method doing exactly that. "
             "How much load a repair may shed is an operator's judgement, not a threshold a harness can set, so it is reported as the "
             "<b>Load served</b> column beside Repaired rather than gated, the same way the EV case study puts undelivered energy beside "
             "the cost gap.</li></ul></div></div>",
             note("That is why diagnosis is a column of its own and never a term of Solved: the gate measures whether the report is true, the diagnosis "
                  "column whether the fault was understood.", "warn")),
        card("Where a scenario ends up",
             "<p>Three exclusive outcomes, adding to 100 %.</p>",
             table(["outcome", "definition"], [
                 [verdict("solved"), "the harness's power flow on the final network is secure, the answer claims a repair, every number traces to a tool output or the evidence, and final_state agrees with the solver"],
                 [verdict("escalated"), "the answer declares not_repaired or cannot_repair and lists what remains, or the budget ran out, or the gate rejected two attempts. Takes precedence"],
                 [verdict("wrong"), "a repair claim the solver contradicts, an unsupported number, or no answer with the contract, presented as valid"]])),
        card("The columns", "<p>Three groups, the same three in every case study.</p>", table(["group", "column", "what it measures", "why it is there"], crow)),
        card(
            "How the Diagnosis column is scored",
            "<p>Against the injected fault, never against the symptom. A load scaled by twenty times is "
            "<code>load_increase</code> on the loads, not <code>nonconvergence</code>; a line outage is the line that was "
            "switched out, not the lines that overloaded because of it. An answer is exact when its <code>fault_type</code> "
            "matches the injected one and it names at least one injected component; the normal case needs only the type.</p>",
            table(["injected fault type", "the classes that inject it"],
                  [[f"<code>{E(ft)}</code>", E(", ".join(sid for sid, f in _FAULT_TYPE_OF().items() if f == ft))]
                   for ft in _FAULT_TYPES() if any(f == ft for f in _FAULT_TYPE_OF().values())]),
            note("Diagnosis is scored on every scenario and is deliberately not a term of Solved. A network can be made "
                 "secure by curtailing loads without ever naming the line that was lost: the gate passes that answer and this "
                 "column says the fault was not understood.", "warn"),
        ),
    ])


def _FAULT_TYPES():
    from evaluation.scenarios import FAULT_TYPES

    return FAULT_TYPES


def _FAULT_TYPE_OF():
    from evaluation.scenarios import FAULT_TYPE_OF

    return FAULT_TYPE_OF


def tab_plan() -> str:
    from config import load_pricing, parse_model_spec
    from evaluation.runner import estimate
    from evaluation.scenarios import N_INSTANCES

    ALL = ALL_NETWORKS
    pricing = load_pricing()
    rows, cost = [], {}
    for spec_s in ("openrouter:openai/gpt-4o-mini", "openrouter:openai/gpt-5.6-sol"):
        spec = parse_model_spec(spec_s)
        per_net, tot, tot3 = [], 0.0, 0.0
        for n in ALL:
            v = sum((estimate(m, n, spec, N_INSTANCES, pricing) or 0.0) for m in methods.ORDER)
            per_net.append(f"{v:.2f}")
            cost[(spec.short, n)] = v
            tot += v
            if n in NETWORKS:
                tot3 += v
        cost[(spec.short, "three")] = tot3
        cost[(spec.short, "five")] = tot
        rows.append([f"<code>{E(spec.short)}</code>"] + per_net + [f"{tot3:.2f}", f"<b>{tot:.2f}</b>"])
    return "".join([
        card("Phases",
             table(["phase", "what", "estimated cost", "state"], [
                 ["0", "layout, twenty scenarios frozen on five systems, pages, tests without a key", "0", chip("done", "ok")],
                 ["smoke", "3 scenarios × IEEE-14 × 6 methods, gpt-4o-mini", "0.09 USD measured", chip("done 2026-09-27", "ok")],
                 ["1", f"{N_INSTANCES} scenarios × 6 methods, gpt-4o-mini, on the systems Daniela picks",
                  f"{cost[('gpt-4o-mini', 'three')]:.2f} USD on the three of the paper, {cost[('gpt-4o-mini', 'five')]:.2f} on all five",
                  chip("awaiting her go", "warn")],
                 ["2", "gpt-5.6-sol, IEEE-14 first, more only with a top-up",
                  f"{cost[('gpt-5.6-sol', 'case14')]:.2f} USD for IEEE-14 alone", chip("after phase 1", "warn")]])),
        card(f"Cost estimate per model, {N_INSTANCES} scenarios × 6 methods per network",
             "<p>Scaled from the smoke test, which measured 0.09 USD for three IEEE-14 scenarios across the six methods. The "
             "two loop rows carry almost all of it: a growing conversation over about fifteen model calls, and the tool "
             "outputs grow with the network. <code>run.py run --dry-run</code> prints the same estimate for any selection.</p>",
             table(["model"] + [NETWORK_LABELS[n] for n in ALL] + ["14+30+57", "all five"], rows),
             note("The three systems of the submitted paper are IEEE-14, 30 and 57. IEEE-118 and IEEE-300 are the sizes R4.4 "
                  "calls realistic and the ones the power-flow case study runs; all twenty scenarios build on them, and adding "
                  "them costs about 3.9 USD more on the small model. Which systems the paper table carries is still open.", "info")),
        card("Budget per scenario", kv([("model calls", str(MAX_LLM_CALLS)), ("tool calls", str(MAX_TOOL_CALLS)), ("wall clock", f"{SCENARIO_TIMEOUT_S:.0f} s"),
                                        ("temperature", "0"), ("retry after the gate", "1, inside the same budget")])),
    ])


def tab_results() -> str:
    dirs = method_dirs()
    if not dirs:
        return card("No runs yet", "<p>No results folder carries a summary.json. The first run is the smoke test, after Daniela's go.</p>")
    newest = dirs[0].parts[-3]
    latest = [d for d in dirs if d.parts[-3] == newest]
    body = []
    by_net: Dict[str, Dict[str, Tuple[Path, List[Dict[str, str]], Dict[str, Any]]]] = {}
    for d in latest:
        h = read_header(d)
        by_net.setdefault(h["header"]["case"], {})[h["header"]["method"]] = (d, read_summary(d), h)

    def pct(rows: List[Dict[str, str]], kind: str) -> str:
        k = sum(1 for r in rows if r.get("outcome") == kind)
        return f"{100.0 * k / len(rows):.0f} % <span class='muted'>({k}/{len(rows)})</span>" if rows else "-"

    for net_name, per in by_net.items():
        split = []
        for row in ROWS:
            if row["name"] in per:
                d, rows, h = per[row["name"]]
                a = h["aggregate"]
                split.append([f"<b>{E(row['label'])}</b>", str(len(rows)), pct(rows, "solved"), pct(rows, "escalated"), pct(rows, "wrong_unflagged"),
                              f"{a.get('form')} %", f"{a.get('repaired')}/{len(rows)}", f"{a.get('trace')} %", f"{a.get('tokens')}", f"{a.get('cost')}"])
            else:
                split.append([f"<b>{E(row['label'])}</b>", "<span class='muted'>not run</span>"] + [""] * 8)
        body.append(card(f"{NETWORK_LABELS.get(net_name, net_name)} · run of {E(newest)}",
                         table(["method", "n", verdict("solved"), verdict("escalated"), verdict("wrong"), "diagnosis", "repaired", "traceable", "tokens", "cost $"], split)))
    det = []
    cols = [("nn", "nn"), ("scenario_id", "scenario"), ("initial_state", "initial"), ("outcome", "outcome"), ("solved_reason", "why"), ("formulation_exact", "diag."),
            ("final_secure", "secure"), ("final_n_new", "new viol."), ("gate_pass", "gate"), ("n_actions", "actions"), ("n_llm_calls", "llm"), ("n_tool_calls", "tools"), ("cost_usd", "cost $")]
    for d in latest:
        rows = read_summary(d)
        det.append(f"<details><summary>{E(d.parts[-4])} / {E(d.parts[-2])} / {E(d.name)} — every scenario</summary>"
                   + table([l for _k, l in cols], [[verdict(r["outcome"]) if k == "outcome" else E(r.get(k, "")) for k, _l in cols] for r in rows]) + "</details>")
    body.append(card("Scenario by scenario", *det))
    return "".join(body)


def tab_traces() -> str:
    dirs = method_dirs()
    if not dirs:
        return card("Traces", "<p class='muted'>No run yet. Every run leaves <code>traces/NN_&lt;request-id&gt;.narrative.txt</code> and "
                              "<code>.transcript.txt</code> next to its rows; this section shows them once they exist.</p>")
    newest = dirs[0].parts[-3]
    body = [card("Every run end to end", "<p>The narrative of each scenario of the newest run set, as written by evaluation/postprocess.py from the "
                                          "trace: what the method did, the diagnosis verdict, the harness's state, the reporting checks, the outcome. "
                                          "The transcript next to it in the results folder is the raw exchange.</p>")]
    for d in [x for x in dirs if x.parts[-3] == newest]:
        items = []
        for p in sorted((d / "traces").glob("*.narrative.txt")):
            items.append(f"<details><summary><code>{E(p.name)}</code></summary><pre>{E(p.read_text(encoding='utf-8'))}</pre></details>")
        body.append(card(f"{E(d.parts[-4])} / {E(d.parts[-2])} / {E(d.name)}", *items))
    return "".join(body)


def tab_analysis() -> str:
    from visuals.shell import markdown

    dirs = [d for d in method_dirs() if (d / "REPORT.md").exists()]
    if not dirs:
        return card("Analysis", "<p class='muted'>No results folder carries a REPORT.md yet.</p>"
                                "<p>Every run ends with one per method, written by <code>evaluation/postprocess.py</code> from the rows. No model is called to write it.</p>")
    newest = dirs[0].parts[-3]
    body = [card("What the reports are", "<p>Each method folder ends with a REPORT.md written from its rows: the outcome split, the metrics by group, "
                                          "the split by category and by measured initial state, the wrong and escalated lists, every scenario on one line.</p>")]
    for d in [x for x in dirs if x.parts[-3] == newest]:
        body.append(f"<div class='card'><h2><code>{E(str(d.relative_to(PROJECT_ROOT / 'results')))}</code></h2>" + markdown((d / "REPORT.md").read_text(encoding="utf-8")) + "</div>")
    return "".join(body)


def tab_status() -> str:
    rows = [[f"<b>{E(r['label'])}</b>", f"<code>{E(r['name'])}</code>", chip("implemented, tested with a scripted model", "ok") if methods.card(r["name"]).get("implemented") else chip("to be written", "warn")] for r in ROWS]
    models = sorted({d.parts[-2] for d in method_dirs() if d.parts[-2] != "no-llm"})
    return card("Where the implementation stands",
                f"<p>All six methods run today; every one of them has an end-to-end test with a scripted model and no API key. "
                f"Runs made so far with a model: {E(', '.join(models) if models else 'none')}.</p>",
                table(["method", "name", "state"], rows),
                "<p class='muted'>Not part of the evaluation: the FastAPI and Next.js demo under <code>ui/</code> predates this layout and is not "
                "wired to the six methods; it is kept as it was.</p>")


GROUPS = (("Design", (("home", "Home"), ("methods", "Methods"), ("scenarios", "Scenarios"), ("prompts", "Prompts"), ("tools", "Tools"), ("gate", "Gate & scoring"), ("plan", "Run plan"))),
          ("Results", (("results", "Results"), ("traces", "Traces"), ("analysis", "Analysis"), ("status", "Implementation"))))
BUILDERS = {"home": tab_home, "methods": tab_methods, "scenarios": tab_scenarios, "prompts": tab_prompts, "tools": tab_tools, "gate": tab_gate,
            "plan": tab_plan, "results": tab_results, "traces": tab_traces, "analysis": tab_analysis, "status": tab_status}

SCRIPT = """
(function(){
  var mth=document.getElementById('mth');
  if(mth){ var apply=function(){ document.querySelectorAll('.pm').forEach(function(p){ p.style.display = p.dataset.mth===mth.value ? '' : 'none'; }); };
    mth.onchange=apply; apply(); }
})();
(function(){
  var L=window.GEX; if(!L) return;
  var sys=document.getElementById('gsys'), scn=document.getElementById('gscn');
  if(!sys||!scn) return;
  var esc=function(t){return String(t==null?'':t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');};
  function fill(){ var l=L[sys.value]||[];
    scn.innerHTML=l.map(function(p){return '<option value="'+esc(p[0])+'">'+esc(p[1])+'</option>';}).join(''); }
  function show(){ document.querySelectorAll('.gex').forEach(function(b){
      b.classList.toggle('on', b.dataset.case===sys.value && b.dataset.scn===scn.value); }); }
  sys.onchange=function(){fill();show();}; scn.onchange=show;
  document.addEventListener('click', function(e){ var ln=e.target.closest && e.target.closest('.gln'); if(!ln) return;
    var s2=ln.querySelector('.gs'); if(!ln.classList.contains('open')){ ln.dataset.short=s2.textContent;
      s2.textContent=ln.dataset.full; ln.classList.add('open'); }
    else { s2.textContent=ln.dataset.short; ln.classList.remove('open'); } });
  fill(); show();
})();
"""


def payload() -> Dict[str, Any]:
    m = manifest()
    n = len(m["entries"]) if m else 0
    return {
        "id": CASE_ID, "title": CASE_TITLE, "brand": "GridDebugAgent · contingency diagnosis and repair",
        "note": f"{S_N()} scenarios on each of {len(NETWORKS)} IEEE networks",
        "blurb": "Diagnose a fault injected into an IEEE test network and restore a secure operating point with control-room actions, verified by the power flow.",
        "summary": [("task", "diagnose and repair"), ("solver", "pandapower AC power flow"), ("data", f"{S_N()} frozen scenarios per network")],
        "groups": [[label, [list(e) for e in entries]] for label, entries in GROUPS],
        "tabs": {key: BUILDERS[key]() for _l, entries in GROUPS for key, _t in entries},
        "script": SCRIPT,
    }


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "results" / "visuals" / "fragments.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload()), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

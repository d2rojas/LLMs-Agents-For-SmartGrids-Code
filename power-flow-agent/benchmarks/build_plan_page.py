#!/usr/bin/env python3
"""Build results/visuals/design.html: the evaluation design as an app-like page.

Tabs: Overview, Methods, Scenarios, Prompts, Tools, Gate & scoring, Run plan. Everything is
generated from the code that will run (methods/, llm/, benchmarks/requests.py, the dispatcher).

    .venv/bin/python benchmarks/build_plan_page.py
"""

from __future__ import annotations

import html
import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import methods  # noqa: E402
from baselines import rule_based  # noqa: E402
from benchmarks import metrics as bm, scoring as bs  # noqa: E402
from benchmarks.evaluate_llms import perturbed_case, perturbing_dispatcher  # noqa: E402
from benchmarks.requests import generate_requests  # noqa: E402
from llm.engine import LLMEngine, SessionState, verify_final_answer  # noqa: E402
from llm.prompt_variants import build_messages  # noqa: E402
from llm.tools import ToolContext, get_openai_tools  # noqa: E402

E = html.escape
CASE, N, SEED, K, ROUNDS, TOOLS = "case14", 40, 0, 1, 8, "load_split"
MODELS = ["gpt-4o-mini", "gpt-5.6-sol"]
MODEL_IDS = {"gpt-4o-mini": "openrouter:openai/gpt-4o-mini", "gpt-5.6-sol": "openrouter:openai/gpt-5.6-sol"}

# The six methods. Companion measurements hang off the prompting methods.
ROWS: List[Dict[str, Any]] = [
    {"key": "rule_based", "label": "Deterministic parser", "sub": "no LLM", "runner": "rule_based", "formulates": "fixed regex rules", "computes": "PandaPower", "sees": "—", "gate": "none",
     "story": "The conventional automation baseline: a hand-written parser maps the request to solver calls. Everything it cannot parse, it cannot do."},
    {"key": "llm_only_structured", "label": "Structured prompting", "sub": "LLM only, no tools", "runner": "llm_only:structured", "formulates": "the LLM, implicitly", "computes": "the LLM, by hand", "sees": "—", "gate": "none",
     "story": "The model gets the full case tables in the prompt and must return the power-flow numbers itself, or set converged to false if it cannot. It makes no tool calls; it declares the operations the request needs and computes the numbers itself."},
    {"key": "llm_only_cot", "label": "Chain-of-thought prompting", "sub": "LLM only, no tools", "runner": "llm_only:cot", "formulates": "the LLM, implicitly", "computes": "the LLM, by hand", "sees": "—", "gate": "none",
     "story": "Same as structured, plus a reasoning section that asks the model to think step by step before the final JSON."},
    {"key": "plan_act_nogate", "label": "Plan-and-Act", "sub": "LLM + solver", "runner": "plan_act_nogate", "formulates": "the LLM, whole plan at once", "computes": "PandaPower", "sees": "no: commits before seeing any result", "gate": "none",
     "story": "One planning call writes the complete list of tool calls as JSON; the executor runs them; the LLM writes the answer from the outputs."},
    {"key": "react_nogate", "label": "ReAct", "sub": "LLM + solver", "runner": "react_nogate", "formulates": "the LLM, one call at a time", "computes": "PandaPower", "sees": "yes, up to 8 rounds", "gate": "none",
     "story": "Thought, tool call, observation, repeat. The model sees every solver output before deciding the next call."},
    {"key": "pfagent", "label": "PFAgent", "sub": "ReAct + verification gate", "runner": "pfagent", "formulates": "the LLM, one call at a time", "computes": "PandaPower", "sees": "yes, up to 8 rounds", "gate": "final answer, V1–V7",
     "story": "ReAct, plus a gate on the final answer: numbers must come from the last solve of a converged, connected network and every argument must trace to the request. A rejected answer is retried once, then escalated."},
]
# estimated cost per method and model for 40 requests, USD (gpt-4o-mini, gpt-5.6-sol): the cost_usd_total
# recorded in summary.json of the 2026-09-21/23 runs, rounded up. On sol the prompting rows are the expensive
# ones (about 8,000 reasoning tokens per answer); the agents mostly pay for prompt tokens.
COST = {"rule_based": (0, 0), "llm_only:structured": (0.03, 3.6), "llm_only:cot": (0.05, 3.5), "plan_act_nogate": (0.05, 0.7), "react_nogate": (0.1, 1.3), "pfagent": (0.1, 1.7)}
BALANCE_USD = 16.64  # OpenRouter credit on 2026-09-25
RUN_PLAN = [  # (runner, models, why it has to run again)
    ("rule_based", [], "free, no LLM; fills the shared answer object from the solver outputs"),
    ("llm_only:structured", MODELS, "prompt changed: shared rules, operations catalogue and the shared answer object"),
    ("llm_only:cot", MODELS, "same prompt change, plus the reasoning section"),
    ("plan_act_nogate", MODELS, "planner catalogue and tool schema now explain the N-1 arguments; shared answer object"),
    ("react_nogate", MODELS, "tool schema now explains the N-1 arguments; shared answer object; messages stored"),
    ("pfagent", MODELS, "same as ReAct, plus V6 now covers max_candidates"),
]

# prompt building blocks: (id, color, label, where it comes from)
BLOCKS = {
    "sys_base": ("#2f5fd0", "system · role and rules", "methods/_shared/llm_only_system_prompt.txt"),
    "sys_agent": ("#2f5fd0", "system · agent role, tools, rules, reply format", "methods/_shared/agent_system_prompt.txt"),
    "sys_forced": ("#d53f3f", "system · forced clause (abstention removed)", "methods/llm_only_forced_structured/forced_replacement.txt"),
    "sys_cot": ("#6d4fc4", "system · reasoning-mode suffix", "methods/_shared/cot_system_suffix.txt"),
    "sys_probe": ("#0f8f84", "system · probe role (declare, do not compute)", "methods/_shared/formulation_probe_system_prompt.txt"),
    "u_role": ("#64748b", "user · role line", "methods/_shared/llm_only_user_template.txt"),
    "u_data": ("#e0891a", "user · system data: the case tables", "rendered from the perturbed case (baselines/llm_only.py)"),
    "u_task": ("#1f9d55", "user · task: the request", "benchmarks/requests.py"),
    "u_reason": ("#6d4fc4", "user · reasoning instructions", "methods/llm_only_cot/reasoning_section.txt"),
    "u_form": ("#0f8f84", "user · formulation: operations catalogue", "methods/_shared/formulation_probe_section.txt + llm/tools.py"),
    "u_ops": ("#0f8f84", "user · operations catalogue (for the formulation field)", "methods/_shared/operations_section.txt + llm/tools.py"),
    "u_out": ("#c99a06", "user · output requirements (JSON schema)", "methods/_shared/llm_only_user_template.txt"),
    "u_out_probe": ("#c99a06", "user · output requirements (formulation only)", "methods/_shared/formulation_probe_output_section.txt"),
    "u_request": ("#1f9d55", "user · the request, verbatim", "benchmarks/requests.py"),
    "planner": ("#6d4fc4", "planner system prompt (plan step only)", "methods/plan_act_nogate/plan_system_prompt_prefix.txt + llm/tools.py"),
    "tools": ("#0f8f84", "tool schema (function calling)", "llm/tools.py"),
}
FIG = re.compile(r'"figure_json":\s*"((?:[^"\\]|\\.)*)"')

# existing runs used only for the examples on the Methods tab (they will be re-run under this design)
EXAMPLE_RUNS = {
    "gpt-5.6-sol": {"rule_based": "ieee14/2026-09-21/no-llm/rule_based", "llm_only:structured": "ieee14/2026-09-21/gpt-5.6-sol/llm_only_structured", "llm_only:cot": "ieee14/2026-09-21/gpt-5.6-sol/llm_only_cot", "plan_act_nogate": "ieee14/2026-09-23/gpt-5.6-sol/plan_act_nogate__matched", "react_nogate": "ieee14/2026-09-21/gpt-5.6-sol/react_nogate", "pfagent": "ieee14/2026-09-21/gpt-5.6-sol/pfagent"},
    "gpt-4o-mini": {"rule_based": "ieee14/2026-09-21/no-llm/rule_based", "llm_only:structured": "ieee14/2026-09-16/gpt-4o-mini/llm_only_structured", "llm_only:cot": "ieee14/2026-09-18/gpt-4o-mini/llm_only_cot", "plan_act_nogate": "ieee14/2026-09-23/gpt-4o-mini/plan_act_nogate__matched", "react_nogate": "ieee14/2026-09-21/gpt-4o-mini/react_nogate", "pfagent": "ieee14/2026-09-21/gpt-4o-mini/pfagent"},
}
EXAMPLE_SCENARIOS = ["case14-plain-004-s0", "case14-ambiguous-027-s0", "case14-multistep-006-s0", "case14-parameterized-009-s0"]
RESULTS = PROJECT_ROOT / "results"


def _fmt_args(a: Any) -> str:
    if isinstance(a, str):
        try:
            a = json.loads(a)
        except Exception:
            return a
    if not a:
        return "()"
    return "(" + ", ".join(f"{k}={json.dumps(v)}" for k, v in a.items()) + ")"


def _tool_short(out: str) -> str:
    try:
        o = json.loads(out)
    except Exception:
        return " ".join(out.split())[:150]
    if not isinstance(o, dict):
        return " ".join(out.split())[:150]
    bits = []
    if o.get("error"): bits.append("ERROR " + str(o["error"]))
    if "converged" in o: bits.append(f"converged={o['converged']}")
    for k, lab in (("total_load_mw", "load"), ("total_generation_mw", "gen"), ("total_loss_mw", "loss")):
        if isinstance(o.get(k), (int, float)): bits.append(f"{lab} {o[k]:.1f} MW")
    for k in ("voltage_violations", "thermal_violations"):
        if isinstance(o.get(k), list): bits.append(f"{k.split('_')[0]} viol {len(o[k])}")
    if isinstance(o.get("n1_report"), dict): bits.append(str(o["n1_report"].get("summary_text", "")))
    if o.get("summary_text") and not o.get("n1_report"): bits.append(str(o["summary_text"]))
    if o.get("message"): bits.append(str(o["message"]))
    return " · ".join(bits)[:220] or " ".join(out.split())[:150]


def example_rows(payload: Dict[str, Any], row: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    """(kind, short, full) log lines from a real trace."""
    tr = payload.get("trace") or {}
    L: List[Tuple[str, str, str]] = []
    if tr.get("plan"):
        L.append(("plan", "plan: " + " → ".join(c["tool"] + _fmt_args(c.get("args")) for c in tr["plan"]), json.dumps(tr["plan"], indent=1)))
    rounds = tr.get("rounds") or []
    for rd in rounds:
        llm = rd.get("llm") if isinstance(rd.get("llm"), dict) else None
        if llm is not None:
            calls = [tc["name"] + _fmt_args(tc.get("arguments")) for tc in llm.get("tool_calls") or []]
            u = llm.get("usage") or {}
            if rd.get("final"):
                L.append(("model", "final answer: " + " ".join(str(llm.get("content") or "").split())[:150], str(llm.get("content") or "")))
            elif calls:
                L.append(("model", "calls → " + "; ".join(calls), (llm.get("content") or "") + "\n\ntool calls:\n" + "\n".join(calls) + f"\n\n[{u.get('prompt_tokens', '?')} in / {u.get('completion_tokens', '?')} out tokens]"))
            else:
                L.append(("model", "text: " + " ".join(str(llm.get("content") or "").split())[:150], str(llm.get("content") or "")))
        for tool in rd.get("tools") or []:
            out = tool.get("output"); out = out if isinstance(out, str) else json.dumps(out)
            out = FIG.sub(lambda m: '"figure_json": "<plot omitted>"', out)
            g = "" if tool.get("gate") is None else (" [gate: pass]" if (tool["gate"].get("passed") if isinstance(tool["gate"], dict) else tool["gate"]) else " [gate: FAIL]")
            L.append(("solver", tool["name"] + _fmt_args(tool.get("arguments")) + " → " + _tool_short(out) + g, tool["name"] + _fmt_args(tool.get("arguments")) + "\n\n" + out))
    if not rounds:
        ans = str(payload.get("answer") or row.get("raw_response") or "")
        L.append(("model", "answer: " + " ".join(ans.split())[:150], ans))
    elif not any(r.get("final") for r in rounds) and payload.get("answer"):
        L.append(("final", " ".join(str(payload["answer"]).split())[:150], str(payload["answer"])))
    for i, v in enumerate(tr.get("verification") or []):
        cs = v.get("conditions") or {}
        L.append(("gate", f"gate attempt {i + 1}: {'PASS' if v.get('passed') else 'FAIL'} · " + " ".join(f"{c.get('label', k)}{'✓' if c.get('passed') else ('·' if c.get('applicable') is False else '✗')}" for k, c in cs.items()), "\n".join(f"{c.get('label', k)} {k}: {'pass' if c.get('passed') else 'FAIL'}{' · ' + str(c.get('detail')) if c.get('detail') else ''}" for k, c in cs.items())))
    for m in tr.get("verification_retry_messages") or []:
        L.append(("gate", "retry message: " + " ".join(str(m).split())[:150], str(m)))
    if tr.get("status") and tr.get("status") != "ok":
        L.append(("status", "engine status: " + str(tr["status"]), str(tr["status"])))
    return L


def load_example(rel: str, rid: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    d = RESULTS / rel
    try:
        rows = {r["request_id"]: r for r in json.loads((d / "raw" / "report.rescored.json").read_text(encoding="utf-8"))["runs"]}
    except Exception:
        return None, None
    row = rows.get(rid)
    if not row:
        return None, None
    hits = list((d / "raw" / "traces").rglob(f"{rid}_run0.json")) if (d / "raw" / "traces").is_dir() else []
    payload = json.loads(hits[0].read_text(encoding="utf-8")) if hits else {"trace": row.get("trace") or {}, "answer": row.get("raw_response")}
    return payload, row


def prompt_for(runner: str, rid: str, reqs: Any, net: Any) -> str:
    """The prompt this design sends to ``runner`` for scenario ``rid``, rendered as labeled blocks."""
    m = methods.get_method(runner)
    r = next((x for x in reqs if x.id == rid), None)
    if r is None or m.kind == "rule_based":
        return "<p class='muted'>No prompt: the parser reads the request text directly.</p>"
    sp = methods.system_prompt_for(m, tool_variant=TOOLS) or ""
    out = [f"<div class='muted'>system prompt · hash {methods.prompt_hash(sp)}</div>", blocks_html(split_system(sp, m), collapsed=())]
    if m.architecture == "plan_act":
        out += ["<div class='muted'>planner system prompt (planning call only)</div>", blocks_html([("planner", methods.planner_prompt_for(m, tool_variant=TOOLS) or "")], collapsed=("planner",))]
    if m.kind == "llm_only":
        u = build_messages(m.strategy or "structured", "llm_only", r.text, net, CASE, forced=bool(m.forced), probe=bool(m.probe), tool_variant=TOOLS)[1]["content"]
        out += ["<div class='muted'>user message</div>", blocks_html(split_user(u, bool(m.probe)))]
    else:
        out += ["<div class='muted'>user message</div>", blocks_html([("u_request", r.text)])]
    if m.uses_tools and m.uses_llm:
        out += ["<div class='muted'>tool schema, with every call</div>", blocks_html([("tools", json.dumps(get_openai_tools(variant=TOOLS), indent=1, ensure_ascii=False))], collapsed=("tools",))]
    return "".join(out)


def examples_section(reqs: Any, net: Any = None) -> str:
    out = ["<div class='card'><h2>The same request under each method, step by step</h2><p class='muted'><b>Illustration, not a result.</b> The steps come from earlier runs made under the previous prompts, so you can see how each method moves before the new runs exist: what it says, what it calls, what the solver returns. Nothing here is scored; scores belong to the results page, after the runs. Click a line to expand it.</p>"
           "<p><label>Model <span class='seg' id='exm'><button data-v='gpt-5.6-sol' class='on'>gpt-5.6-sol</button><button data-v='gpt-4o-mini'>gpt-4o-mini</button></span></label> <label>Scenario <select id='exs'>" + "".join(f"<option value='{rid}'>{E(next((f'{i+1:02d} · {r.difficulty} · {r.text}' for i, r in enumerate(reqs) if r.id == rid), rid))}</option>" for rid in EXAMPLE_SCENARIOS) + "</select></label></p></div>"]
    for model, runs in EXAMPLE_RUNS.items():
        for rid in EXAMPLE_SCENARIOS:
            out.append(f"<div class='ex' data-model='{model}' data-scn='{rid}'><div class='cols6'>")
            for r in ROWS:
                rel = runs.get(r["runner"])
                payload, row = load_example(rel, rid) if rel else (None, None)
                if not row:
                    out.append(f"<div class='col'><h4>{E(r['label'])}</h4><p class='muted'>no run</p></div>"); continue
                lines = example_rows(payload, row)
                stored = bool(((payload or {}).get("trace") or {}).get("messages"))
                out.append(f"<div class='col'><h4>{E(r['label'])}</h4><details class='pr'><summary>prompt sent to this method for this scenario</summary><div class='prb'>{prompt_for(r['runner'], rid, reqs, net)}</div><div class='muted' style='padding:4px 10px'>{'This example run stored exactly these messages.' if stored else 'Shown as this design will send it; this example run stored only the request and the prompt hash (' + E(str(row.get('system_prompt_hash'))) + ').'}</div></details><div class='log'>" + "".join(f"<div class='ln' data-full='{E(full)}'><span class='k {k}'>{k}</span><span class='s'>{E(short)}</span></div>" for k, short, full in lines) + f"</div><div class='vt'>{row.get('n_llm_calls')} model calls, {row.get('n_tool_calls')} solver calls<br><span class='muted'>from {E(rel)}</span></div></div>")
            out.append("</div></div>")
    return "".join(out)



def split_user(text: str, probe: bool) -> List[Tuple[str, str]]:
    """Split an assembled user message into labeled blocks at its '## ' headings."""
    heads = {"## System Data": "u_data", "## Worked Examples": "u_examples", "## Task": "u_task", "## Reasoning Instructions": "u_reason", "## Formulation": "u_form", "## Operations": "u_ops", "## Output Requirements": "u_out_probe" if probe else "u_out"}
    parts: List[Tuple[str, str]] = []
    idx = [(m.start(), m.group(0)) for m in re.finditer(r"^## [A-Za-z ]+", text, flags=re.M)]
    if not idx:
        return [("u_request", text)]
    if idx[0][0] > 0:
        parts.append(("u_role", text[: idx[0][0]].strip()))
    for i, (pos, head) in enumerate(idx):
        end = idx[i + 1][0] if i + 1 < len(idx) else len(text)
        key = next((v for k, v in heads.items() if head.startswith(k)), "u_other")
        parts.append((key, text[pos:end].strip()))
    return parts


def split_system(text: str, m: methods.Method) -> List[Tuple[str, str]]:
    parts: List[Tuple[str, str]] = []
    if m.kind == "llm_only" and m.probe:
        base = methods.read_text("_shared/formulation_probe_system_prompt.txt")
        parts.append(("sys_probe", base))
        rest = text[len(base):]
    elif m.kind == "llm_only":
        base = methods.read_text("_shared/llm_only_system_prompt.txt").strip()
        if m.forced:
            from llm.prompt_variants import forced_system_prompt

            fb = forced_system_prompt(base)
            clause = methods.read_text("llm_only_forced_structured/forced_replacement.txt")
            i = fb.find(clause)
            parts.append(("sys_base", fb[:i].rstrip()))
            parts.append(("sys_forced", clause))
            rest = text[len(fb):]
        else:
            parts.append(("sys_base", base))
            rest = text[len(base):]
    else:
        base = methods.read_text("_shared/agent_system_prompt.txt")
        parts.append(("sys_agent", base))
        rest = text[len(base):]
    if rest.strip():
        parts.append(("sys_cot" if "Reasoning mode" in rest else "sys_other", rest.strip()))
    return parts


def diagram(kind: str) -> str:
    """Small inline SVG of the method's control flow."""
    W, H_ = 230, 250
    box = lambda x, y, w, h, t, c="#fff", stroke="#cbd5e1": f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='8' fill='{c}' stroke='{stroke}'/><text x='{x + w / 2}' y='{y + h / 2 + 4}' text-anchor='middle' font-size='11' font-family='Inter,Helvetica,Arial' fill='#0f172a'>{t}</text>"
    arrow = lambda x1, y1, x2, y2, c="#64748b": f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='{c}' stroke-width='1.6' marker-end='url(#a)'/>"
    label = lambda x, y, t, c="#64748b": f"<text x='{x}' y='{y}' font-size='10' font-family='Inter,Helvetica,Arial' fill='{c}'>{t}</text>"
    d = [f"<svg viewBox='0 0 {W} {H_}' width='100%' xmlns='http://www.w3.org/2000/svg'><defs><marker id='a' markerWidth='8' markerHeight='8' refX='7' refY='4' orient='auto'><path d='M0,0 L8,4 L0,8 z' fill='#64748b'/></marker></defs>"]
    d.append(box(60, 8, 110, 26, "request", "#eef1f5"))
    if kind == "rule_based":
        d.append(arrow(115, 34, 115, 56)); d.append(box(45, 56, 140, 28, "regex parser", "#f3f4f6")); d.append(arrow(115, 84, 115, 108)); d.append(box(45, 108, 140, 28, "solver (PandaPower)", "#e0f2f1", "#0f8f84")); d.append(arrow(115, 136, 115, 160)); d.append(box(45, 160, 140, 28, "template answer", "#eef1f5")); d.append(label(8, 215, "no LLM · no gate"))
    elif kind in ("llm_only:structured", "llm_only:cot"):
        d.append(arrow(115, 34, 115, 56)); d.append(box(30, 56, 170, 40, "LLM reads the case tables", "#e8eefc", "#2f5fd0")); d.append(label(40, 90, "and computes by hand" if kind.endswith("structured") else "reasons, then computes by hand", "#2f5fd0")); d.append(arrow(115, 96, 115, 120)); d.append(box(45, 120, 140, 28, "JSON answer", "#eef1f5")); d.append(label(8, 175, "no solver · no tool calls · no gate")); d.append(label(8, 192, "may set converged=false (abstain)"))
    elif kind == "plan_act_nogate":
        d.append(arrow(115, 34, 115, 56)); d.append(box(30, 56, 170, 28, "LLM writes the whole plan", "#e8eefc", "#6d4fc4")); d.append(arrow(115, 84, 115, 108)); d.append(box(30, 108, 170, 28, "solver runs every step", "#e0f2f1", "#0f8f84")); d.append(arrow(115, 136, 115, 160)); d.append(box(30, 160, 170, 28, "LLM writes the answer", "#e8eefc", "#2f5fd0")); d.append(label(8, 215, "plans once, never sees results before committing"))
    else:  # react / pfagent
        d.append(arrow(115, 34, 115, 56)); d.append(box(30, 56, 170, 28, "LLM decides a tool call", "#e8eefc", "#2f5fd0")); d.append(arrow(115, 84, 115, 108)); d.append(box(30, 108, 170, 28, "solver executes it", "#e0f2f1", "#0f8f84"))
        d.append(f"<path d='M200,122 C225,122 225,70 200,70' fill='none' stroke='#64748b' stroke-width='1.6' marker-end='url(#a)'/>"); d.append(label(160, 100, "up to 8 rounds", "#64748b"))
        d.append(arrow(115, 136, 115, 160))
        if kind == "pfagent":
            d.append(box(30, 160, 170, 28, "verification gate V1–V7", "#fff7db", "#c99a06")); d.append(arrow(115, 188, 115, 212)); d.append(box(15, 212, 95, 26, "report", "#e6f4ea", "#1f9d55")); d.append(box(120, 212, 95, 26, "escalate", "#fdf0e3", "#e0891a"))
        else:
            d.append(box(30, 160, 170, 28, "LLM writes the answer", "#e8eefc", "#2f5fd0")); d.append(label(8, 215, "sees every result · no gate"))
    d.append("</svg>")
    return "".join(d)


def _src(obj: Any) -> str:
    try:
        return inspect.getsource(obj)
    except Exception as exc:  # pragma: no cover
        return f"(source not available: {exc})"


def blocks_html(parts: List[Tuple[str, str]], collapsed: Tuple[str, ...] = ("u_data",)) -> str:
    out = []
    for key, txt in parts:
        color, label, src = BLOCKS.get(key, ("#94a3b8", key, ""))
        body = f"<pre>{E(txt)}</pre>"
        if key in collapsed:
            body = f"<details><summary>show the {len(txt)} characters</summary>{body}</details><pre class='peek'>{E(txt[:420])}…</pre>"
        out.append(f"<div class='blk' style='border-left-color:{color}'><div class='blk-h'><span class='sw' style='background:{color}'></span><b>{E(label)}</b><span class='src'>{E(src)}</span></div>{body}</div>")
    return "".join(out)



def build() -> Path:
    reqs = generate_requests(CASE, N, SEED)
    net = perturbed_case(CASE, seed=SEED, k=K)
    css = """
:root{--bg:#f3f5f8;--panel:#fff;--line:#e3e7ee;--text:#0f172a;--muted:#64748b;--acc:#2f5fd0;--ok:#1f9d55;--esc:#e0891a;--bad:#d53f3f;--shadow:0 1px 2px rgba(15,23,42,.06),0 4px 14px rgba(15,23,42,.05)}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 Inter,-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:var(--text);background:var(--bg)}
header{position:sticky;top:0;z-index:5;background:var(--panel);border-bottom:1px solid var(--line);padding:10px 22px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
header h1{font-size:17px;margin:0;letter-spacing:-.01em}.tabs{display:flex;gap:4px}body.embed header{display:none}.tabs button{font:inherit;font-weight:500;padding:7px 14px;border:1px solid transparent;border-radius:8px;background:transparent;cursor:pointer;color:var(--muted)}.tabs button.on{background:var(--acc);color:#fff}
main{padding:18px 22px;max-width:1500px;margin:0 auto}.tab{display:none}.tab.on{display:block}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow);margin-bottom:12px}.card h2{font-size:16px;margin:0 0 6px}.card h3{font-size:14px;margin:12px 0 6px}
.grid{display:grid;gap:12px}.g6{grid-template-columns:repeat(6,minmax(0,1fr))}.dg{background:#fafbfd;border:1px solid var(--line);border-radius:10px;padding:8px}.dg h4{margin:0;font-size:12.5px}.g3{grid-template-columns:repeat(3,minmax(0,1fr))}.g2{grid-template-columns:repeat(2,minmax(0,1fr))}
.muted{color:var(--muted);font-size:12.5px}.chip{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11.5px;font-weight:600;background:#eef1f5;color:#334155;margin:2px 4px 2px 0}.chip.acc{background:var(--acc);color:#fff}.chip.ok{background:#e6f4ea;color:#166534}.chip.bad{background:#fdecec;color:#991b1b}
.flow{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0}.flow .box{background:#fff;border:1px solid var(--line);border-radius:10px;padding:8px 12px;box-shadow:var(--shadow)}.flow .box b{display:block;font-size:13px}.flow .box span{font-size:12px;color:var(--muted)}.flow .arr{color:var(--muted);font-size:18px}
table{border-collapse:collapse;width:100%;font-size:13px;background:#fff}th,td{border:1px solid var(--line);padding:6px 8px;vertical-align:top;text-align:left}th{background:#f6f8fb;font-weight:600}
pre{background:#fafbfd;border:1px solid var(--line);border-radius:8px;padding:10px;white-space:pre-wrap;word-break:break-word;font:12px/1.45 "JetBrains Mono",ui-monospace,Menlo,Consolas,monospace;margin:4px 0;max-height:460px;overflow:auto}pre.peek{max-height:none;color:var(--muted)}
.blk{border-left:5px solid #ccc;background:#fff;border-radius:0 8px 8px 0;padding:8px 12px;margin:8px 0;border-top:1px solid var(--line);border-right:1px solid var(--line);border-bottom:1px solid var(--line)}.blk-h{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.blk-h .src{color:var(--muted);font-size:11.5px;font-family:ui-monospace,Menlo,monospace}.sw{width:10px;height:10px;border-radius:3px;display:inline-block}
details summary{cursor:pointer;color:var(--acc);font-size:12.5px}.hid{display:none}
.mcard{cursor:pointer}.mcard:hover{border-color:var(--acc)}.mcard.on{border-color:var(--acc);box-shadow:0 0 0 2px #dbe5fb}
.steps{margin:0;padding-left:18px;font:12px/1.5 "JetBrains Mono",ui-monospace,Menlo,monospace}.steps li{margin:1px 0}
select{font:inherit;padding:5px 8px;max-width:760px}a.lnk{color:var(--acc);text-decoration:none;font-weight:500}a.lnk:hover{text-decoration:underline}
.legend{display:flex;gap:10px;flex-wrap:wrap;font-size:12px;color:var(--muted)}.legend span{display:inline-flex;gap:5px;align-items:center}
.cols6{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;align-items:start}.col{background:#fff;border:1px solid var(--line);border-radius:10px;min-width:0;overflow:hidden}.col h4{margin:0;padding:8px 10px;border-bottom:1px solid var(--line);font-size:12.5px;background:#fafbfd;display:flex;justify-content:space-between;gap:6px;align-items:center}.vd{display:inline-block;padding:1px 8px;border-radius:999px;color:#fff;font-size:10.5px;font-weight:600;white-space:nowrap}.vd.solved{background:var(--ok)}.vd.escalated{background:var(--esc)}.vd.wrong{background:var(--bad)}
.log{font:11.5px/1.4 'JetBrains Mono',ui-monospace,Menlo,monospace}.ln{display:grid;grid-template-columns:44px 1fr;gap:6px;padding:4px 8px;border-bottom:1px solid #f0f2f5;cursor:pointer}.ln:hover{background:#f7f9fc}.ln .k{font-weight:600;font-size:10.5px}.ln .k.model{color:var(--acc)}.ln .k.solver{color:#0f8f84}.ln .k.plan{color:#6d4fc4}.ln .k.gate{color:#c99a06}.ln .k.final{color:var(--acc)}.ln .k.status{color:var(--muted)}.ln .s{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ln.open .s{white-space:pre-wrap;overflow:visible;word-break:break-word}details.pr{border-bottom:1px solid var(--line)}details.pr summary{padding:6px 10px;font-size:12px}.prb{padding:0 8px 6px}.prb .blk{margin:6px 0}.prb pre{max-height:260px;font-size:11px}
.vt{padding:8px 10px;border-top:1px solid var(--line);font-size:11.5px;background:#fbfcfe}
table.cmp td,table.cmp th{font-size:12.5px}.ex{display:none}.ex.on{display:block}.seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:#fff;vertical-align:middle}.seg button{font:inherit;font-weight:500;padding:4px 12px;border:none;background:#fff;cursor:pointer;color:var(--muted)}.seg button.on{background:var(--acc);color:#fff}
.kv{display:grid;grid-template-columns:auto 1fr;gap:3px 12px;font-size:13px}.kv b{color:var(--muted);font-weight:500}
"""
    H: List[str] = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>PFAgent · Evaluation design</title><link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap' rel='stylesheet'><style>{css}</style></head><body>"]
    tabs = [("overview", "Overview"), ("methods", "Methods"), ("scenarios", "Scenarios"), ("prompts", "Prompts"), ("tools", "Tools"), ("gate", "Gate & scoring"), ("plan", "Run plan")]
    H.append("<header><h1>PFAgent · Evaluation design</h1><nav class='tabs'>" + "".join(f"<button data-tab='{k}' class='{'on' if k == 'overview' else ''}'>{v}</button>" for k, v in tabs) + "</nav></header><main>")

    # ---------------- overview
    H.append("<div class='tab on' id='tab-overview'>")
    H.append("<div class='card'><h2>One question, six ways to answer it</h2><p>Every method receives the same 40 natural-language power-flow requests on the same perturbed IEEE 14-bus network, answers with the same JSON object, and is scored by the same evaluator. What changes between methods is only <b>who formulates</b> the solver operations, <b>who computes</b> the numbers, whether the method <b>sees the solver's outputs</b> before answering, and whether a <b>gate</b> checks the answer before it is reported.</p>")
    H.append("<div class='flow'><div class='box'><b>Request</b><span>one of 40 scenarios</span></div><span class='arr'>→</span><div class='box'><b>Formulate</b><span>which solver operations, with which arguments</span></div><span class='arr'>→</span><div class='box'><b>Compute</b><span>PandaPower, or the LLM by hand</span></div><span class='arr'>→</span><div class='box'><b>Report</b><span>the answer for the operator</span></div><span class='arr'>→</span><div class='box'><b>Verdict</b><span>solved · escalated · wrong</span></div></div></div>")
    H.append("<div class='grid g3'>")
    for r in ROWS:
        H.append(f"<div class='card'><h2>{E(r['label'])} <span class='chip'>{E(r['sub'])}</span></h2><div class='kv'><b>formulates</b><span>{E(r['formulates'])}</span><b>computes</b><span>{E(r['computes'])}</span><b>sees outputs</b><span>{E(r['sees'])}</span><b>gate</b><span>{E(r['gate'])}</span></div><p class='muted'>{E(r['story'])}</p></div>")
    H.append("</div>")
    H.append(f"<div class='card'><h2>Common to every method</h2><span class='chip'>IEEE 14-bus</span><span class='chip'>N = {N} requests</span><span class='chip'>perturbation seed {SEED}, k = {K}</span><span class='chip'>≤ {ROUNDS} tool rounds</span><span class='chip'>temperature 0</span><span class='chip'>tool set {TOOLS}</span><span class='chip'>models: gpt-4o-mini · gpt-5.6-sol</span><span class='chip'>same output JSON for every method</span><span class='chip'>one evaluator for every method</span><span class='chip'>every message sent is stored in the trace</span></div>")
    H.append("</div>")

    # ---------------- methods
    H.append("<div class='tab' id='tab-methods'>")
    cols = ["case tables in the prompt", "tool schema (function calling)", "allowed values of each argument", "1-based / (0-based) indexing rule", "sees the solver outputs", "may abstain (converged=false)", "gate"]
    matrix: List[Tuple[str, Dict[str, str]]] = []
    for r in ROWS:
        m = methods.get_method(r["runner"])
        sp = methods.system_prompt_for(m, tool_variant=TOOLS) or ""
        planner = methods.planner_prompt_for(m, tool_variant=TOOLS) if m.architecture == "plan_act" else None
        u0 = build_messages(m.strategy or "structured", "llm_only", reqs[0].text, net, CASE, forced=bool(m.forced), probe=bool(m.probe), tool_variant=TOOLS)[1]["content"] if m.kind == "llm_only" else ""
        tools = get_openai_tools(variant=TOOLS) if (m.uses_tools and m.uses_llm) else []
        sysm = sp + (planner or "")
        matrix.append((r["label"], {cols[0]: "yes" if "### Node Data" in u0 else ("n/a" if m.kind == "rule_based" else "no"), cols[1]: "yes" if tools else ("n/a" if m.kind == "rule_based" else "no"), cols[2]: "yes" if (tools or " in {" in sysm) else ("n/a" if m.kind == "rule_based" else "no"), cols[3]: "yes" if "0-based" in sysm else ("fixed rules" if m.kind == "rule_based" else "no"), cols[4]: "yes" if m.architecture == "react" else ("no" if m.uses_tools else "n/a"), cols[5]: "yes" if "set `converged` to false" in sp else ("n/a" if m.uses_tools or m.kind == "rule_based" else "no"), cols[6]: "final V1–V7" if m.final_gate else "no"}))
    # diagrams row
    H.append("<div class='card'><h2>Six ways to answer the same request</h2><div class='grid g6'>" + "".join(f"<div class='dg'><h4>{E(r['label'])}</h4><div class='muted'>{E(r['sub'])}</div>{diagram(r['runner'])}</div>" for r in ROWS) + "</div></div>")
    # light comparison
    aspects = [("formulates the solver operations", "formulates"), ("computes the numbers", "computes"), ("sees the solver outputs before answering", "sees"), ("gate on the answer", "gate")]
    H.append("<div class='card'><h2>Side by side</h2><table class='cmp'><tr><th></th>" + "".join(f"<th>{E(r['label'])}</th>" for r in ROWS) + "</tr>")
    for title, key in aspects:
        H.append(f"<tr><td><b>{E(title)}</b></td>" + "".join(f"<td>{E(r[key])}</td>" for r in ROWS) + "</tr>")
    H.append("<tr><td></td>" + "".join(f"<td><a class='lnk' href='#' data-goto='{E(r['runner'])}'>prompts →</a></td>" for r in ROWS) + "</tr></table>")
    H.append("<details><summary>Details: what information each method receives, and the prompt blocks it is built from</summary><table class='cmp' style='margin-top:8px'><tr><th></th>" + "".join(f"<th>{E(r['label'])}</th>" for r in ROWS) + "</tr>")
    for c in cols:
        H.append(f"<tr><td><b>{E(c)}</b></td>" + "".join(f"<td style='background:{'#e6f4ea' if v.startswith('yes') or v.startswith('final') else ('#f3f4f6' if v in ('n/a', 'fixed rules') else '#fdecec')}'>{E(v)}</td>" for _, row in matrix for v in [row[c]]) + "</tr>")
    H.append("<tr><td><b>prompt blocks</b></td>" + "".join("<td>" + (" ".join(f"<span class='chip'>{E(Path(f).name)}</span>" for f in methods.get_method(r['runner']).prompt_files) or "<span class='muted'>none, no LLM</span>") + "</td>" for r in ROWS) + "</tr></table><p class='muted'>Derived from the assembled prompts. Green: the method receives it. Red: it does not. Grey: not applicable. The prompting methods get no tools by design: they declare the operations the request needs and their numbers are their own arithmetic.</p></details></div>")
    H.append(examples_section(reqs, net))
    H.append("</div>")

    # ---------------- scenarios
    H.append("<div class='tab' id='tab-scenarios'>")
    H.append(f"<div class='card'><h2>The {N} scenarios</h2><p>The same requests every method and every model see, generated by <code>benchmarks/requests.py</code> from (case14, N = 40, seed 0): ten <b>plain</b>, ten <b>parameterized</b> (a value or a criterion is stated), ten <b>multistep</b> (several operations), ten <b>ambiguous</b> (numbers spelled out, units in kW, 0-based indices). They are the same 40 used by every run since 2026-09-14.</p><p><b>Why every expected outcome is “converged”.</b> This is the normal request set: the reference solution of each request converges on a connected network, so the reference calls and the reference numbers are deterministic and every method can be judged on the same ground truth. Requests whose reference fails (islanding, non-convergence) form a separate <b>stress</b> set used to measure safe failure; it is not part of this evaluation.</p><p class='muted'>Reference calls are what a correct formulation must match: same tools, same identifiers and values, same order; read-only repeats are ignored. Click “prompts” to see how every method receives that scenario.</p><div class='legend'><span><span class='sw' style='background:#1f9d55'></span>plain</span><span><span class='sw' style='background:#2f5fd0'></span>parameterized</span><span><span class='sw' style='background:#6d4fc4'></span>multistep</span><span><span class='sw' style='background:#e0891a'></span>ambiguous</span></div></div>")
    dcol = {"plain": "#1f9d55", "parameterized": "#2f5fd0", "multistep": "#6d4fc4", "ambiguous": "#e0891a"}
    H.append("<div class='card'><table><tr><th>#</th><th>scenario</th><th>request</th><th>reference calls, in order</th><th></th></tr>")
    for i, r in enumerate(reqs, start=1):
        steps = "".join(f"<li>{E(c['tool'])}(" + E(", ".join(f"{k}={v}" for k, v in (c.get('args') or {}).items())) + ")</li>" for c in r.intended_calls)
        H.append(f"<tr><td>{i}</td><td><span class='sw' style='background:{dcol[r.difficulty]}'></span> {E(r.difficulty)}<br><span class='muted'>{E(r.id)}</span></td><td>{E(r.text)}</td><td><ol class='steps'>{steps}</ol></td><td><a class='lnk' href='#' data-scn='{E(r.id)}'>prompts →</a></td></tr>")
    H.append("</table></div></div>")

    # ---------------- prompts
    H.append("<div class='tab' id='tab-prompts'>")
    H.append("<div class='card'><h2>What the model receives, block by block</h2><p>Pick a scenario and a method. Each prompt is shown as the blocks it is assembled from; the colour tells the kind of block and the grey label says which file or code produces it. The case-tables block is long and collapsed; it is identical for every scenario (same perturbed network).</p><div class='legend'>" + "".join(f"<span><span class='sw' style='background:{c}'></span>{E(l)}</span>" for k, (c, l, s) in BLOCKS.items() if k in ('sys_base', 'sys_agent', 'sys_cot', 'u_data', 'u_task', 'u_reason', 'u_ops', 'u_out', 'planner', 'tools')) + "</div>")
    all_methods = [r["runner"] for r in ROWS] + [c for r in ROWS for c, _ in r.get("companions", [])]
    labels = {r["runner"]: r["label"] for r in ROWS}
    for r in ROWS:
        for c, why in r.get("companions", []):
            labels[c] = f"{r['label']} · companion: {methods.get_method(c).folder}"
    H.append("<p><label>Scenario <select id='scn'>" + "".join(f"<option value='{r.id}'>{i+1:02d} · {E(r.difficulty)} · {E(r.text)}</option>" for i, r in enumerate(reqs)) + "</select></label> <label>Method <select id='mth'>" + "".join(f"<option value='{E(k)}'>{E(labels[k])}</option>" for k in all_methods) + "</select></label></p></div>")
    for runner in all_methods:
        m = methods.get_method(runner)
        H.append(f"<div class='pm card' data-mth='{E(runner)}'><h2>{E(labels[runner])} <span class='muted'>runner: {E(runner)}</span></h2>")
        if m.kind == "rule_based":
            H.append("<p class='muted'>No LLM and no prompt. The parser reads the request text and calls the solver; its code is in the Tools tab and the Gate & scoring tab (deterministic parser).</p></div>")
            continue
        sp = methods.system_prompt_for(m, tool_variant=TOOLS) or ""
        H.append(f"<h3>System prompt <span class='muted'>hash {methods.prompt_hash(sp)}</span></h3>" + blocks_html(split_system(sp, m), collapsed=()))
        if m.architecture == "plan_act":
            planner = methods.planner_prompt_for(m, tool_variant=TOOLS) or ""
            H.append(f"<h3>Planner system prompt <span class='muted'>used only by the planning call, with the request as user message · hash {methods.prompt_hash(planner)}</span></h3>" + blocks_html([("planner", planner)], collapsed=()))
        H.append("<h3>User message for the selected scenario</h3>")
        for r in reqs:
            if m.kind == "llm_only":
                u = build_messages(m.strategy or "structured", "llm_only", r.text, net, CASE, forced=bool(m.forced), probe=bool(m.probe), tool_variant=TOOLS)[1]["content"]
                parts = split_user(u, bool(m.probe))
            else:
                parts = [("u_request", r.text)]
            H.append(f"<div class='um' data-scn='{r.id}'>{blocks_html(parts)}</div>")
        if m.uses_tools and m.uses_llm:
            H.append("<h3>Tool schema, sent through function calling with every call</h3>" + blocks_html([("tools", json.dumps(get_openai_tools(variant=TOOLS), indent=1, ensure_ascii=False))], collapsed=("tools",)))
        H.append("</div>")
    H.append("</div>")

    # ---------------- tools
    from solver.power_flow import SolverConfig

    ctx = ToolContext(session=SessionState(), solver_config=SolverConfig())
    disp = perturbing_dispatcher(ctx, seed=SEED, k=K)
    sample: Dict[str, Dict[str, Any]] = {"load_case": {"case_name": "case14"}, "run_powerflow": {}, "get_status": {}, "get_most_loaded_branch": {}, "set_active_load": {"bus_id": 6, "p_mw": 14.7}, "set_load": {"bus_id": 9, "p_mw": 29.5, "q_mvar": 16.6}, "disconnect_line": {"from_bus": 1, "to_bus": 5}, "reconnect_line": {"from_bus": 1, "to_bus": 5}, "run_n1_contingency": {"top_k": 1, "criteria": "max_violations"}, "recommend_remedial_actions": {"max_actions": 2}, "apply_remedial_action": {"action_index": 0, "confirmed": True}, "generate_plot": {"plot_type": "voltage_heatmap"}}
    order = list(sample)
    schema = {(t.get("function") or t)["name"]: (t.get("function") or t) for t in get_openai_tools(variant=TOOLS)}
    H.append("<div class='tab' id='tab-tools'><div class='card'><h2>The solver interface</h2><p>These twelve tools are the only way any method touches the network. The schema is what the model sees; the handler is the Python the dispatcher runs (PandaPower underneath); the output was produced now on the same perturbed case14 the runs use, in this order, so state carries from one call to the next.</p></div>")
    for name in order:
        fn = schema.get(name, {}); props = (fn.get("parameters") or {}).get("properties") or {}; req = set((fn.get("parameters") or {}).get("required") or [])
        inputs = "".join(f"<tr><td><code>{E(k)}</code>{'*' if k in req else ''}</td><td>{E(str(v.get('type')))}{' in {' + ', '.join(map(str, v['enum'])) + '}' if v.get('enum') else ''}</td><td>{E(str(v.get('default'))) if 'default' in v else ''}</td><td>{E(v.get('description') or '')}</td></tr>" for k, v in props.items()) or "<tr><td colspan='4' class='muted'>no inputs</td></tr>"
        code = _src(disp.handlers.get(name)) if disp.handlers.get(name) else "(no handler)"
        try:
            result = disp.dispatch(name, sample[name])
        except Exception as exc:
            result = f"(error: {exc})"
        result = FIG.sub(lambda mm: f'"figure_json": "<plot, {len(mm.group(1)) // 1024} KB, omitted>"', str(result))
        H.append(f"<div class='card'><h2><code>{E(name)}</code> <span class='muted'>{E(fn.get('description') or '')}</span></h2><div class='grid g2'><div><h3>Inputs</h3><table><tr><th>input</th><th>type</th><th>default</th><th>meaning</th></tr>{inputs}</table><h3>Output for <code>{E(name)}({E(', '.join(f'{k}={v!r}' for k, v in sample[name].items()))})</code></h3><pre>{E(result if len(result) < 5000 else result[:5000] + chr(10) + '... (' + str(len(result) - 5000) + ' more chars)')}</pre></div><div><h3>Handler, Python</h3><pre>{E(code)}</pre></div></div></div>")
    H.append("</div>")

    # ---------------- gate & scoring
    GATE = [("V1", "converged", "The last power flow the agent ran converged."), ("V2", "balance", "Active-power balance of the reported state holds within tolerance."), ("V3", "no_isolated_buses", "No bus was left isolated by the network changes."), ("V4", "faithfulness", "Every unit-bearing number in the answer appears in a tool output."), ("V5", "currency", "Those numbers come from the solve made after the last network change."), ("V6", "argument_grounding", "Every argument of a mutating tool traces to the request or to a prior tool output; a positive max_candidates on the N-1 scan must also come from the request."), ("V7", "claims_from_tools", "The answer's claims match the agent's own last solved state.")]
    SCORING = [
        ("Where the numbers come from", "The evaluator reads the answer JSON, never the solver trace: the trace is evidence for traceability and for the gate, not the source of the scored numbers."),
        ("Reported state", "Bus voltages, branch flows and totals from the answer JSON, compared with the reference solution: voltage MAE, flow MAE, coverage (every bus reported), and the bus power-balance residual."),
        ("Answer", "The specific quantity the request asked for (worst outage, lowest-voltage bus, overloaded lines, totals), read from the answer and compared with the reference answer."),
        ("Formulation", "The `formulation` field of the answer, the ordered solver operations the method used (with tools) or that the request needs (without tools), must match the reference operations in tool, identifiers, values and order; read-only repeats are ignored; an unrequested argument that changes the result (an invented q_mvar, an N-1 max_candidates below the branch count) is an error. With tools, the declared operations must also match the ones the trace shows the method actually ran."),
        ("Escalated", "The answer declares it cannot complete the request: cannot_answer filled, the abstention shape (converged false, empty arrays), an explicit statement of inability, the round limit, or the gate rejecting every candidate. Takes precedence over the other two outcomes."),
        ("Solved", "Not escalated, formulation exact, a reported state that converges like the reference, covers every bus, and is within tolerance (1e-3 p.u. on voltages, 1% on flows), and an answer that matches the reference where the request asks a checkable question."),
        ("Wrong, unflagged", "Everything else: numbers or an answer that do not match the reference, reported as if they did. Solved + Escalated + Wrong = 100%."),
        ("Traceable", "Every number in the answer JSON appears in a solver output of the trace, from the solve after the last network change. Zero by construction without tools."),
    ]
    contract = methods.read_text("_shared/output_contract.txt")
    rules = methods.read_text("_shared/common_rules.txt")
    FIELDS = [
        ("formulation", "the ordered solver operations the method ran (tools) or that the request needs (no tools)", "the model; the parser copies its plan", "compared with the reference operations → Formulation; with tools, also compared with what the trace shows ran"),
        ("converged", "whether the reported state is a converged solution", "the model, from the solver (tools) or its own judgment (no tools)", "must match the reference; false with empty arrays counts as declaring inability → Escalated"),
        ("summary", "one sentence on what was done, including the interpretation of an ambiguous request", "the model", "read by a person; not scored"),
        ("answer", "the specific thing the request asked for, with its numbers", "the model", "compared with the reference answer (worst outage, lowest-voltage bus, overloaded lines, totals) → Solved / Wrong"),
        ("bus_voltages, line_flows, totals", "the full network state being reported", "copied from the last solve (tools) or computed by hand (no tools)", "compared bus by bus and branch by branch with the reference → V_MAE, flow MAE, coverage, KCL; every number checked against the trace → Traceable"),
        ("violations", "buses outside 0.95–1.05 p.u., branches above 100 % loading, in the reported state", "the model", "read by a person; consistency with the state is part of the gate's checks"),
        ("next_step", "one recommendation for the operator", "the model", "read by a person; not scored"),
        ("cannot_answer", "why the request could not be completed, or null", "the model", "a filled string → Escalated"),
    ]
    field_rows = "".join(f"<tr><td><code>{E(a)}</code></td><td>{E(b)}</td><td>{E(c)}</td><td>{E(d)}</td></tr>" for a, b, c, d in FIELDS)
    H.append("<div class='tab' id='tab-gate'><div class='card'><h2>The answer every method must return</h2><h3>What we expect back, field by field</h3><table><tr><th>field</th><th>what it holds</th><th>who fills it</th><th>what the evaluator does with it</th></tr>" + field_rows + "</table><h3>The exact text the model reads</h3><p class='muted'>This block is part of every prompt: the last section of the user message in the prompting methods, and the final-answer instruction of the agents. The parser fills the same object from the solver outputs without reading it.</p>" + blocks_html([("u_out", contract)], collapsed=()) + "<h3>The rules block, in both system prompts</h3>" + blocks_html([("sys_base", rules)], collapsed=()) + "</div><div class='grid g2'><div class='card'><h2>Verification gate, PFAgent only</h2><p class='muted'>Runs once on the final answer. A failure is sent back to the model with the failed conditions spelled out; a second failure escalates the request.</p><table><tr><th></th><th>condition</th></tr>" + "".join(f"<tr><td><b>{a}</b><br><span class='muted'>{b}</span></td><td>{E(c)}</td></tr>" for a, b, c in GATE) + "</table></div><div class='card'><h2>Scoring</h2><table><tr><th>metric</th><th>definition</th></tr>" + "".join(f"<tr><td><b>{E(a)}</b></td><td>{E(b)}</td></tr>" for a, b in SCORING) + "</table></div></div>")
    parts = [("Engine: one request, any architecture", LLMEngine.run_with_trace), ("ReAct loop", LLMEngine._run_react), ("Plan-and-Act", LLMEngine._run_plan_act), ("How a run ends", LLMEngine._finish), ("Verification gate V1–V7", verify_final_answer), ("V6 argument grounding", bm.argument_grounding_check), ("Deterministic parser: request → calls", rule_based._parse_clause), ("Deterministic parser: run", rule_based.run), ("Formulation comparator, rules R0–R10", bm.formulation_check), ("The evaluator: score_common", __import__("benchmarks.common_eval", fromlist=["score_common"]).score_common), ("Traceable numbers", bm.faithful_numbers), ("Answer matches the reference", bs.answer_matches_truth)]
    H.append("<div class='card'><h2>The code behind each step, verbatim</h2><p class='muted'>From llm/engine.py, baselines/rule_based.py, benchmarks/metrics.py and benchmarks/scoring.py in this worktree.</p>" + "".join(f"<details><summary><b>{E(t)}</b> · {E(o.__module__)}.{E(getattr(o, '__qualname__', o.__name__))} · {len(_src(o).splitlines())} lines</summary><pre>{E(_src(o))}</pre></details>" for t, o in parts) + "</div></div>")

    # ---------------- run plan
    H.append("<div class='tab' id='tab-plan'><div class='card'><h2>What runs and what it costs</h2><p class='muted'>Every prompt changed with the shared rules and the shared answer object, so no earlier run is comparable: all six methods run again on both models, 40 requests each, gpt-4o-mini first. Earlier runs stay under their own dates for reference only.</p><table><tr><th>method</th><th>gpt-4o-mini</th><th>gpt-5.6-sol</th><th>why</th></tr>")
    tm = ts = 0.0
    for runner, models_, note in RUN_PLAN:
        m = methods.get_method(runner)
        cm, cs = COST[runner]
        a = "run" if (not m.uses_llm or "gpt-4o-mini" in models_) else "skip"
        b = "run" if (not m.uses_llm or "gpt-5.6-sol" in models_) else "skip"
        if a == "run": tm += cm
        if b == "run": ts += cs
        H.append(f"<tr><td><b>{E(m.folder)}</b></td><td><span class='chip {'acc' if a == 'run' else ''}'>{a}</span> {'$%.2f' % cm if a == 'run' else ''}</td><td><span class='chip {'acc' if b == 'run' else ''}'>{b}</span> {'$%.2f' % cs if b == 'run' else ''}</td><td class='muted'>{E(note)}</td></tr>")
    H.append(f"</table><p>Estimated cost: gpt-4o-mini about ${tm:.2f}, gpt-5.6-sol about ${ts:.2f}, total about ${tm + ts:.2f}; the recorded costs are from 40-request runs with the earlier prompts, and the shared answer object asks for a few more output tokens, so allow about 20% more. The OpenRouter balance is ${BALANCE_USD:.2f}. The EV case study still needs about $10, so after the sol runs it waits for a recharge. Output goes to <code>results/ieee14/&lt;date&gt;/&lt;model&gt;/&lt;method&gt;/</code>; afterwards the results page and the table builder read only from there.</p><h3>Order</h3><ol><li>Parser (free) and the five LLM methods on gpt-4o-mini: about ${tm:.2f}.</li><li>Check the gpt-4o-mini reports and traces in the viewer. Fix anything wrong before spending on sol.</li><li>The five LLM methods on gpt-5.6-sol: about ${ts:.2f}.</li><li>Regenerate the results page and the paper table from the new folders.</li></ol><h3>Commands</h3><pre>")
    cmds = []
    for runner, models_, _ in RUN_PLAN:
        m = methods.get_method(runner)
        if not m.uses_llm:
            cmds.append(f".venv/bin/python run.py run --method {m.folder} --case ieee14 --n 40")
        elif models_:
            cmds.append(f".venv/bin/python run.py run --method {m.folder} " + " ".join(f"--model {MODEL_IDS[x]}" for x in models_) + " --case ieee14 --n 40")
    H.append(E("\n".join(cmds)) + "</pre></div></div>")

    H.append("""</main><script>
const tabs=document.querySelectorAll('.tabs button');function show(k){tabs.forEach(b=>b.classList.toggle('on',b.dataset.tab===k));document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on',t.id==='tab-'+k));window.scrollTo(0,0);}
tabs.forEach(b=>b.onclick=()=>{show(b.dataset.tab);history.replaceState(null,'','#'+b.dataset.tab);});
function fromHash(){const k=(location.hash||'#overview').slice(1);if(document.getElementById('tab-'+k)){show(k);}}
window.addEventListener('hashchange',fromHash);
if(window.self!==window.top){document.body.classList.add('embed');}
const _show=show;show=function(k){_show(k);if(window.self!==window.top){window.parent.postMessage({page:'design',tab:k},'*');}};
fromHash();
const scn=document.getElementById('scn'),mth=document.getElementById('mth');
function ap(){document.querySelectorAll('.um').forEach(p=>p.classList.toggle('hid',p.dataset.scn!==scn.value));document.querySelectorAll('.pm').forEach(p=>p.classList.toggle('hid',p.dataset.mth!==mth.value));}
scn.onchange=ap;mth.onchange=ap;ap();
const exm=document.getElementById('exm'),exs=document.getElementById('exs');let exModel='gpt-5.6-sol';function exAp(){document.querySelectorAll('.ex').forEach(x=>x.classList.toggle('on',x.dataset.model===exModel&&x.dataset.scn===exs.value));}
exm.querySelectorAll('button').forEach(b=>b.onclick=()=>{exModel=b.dataset.v;exm.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b));exAp();});exs.onchange=exAp;exAp();
document.querySelectorAll('.ln').forEach(l=>l.onclick=()=>{const o=l.classList.toggle('open');l.querySelector('.s').textContent=o?l.dataset.full:l.dataset.short||l.querySelector('.s').textContent;if(o&&!l.dataset.short){l.dataset.short=l.querySelector('.s').textContent;}});
document.querySelectorAll('a[data-goto]').forEach(a=>a.onclick=e=>{e.preventDefault();mth.value=a.dataset.goto;ap();show('prompts');});
document.querySelectorAll('a[data-scn]').forEach(a=>a.onclick=e=>{e.preventDefault();scn.value=a.dataset.scn;ap();show('prompts');});
</script></body></html>""")
    out = PROJECT_ROOT / "results" / "visuals" / "design.html"
    out.write_text("".join(H), encoding="utf-8")
    return out


if __name__ == "__main__":
    p = build()
    print(f"wrote {p} ({p.stat().st_size // 1024} KB)")

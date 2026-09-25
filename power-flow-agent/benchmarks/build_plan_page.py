#!/usr/bin/env python3
"""Build results/v2_plan.html: the evaluation design, as it will run, for approval before spending.

Everything on the page is generated from the code that the runner will use (methods/, llm/,
benchmarks/requests.py): the rows to run, the 40 scenarios with their reference calls, and for
every method the exact system prompt, the exact user message for any scenario, the tool schema
sent through function calling, the planner prompt, the verification conditions and the scoring
rules. Nothing is typed by hand except the section prose.

    .venv/bin/python benchmarks/build_plan_page.py
"""

from __future__ import annotations

import html
import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import methods  # noqa: E402
from benchmarks.evaluate_llms import perturbed_case  # noqa: E402
from benchmarks.requests import generate_requests  # noqa: E402
from llm import engine  # noqa: E402
from llm.prompt_variants import build_messages  # noqa: E402
from llm.tools import ToolContext, get_openai_tools  # noqa: E402
from llm.engine import LLMEngine, SessionState, verify_final_answer  # noqa: E402
from benchmarks.evaluate_llms import perturbing_dispatcher, declared_formulation_check  # noqa: E402
from benchmarks import metrics as bm, scoring as bs  # noqa: E402
from baselines import rule_based  # noqa: E402

E = html.escape
CASE, N, SEED, K, ROUNDS, TOOLS = "case14", 40, 0, 1, 8, "load_split"
MODELS = ["openrouter:openai/gpt-4o-mini", "openrouter:openai/gpt-5.6-sol"]

# rows of Table 6 and the companion probes, in table order; (label, runner name, rerun?, why)
ROWS = [
    ("Deterministic parser, no LLM", "rule_based", True, "no LLM; rerun for free on the current tool set"),
    ("Structured prompting", "llm_only:structured", None, "no tools; sol reused from 2026-09-21 (prompt unchanged); gpt-4o-mini rerun (its 2026-09-16 prompt predates a fix)"),
    ("Chain-of-thought prompting", "llm_only:cot", False, "no tools; reused (sol 2026-09-21, gpt-4o-mini 2026-09-18), prompt unchanged"),
    ("Structured, forced (§ cells, gpt-4o-mini)", "llm_only_forced:structured", True, "gpt-4o-mini only; rerun with the paper's answer prompt"),
    ("Formulation probe, structured (¶ cells)", "formulation_probe:structured", True, "catalogue now explains the N-1 arguments"),
    ("Formulation probe, chain-of-thought (¶ cells)", "formulation_probe:cot", True, "catalogue now explains the N-1 arguments"),
    ("Single-call", "single_call:structured", True, "tool schema now explains the N-1 arguments"),
    ("Plan-and-Act", "plan_act_nogate", True, "planner catalogue and tool schema now explain the N-1 arguments"),
    ("ReAct", "react_nogate", True, "tool schema now explains the N-1 arguments; messages stored"),
    ("PFAgent (ReAct + verification gate)", "pfagent", True, "tool schema; V6 now covers max_candidates; messages stored"),
]
COST = {"rule_based": (0, 0), "llm_only:structured": (0.02, 0), "llm_only:cot": (0, 0), "llm_only_forced:structured": (0.05, 0), "formulation_probe:structured": (0.02, 0.25), "formulation_probe:cot": (0.02, 0.3), "single_call:structured": (0.03, 0.5), "plan_act_nogate": (0.05, 0.7), "react_nogate": (0.1, 1.5), "pfagent": (0.1, 1.5)}

GATE = [
    ("V1", "converged", "The last power flow the agent ran converged."),
    ("V2", "balance", "Active-power balance of the reported state holds within tolerance."),
    ("V3", "no_isolated_buses", "No bus was left isolated by the network changes."),
    ("V4", "faithfulness", "Every unit-bearing number in the answer appears in a tool output."),
    ("V5", "currency", "Those numbers come from the solve made after the last network change, not an earlier one."),
    ("V6", "argument_grounding", "Every argument of a mutating tool traces to the request or to a prior tool output; since 2026-09-24 a positive max_candidates on the N-1 scan must also come from the request."),
    ("V7", "claims_from_tools", "The answer's claims match the agent's own last solved state."),
]
SCORING = [
    ("Formulation", "The executed tool calls (or, for the prompting rows, the operations the probe declared) match the reference calls in tool, identifiers, values and order. Read-only repeats are ignored; an optional argument the request did not pin is accepted unless it changes the result: an unrequested q_mvar, or an N-1 max_candidates below the branch count of the case (20 on IEEE 14)."),
    ("Solved", "Formulation exact and the reported numbers within tolerance of the reference (1e-3 p.u. on voltages, 1% on flows), answered by the method itself."),
    ("Escalated", "The method declared it could not answer: an explicit statement of inability, the round limit, or the verification gate rejecting every candidate. Takes precedence over the other two."),
    ("Wrong, unflagged", "The answer reports numbers that do not match the reference and does not say so. Solved + Escalated + Wrong = 100%."),
    ("Traceable", "Share of answers whose every number appears in a tool output from the last solve."),
    ("V_MAE / B_mean", "Bus-voltage MAE against the reference and the mean bus power-balance residual, over all requests and over the solved ones."),
]


FIG = re.compile(r'"figure_json":\s*"((?:[^"\\]|\\.)*)"')


def _src(obj: Any) -> str:
    try:
        return inspect.getsource(obj)
    except Exception as exc:  # pragma: no cover
        return f"(source not available: {exc})"


def tools_section() -> str:
    """One card per tool: description, inputs, the Python that runs it, and a real output on case14."""
    from solver.power_flow import SolverConfig

    ctx = ToolContext(session=SessionState(), solver_config=SolverConfig())
    disp = perturbing_dispatcher(ctx, seed=SEED, k=K)
    sample: Dict[str, Dict[str, Any]] = {
        "load_case": {"case_name": "case14"}, "run_powerflow": {}, "get_status": {}, "get_most_loaded_branch": {},
        "set_active_load": {"bus_id": 6, "p_mw": 14.7}, "set_load": {"bus_id": 9, "p_mw": 29.5, "q_mvar": 16.6},
        "disconnect_line": {"from_bus": 1, "to_bus": 5}, "reconnect_line": {"from_bus": 1, "to_bus": 5},
        "run_n1_contingency": {"top_k": 1, "criteria": "max_violations"}, "recommend_remedial_actions": {"max_actions": 2},
        "apply_remedial_action": {"action_index": 0, "confirmed": True}, "generate_plot": {"plot_type": "voltage_heatmap"},
    }
    order = ["load_case", "run_powerflow", "get_status", "get_most_loaded_branch", "set_active_load", "set_load", "disconnect_line", "reconnect_line", "run_n1_contingency", "recommend_remedial_actions", "apply_remedial_action", "generate_plot"]
    schema = {t["function"]["name"] if "function" in t else t["name"]: (t.get("function") or t) for t in get_openai_tools(variant=TOOLS)}
    out: List[str] = ["<section><h2>3b. The tools: what each one is, its inputs, the code that runs it, and a real output</h2><p>These are the only ways any method touches the network. The schema is what the model sees through function calling; the code is the handler the dispatcher runs (PandaPower underneath); the sample output was produced now on the same perturbed case14 the runs use (seed 0, k = 1), in the order listed, so state carries from one call to the next.</p>"]
    for name in order:
        fn = schema.get(name, {})
        props = (fn.get("parameters") or {}).get("properties") or {}
        req = set((fn.get("parameters") or {}).get("required") or [])
        inputs = "".join(f"<tr><td><code>{E(k)}</code>{'*' if k in req else ''}</td><td>{E(str(v.get('type')))}{' in {' + ', '.join(map(str, v['enum'])) + '}' if v.get('enum') else ''}</td><td>{E(str(v.get('default'))) if 'default' in v else ''}</td><td>{E(v.get('description') or '')}</td></tr>" for k, v in props.items()) or "<tr><td colspan='4' class='muted'>no inputs</td></tr>"
        handler = disp.handlers.get(name)
        code = _src(handler) if handler else "(no handler)"
        args = sample.get(name, {})
        try:
            result = disp.dispatch(name, args)
        except Exception as exc:
            result = f"(error: {exc})"
        result = FIG.sub(lambda m: f'"figure_json": "<plot, {len(m.group(1)) // 1024} KB, omitted>"', str(result))
        out.append(f"<h3><code>{E(name)}</code> <span class='muted'>· {E(fn.get('description') or '')}</span></h3><table><tr><th>input</th><th>type</th><th>default</th><th>meaning</th></tr>{inputs}</table>"
                   f"<details><summary>Python handler ({len(code.splitlines())} lines)</summary><pre>{E(code)}</pre></details>"
                   f"<details open><summary>real output for <code>{E(name)}({E(', '.join(f'{k}={v!r}' for k, v in args.items()))})</code></summary><pre>{E(result if len(result) < 6000 else result[:6000] + chr(10) + '... (' + str(len(result) - 6000) + ' more chars)')}</pre></details>")
    out.append("</section>")
    return "".join(out)


def code_section() -> str:
    parts = [
        ("Engine: one request, any architecture (run_with_trace)", LLMEngine.run_with_trace),
        ("ReAct loop (react_nogate, and PFAgent before its gate)", LLMEngine._run_react),
        ("Single-call (one round, no memory)", LLMEngine._run_single_call),
        ("Plan-and-Act (plan once, execute, answer)", LLMEngine._run_plan_act),
        ("How a run ends (escalation text, status)", LLMEngine._finish),
        ("Verification gate V1–V7 on the final answer (PFAgent)", verify_final_answer),
        ("V6 argument grounding", bm.argument_grounding_check),
        ("Deterministic parser: request → tool calls", rule_based._parse_clause),
        ("Deterministic parser: run", rule_based.run),
        ("Formulation comparator (the rules R0–R10)", bm.formulation_check),
        ("Declared formulation of the probes / no-tools rows", declared_formulation_check),
        ("Solved", bs.solved_check),
        ("Escalated / wrong unflagged (declared inability rule)", bs.escalation_check),
        ("Reporting: traceable numbers (V4 offline)", bm.faithful_numbers),
    ]
    out = ["<section><h2>8. The code behind every step, verbatim</h2><p>The actual Python from <code>llm/engine.py</code>, <code>baselines/rule_based.py</code>, <code>benchmarks/metrics.py</code> and <code>benchmarks/scoring.py</code>, as it is in this worktree. Docstrings carry the rules in words; the body is what runs.</p>"]
    for title, obj in parts:
        src = _src(obj)
        out.append(f"<details><summary><b>{E(title)}</b> · {E(getattr(obj, '__module__', ''))}.{E(getattr(obj, '__qualname__', getattr(obj, '__name__', '')))} · {len(src.splitlines())} lines</summary><pre>{E(src)}</pre></details>")
    out.append("</section>")
    return "".join(out)


def tools_block(variant: str) -> str:
    return E(json.dumps(get_openai_tools(variant=variant), indent=1, ensure_ascii=False))


def build() -> Path:
    reqs = generate_requests(CASE, N, SEED)
    net = perturbed_case(CASE, seed=SEED, k=K)
    css = """
:root{--line:#e3e7ee;--muted:#64748b;--acc:#2f5fd0;--ok:#1f9d55;--bad:#d53f3f}body{font:14px/1.5 Inter,-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#0f172a;margin:0;background:#f3f5f8}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid var(--line);padding:10px 22px;display:flex;gap:14px;align-items:center;flex-wrap:wrap;z-index:5}header h1{font-size:17px;margin:0}header label{font-size:13px}select{font:inherit;padding:4px 8px;max-width:640px}
main{padding:16px 22px;max-width:1500px;margin:0 auto}section{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 18px;margin-bottom:16px}h2{font-size:17px;margin:0 0 8px}h3{font-size:14.5px;margin:16px 0 6px}p{margin:6px 0}
table{border-collapse:collapse;font-size:13px;width:100%}th,td{border:1px solid var(--line);padding:5px 8px;vertical-align:top;text-align:left}th{background:#f6f8fb}td.y{background:#e6f4ea}td.n{background:#fdecec}td.x{color:var(--muted)}
pre{background:#fafbfd;border:1px solid var(--line);border-radius:8px;padding:10px;white-space:pre-wrap;word-break:break-word;font:12px/1.45 "JetBrains Mono",ui-monospace,Menlo,Consolas,monospace;margin:4px 0;max-height:480px;overflow:auto}
.muted{color:var(--muted);font-size:12.5px}.hid{display:none}details summary{cursor:pointer;color:var(--acc)}.tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:600;color:#fff;background:var(--acc)}.tag.reuse{background:var(--muted)}
"""
    H: List[str] = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>PFAgent v2 evaluation plan</title><style>{css}</style></head><body>"]
    H.append("<header><h1>PFAgent v2 evaluation plan · for approval</h1><label>Scenario shown in section 4: <select id='req'>" + "".join(f"<option value='{r.id}'>{i+1:02d} · {E(r.difficulty)} · {E(r.text)}</option>" for i, r in enumerate(reqs)) + "</select></label><span class='muted'>Generated from the code that will run; nothing is spent until you approve.</span></header><main>")

    # 1 summary
    tot_mini = sum(COST[r][0] for _, r, rerun, _ in ROWS if rerun is not False)
    tot_sol = sum(COST[r][1] for _, r, rerun, _ in ROWS if rerun is not False)
    H.append(f"""<section><h2>1. What v2 fixes, in one rule each</h2>
<ul><li><b>One tool set</b>: <code>{TOOLS}</code>, whose N-1 arguments now carry a description (0 = scan every branch). No run uses the old set.</li>
<li><b>One set of prompts</b> with the same information in every row: the planner and the probe see each argument's allowed values and the indexing rule, as ReAct and PFAgent do through the schema and the agent system prompt. The no-tools answer prompts are the paper's, unchanged.</li>
<li><b>One scoring version</b>: current comparator (a narrowed N-1 scan is a formulation error) and verification gate (V6 covers max_candidates).</li>
<li><b>Every trace stores the exact messages sent</b>, so the transcript is the real exchange, never rebuilt.</li></ul>
<p><b>Common parameters</b>: IEEE 14-bus, N = {N} generated requests, perturbation seed {SEED}, k = {K}, up to {ROUNDS} tool rounds, temperature 0, models {', '.join(f'<code>{m}</code>' for m in MODELS)}. Output: <code>results/ieee14/2026-09-24/&lt;model&gt;/&lt;method&gt;__v2/</code> with REPORT.md, summary.csv, traces (transcript, narrative, figure, JSON) and raw/.</p>
<p><b>Estimated cost</b>: gpt-4o-mini about ${tot_mini:.2f}, gpt-5.6-sol about ${tot_sol:.2f}; total about ${tot_mini + tot_sol:.2f} of the credit left (about 16 USD). Real cost on sol has run 1.5 to 2 times the estimate before.</p></section>""")

    # 2 rows
    H.append("<section><h2>2. Rows to run</h2><table><tr><th>Table 6 row</th><th>runner name</th><th>what it is</th><th>run now?</th><th>why</th><th>cost mini / sol</th></tr>")
    for label, runner, rerun, why in ROWS:
        m = methods.get_method(runner)
        tag = "<span class='tag'>run</span>" if rerun else ("<span class='tag reuse'>reuse</span>" if rerun is False else "<span class='tag'>run gpt-4o-mini</span> <span class='tag reuse'>reuse sol</span>")
        H.append(f"<tr><td><b>{E(label)}</b></td><td><code>{E(runner)}</code></td><td>{E(m.description)}</td><td>{tag}</td><td>{E(why)}</td><td>${COST[runner][0]:.2f} / ${COST[runner][1]:.2f}</td></tr>")
    H.append("</table><p class='muted'>Human with solver is not an LLM run (human_run.py). Few-shot and RAG variants are not in Table 6 and are not run.</p></section>")

    # 3 scenarios
    H.append(f"<section><h2>3. The {N} scenarios (same for every row and both models)</h2><p>Generated by <code>benchmarks/requests.py</code> from (case14, N=40, seed 0): four difficulties, ten each. The reference calls define Formulation; the reference solution (PandaPower on the same perturbed case) defines Solved.</p><table><tr><th>#</th><th>id</th><th>difficulty</th><th>request</th><th>reference calls</th><th>expected</th></tr>")
    for i, r in enumerate(reqs, start=1):
        calls = " → ".join(f"{c['tool']}(" + ", ".join(f"{k}={v}" for k, v in (c.get('args') or {}).items()) + ")" for c in r.intended_calls)
        H.append(f"<tr><td>{i}</td><td><code>{E(r.id)}</code></td><td>{E(r.difficulty)}</td><td>{E(r.text)}</td><td><code>{E(calls)}</code></td><td>{E(r.expected_outcome)}</td></tr>")
    H.append("</table></section>")
    H.append(tools_section())

    # 4 per method: exact messages
    H.append("<section><h2>4. What each method receives, exactly</h2><p>Pick a scenario in the header. For each row: the system prompt (hash as it will be stamped on the run), the full user message for that scenario, the tool schema sent through function calling, and the planner prompt where it exists. Long blocks are collapsed; expand to read them whole.</p>")
    matrix_rows = []
    cols = ["case tables in the prompt", "tool schema (function calling)", "text catalogue", "allowed values (enum)", "1-based / (0-based) rule", "sees tool outputs", "abstention clause", "gate"]
    for label, runner, rerun, _ in ROWS:
        m = methods.get_method(runner)
        H.append(f"<h3>{E(label)} <span class='muted'>· {E(runner)}</span></h3>")
        sp = methods.system_prompt_for(m, tool_variant=TOOLS)
        planner = methods.planner_prompt_for(m, tool_variant=TOOLS) if m.architecture == "plan_act" else None
        if m.kind == "rule_based":
            H.append("<p class='muted'>No LLM: a regex parser maps the request to tool calls and the solver runs them (baselines/rule_based.py). Nothing is sent to a model.</p>")
        if sp:
            H.append(f"<details><summary>system prompt · hash {methods.prompt_hash(sp)} · {len(sp)} chars</summary><pre>{E(sp)}</pre></details>")
        if planner:
            H.append(f"<details><summary>planner system prompt (the planning call sends this plus the request) · hash {methods.prompt_hash(planner)}</summary><pre>{E(planner)}</pre></details>")
        # user messages per scenario
        user_msgs: Dict[str, str] = {}
        if m.kind == "llm_only":
            for r in reqs:
                user_msgs[r.id] = build_messages(m.strategy or "structured", "llm_only", r.text, net, CASE, forced=bool(m.forced), probe=bool(m.probe), tool_variant=TOOLS)[1]["content"]
        elif m.architecture == "single_call":
            for r in reqs:
                user_msgs[r.id] = build_messages(m.strategy or "structured", "single_call", r.text, net, CASE, tool_variant=TOOLS)[1]["content"]
        elif m.uses_llm:
            for r in reqs:
                user_msgs[r.id] = r.text
        if user_msgs:
            H.append("<details open><summary>user message for the selected scenario</summary>" + "".join(f"<pre class='um' data-req='{rid}'>{E(txt)}</pre>" for rid, txt in user_msgs.items()) + "</details>")
        if m.uses_tools and m.uses_llm:
            H.append(f"<details><summary>tool schema sent through function calling ({TOOLS})</summary><pre>{tools_block(TOOLS)}</pre></details>")
        # matrix
        sysm = (sp or "") + (planner or "")
        u0 = user_msgs.get(reqs[0].id, "") if user_msgs else ""
        tools = get_openai_tools(variant=TOOLS) if (m.uses_tools and m.uses_llm) else []
        row = {
            cols[0]: "yes" if ("### Node Data" in u0 or "## System Data" in u0) else ("n/a" if m.kind == "rule_based" else "no"),
            cols[1]: "yes" if tools else ("n/a" if m.kind == "rule_based" else "no"),
            cols[2]: "yes" if ("Available tools:" in sysm or "Available operations:" in u0) else "no",
            cols[3]: "yes" if (tools or " in {" in u0 or " in {" in sysm) else ("n/a" if m.kind == "rule_based" else "no"),
            cols[4]: "yes" if "0-based" in sysm else ("fixed rules" if m.kind == "rule_based" else "no"),
            cols[5]: "yes, up to 8 rounds" if m.architecture == "react" else ("no" if m.uses_tools else "n/a"),
            cols[6]: "yes" if "set `converged` to false" in sysm else ("removed" if m.forced else "n/a"),
            cols[7]: "final V1–V7" if m.final_gate else ("observation" if (m.gate and m.uses_tools) else "no"),
        }
        matrix_rows.append((label, row))
    H.append("</section>")

    # 5 information matrix
    H.append("<section><h2>5. Information matrix, derived from section 4</h2><table><tr><th>row</th>" + "".join(f"<th>{E(c)}</th>" for c in cols) + "</tr>")
    for label, row in matrix_rows:
        H.append(f"<tr><td><b>{E(label)}</b></td>" + "".join(f"<td class='{'y' if v.startswith('yes') else ('x' if v in ('n/a', 'fixed rules') else 'n')}'>{E(v)}</td>" for v in row.values()) + "</tr>")
    H.append("</table><p class='muted'>Green: the row receives it. Red: it does not. Grey: does not apply. The prompting rows deliberately have no tools; their Formulation is measured by the probes, which receive the catalogue with allowed values and the indexing rule.</p></section>")

    # 6 gate + scoring
    H.append("<section><h2>6. Verification gate (PFAgent) and scoring (every row)</h2><h3>Gate conditions on the final answer</h3><table><tr><th>label</th><th>key</th><th>condition</th></tr>" + "".join(f"<tr><td>{a}</td><td><code>{b}</code></td><td>{E(c)}</td></tr>" for a, b, c in GATE) + "</table><p class='muted'>A rejected answer is retried once with the failed conditions spelled out; a second failure escalates. ReAct and Plan-and-Act run without this gate; single-call runs with the observation gate on tool outputs only.</p><h3>Scoring rules</h3><table><tr><th>metric</th><th>definition</th></tr>" + "".join(f"<tr><td><b>{E(a)}</b></td><td>{E(b)}</td></tr>" for a, b in SCORING) + "</table></section>")

    H.append(code_section())

    # 7 commands
    cmds = []
    for label, runner, rerun, _ in ROWS:
        m = methods.get_method(runner)
        if rerun is False:
            continue
        if not m.uses_llm:
            cmds.append(f".venv/bin/python run.py run --method {m.folder} --case ieee14 --n 40 --tag v2")
        elif rerun is None:
            cmds.append(f".venv/bin/python run.py run --method {m.folder} --model openrouter:openai/gpt-4o-mini --case ieee14 --n 40 --tag v2")
        elif runner == "llm_only_forced:structured":
            cmds.append(f".venv/bin/python run.py run --method {m.folder} --model openrouter:openai/gpt-4o-mini --case ieee14 --n 40 --tag v2")
        else:
            cmds.append(f".venv/bin/python run.py run --method {m.folder} --model openrouter:openai/gpt-4o-mini --model openrouter:openai/gpt-5.6-sol --case ieee14 --n 40 --tag v2")
    H.append("<section><h2>7. Exactly what will be executed, in order</h2><p>gpt-4o-mini runs first within each command; each run is rescored offline and rendered before the next starts. Nothing starts until you say so.</p><pre>" + E("\n".join(cmds)) + "</pre><p>Afterwards: Table 6 in <code>borrador</code>, <code>results/table6.html</code> and <code>benchmarks/build_paper_tables.py</code> point only to the <code>__v2</code> folders (plus the reused prompting rows named above).</p></section>")
    H.append("</main><script>const s=document.getElementById('req');function ap(){document.querySelectorAll('.um').forEach(p=>p.classList.toggle('hid',p.dataset.req!==s.value));}s.onchange=ap;ap();</script></body></html>")
    out = PROJECT_ROOT / "results" / "v2_plan.html"
    out.write_text("".join(H), encoding="utf-8")
    return out


if __name__ == "__main__":
    p = build()
    print(f"wrote {p} ({p.stat().st_size // 1024} KB)")

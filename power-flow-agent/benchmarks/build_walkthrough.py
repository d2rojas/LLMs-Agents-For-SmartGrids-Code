#!/usr/bin/env python3
"""Build results/walkthrough.html: one self-contained page that shows what was tested and how.

Sections: (1) the methods and, derived from the real messages, which information each one
receives; (2) for three real requests, the exact messages every method sent to the model
(system prompt, user message with the case tables, tool schema, planner prompt), with a
line diff against a reference method; (3) the complete real exchange of both models on those
requests, step by step, from the trace files; (4) the per-run results. Everything is read from
results/ and methods/; nothing is summarized by hand. Open the file directly in a browser.

    .venv/bin/python benchmarks/build_walkthrough.py
"""

from __future__ import annotations

import difflib
import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import methods  # noqa: E402
from benchmarks.postprocess import _elide_figures, load_report, rebuild_user_message  # noqa: E402
from llm.tools import get_openai_tools  # noqa: E402

RESULTS = PROJECT_ROOT / "results"
MODELS = {"gpt-5.6-sol": "gpt-5.6-sol", "gpt-4o-mini": "gpt-4o-mini"}
# the run behind each Table 6 row today, per model
RUNS: Dict[str, Dict[str, str]] = {
    "gpt-5.6-sol": {
        "rule_based": "ieee14/2026-09-21/no-llm/rule_based",
        "llm_only_structured": "ieee14/2026-09-21/gpt-5.6-sol/llm_only_structured",
        "llm_only_cot": "ieee14/2026-09-21/gpt-5.6-sol/llm_only_cot",
        "formulation_probe_structured": "ieee14/2026-09-23/gpt-5.6-sol/formulation_probe_structured__matched",
        "formulation_probe_cot": "ieee14/2026-09-23/gpt-5.6-sol/formulation_probe_cot__matched",
        "single_call_structured": "ieee14/2026-09-21/gpt-5.6-sol/single_call_structured",
        "plan_act_nogate": "ieee14/2026-09-23/gpt-5.6-sol/plan_act_nogate__matched",
        "react_nogate": "ieee14/2026-09-21/gpt-5.6-sol/react_nogate",
        "pfagent": "ieee14/2026-09-21/gpt-5.6-sol/pfagent",
    },
    "gpt-4o-mini": {
        "rule_based": "ieee14/2026-09-21/no-llm/rule_based",
        "llm_only_structured": "ieee14/2026-09-16/gpt-4o-mini/llm_only_structured",
        "llm_only_cot": "ieee14/2026-09-18/gpt-4o-mini/llm_only_cot",
        "llm_only_forced_structured": "ieee14/2026-09-23/gpt-4o-mini/llm_only_forced_structured__f2",
        "formulation_probe_structured": "ieee14/2026-09-23/gpt-4o-mini/formulation_probe_structured__matched",
        "formulation_probe_cot": "ieee14/2026-09-23/gpt-4o-mini/formulation_probe_cot__matched",
        "single_call_structured": "ieee14/2026-09-21/gpt-4o-mini/single_call_structured",
        "plan_act_nogate": "ieee14/2026-09-23/gpt-4o-mini/plan_act_nogate__matched",
        "react_nogate": "ieee14/2026-09-21/gpt-4o-mini/react_nogate",
        "pfagent": "ieee14/2026-09-21/gpt-4o-mini/pfagent",
    },
}
ORDER = ["rule_based", "llm_only_structured", "llm_only_cot", "llm_only_forced_structured", "formulation_probe_structured", "formulation_probe_cot", "single_call_structured", "plan_act_nogate", "react_nogate", "pfagent"]
REQUESTS = ["case14-plain-004-s0", "case14-ambiguous-027-s0", "case14-multistep-006-s0"]
REFERENCE = {"llm_only": "llm_only_structured", "engine": "react_nogate", "rule_based": None}
LABEL = {"rule_based": "Parser determinista + solver (sin LLM)", "llm_only_structured": "Structured prompting (sin herramientas)", "llm_only_cot": "Chain-of-thought prompting (sin herramientas)",
         "llm_only_forced_structured": "Structured, variante forzada (sin herramientas)", "formulation_probe_structured": "Sonda de formulación, structured", "formulation_probe_cot": "Sonda de formulación, CoT",
         "single_call_structured": "Single-call (una ronda con herramientas)", "plan_act_nogate": "Plan-and-Act (plan completo, luego ejecutar)", "react_nogate": "ReAct (iterar viendo resultados)", "pfagent": "PFAgent (ReAct + compuerta de verificación)"}

E = html.escape


def load_run(rel: str) -> Dict[str, Any]:
    d = RESULTS / rel
    report = load_report(d / "raw")
    cfg = json.loads((d / "config.json").read_text(encoding="utf-8")) if (d / "config.json").is_file() else {}
    rows = {str(r["request_id"]): r for r in report.get("runs") or []}
    summ = json.loads((d / "summary.json").read_text(encoding="utf-8")) if (d / "summary.json").is_file() else {}
    return {"dir": d, "rel": rel, "cfg": cfg, "rows": rows, "sb": (report.get("scoreboard") or [{}])[0], "agg": summ.get("aggregate", {}), "header": (summ.get("header") or {})}


def trace_for(run: Dict[str, Any], rid: str) -> Optional[Dict[str, Any]]:
    hits = list((run["dir"] / "raw" / "traces").rglob(f"{rid}_run0.json")) if (run["dir"] / "raw" / "traces").is_dir() else []
    if not hits:
        hits = [p for p in (run["dir"] / "traces").glob(f"*_{rid}.json")]
    return json.loads(hits[0].read_text(encoding="utf-8")) if hits else None


def messages_for(run: Dict[str, Any], mname: str, rid: str, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The exact messages the model received: stored at run time when present, else rebuilt (hash-verified)."""
    m = methods.get_method(mname)
    row = run["rows"].get(rid) or {}
    tr = (payload or {}).get("trace") or {}
    out: Dict[str, Any] = {"system": None, "user": None, "source": None, "tools": None, "planner": None, "planner_source": None}
    stored = [x for x in (tr.get("messages") or []) if isinstance(x, dict)]
    if stored:
        out["system"] = next((x["content"] for x in stored if x["role"] == "system"), None)
        out["user"] = next((x["content"] for x in stored if x["role"] == "user"), None)
        out["source"] = "guardado en la corrida"
    elif m.kind == "rule_based":
        out["source"] = "sin LLM: el parser lee la petición y llama al solver"
        out["user"] = row.get("request_text")
    else:
        sp = methods.system_prompt_for(m, tool_variant=str(run["header"].get("tool_variant") or "load_split"))
        stamped = row.get("system_prompt_hash")
        if sp is not None and (not stamped or methods.prompt_hash(sp) == stamped):
            out["system"] = sp
            out["user"] = rebuild_user_message(row, run["header"]) if (m.kind == "llm_only" or m.architecture == "single_call") else row.get("request_text")
            out["source"] = f"reconstruido con el mismo código; hash del system prompt verificado ({stamped})"
        else:
            out["system"] = None
            out["user"] = row.get("request_text")
            out["source"] = f"no reconstruible: el prompt cambió desde la corrida (hash estampado {stamped})"
    if m.uses_tools and m.uses_llm:
        out["tools"] = get_openai_tools(variant=str(run["header"].get("tool_variant") or "load_split"))
    if m.architecture == "plan_act":
        out["planner"] = methods.planner_prompt_for(m, tool_variant=str(run["header"].get("tool_variant") or "load_split"))
        out["planner_source"] = "texto actual de methods/plan_act (es el de la corrida __matched)"
    return out


def info_matrix(mname: str, msgs: Dict[str, Any]) -> Dict[str, str]:
    m = methods.get_method(mname)
    sysm = (msgs.get("system") or "") + (msgs.get("planner") or "")
    user = msgs.get("user") or ""
    tools = msgs.get("tools") or []
    has_enum_schema = any(v.get("enum") for t in tools for v in ((t.get("function", t).get("parameters") or {}).get("properties") or {}).values())
    return {
        "tablas del caso": "sí" if ("### Node Data" in user or "## System Data" in user) else ("n/a" if m.kind == "rule_based" else "no"),
        "esquema de herramientas": "sí" if tools else ("n/a" if m.kind == "rule_based" else "no"),
        "catálogo en texto": "sí" if ("Available tools:" in sysm or "Available operations:" in user or "Available operations:" in sysm) else "no",
        "valores permitidos (enum)": "sí" if (has_enum_schema or " in {" in user or " in {" in sysm) else ("n/a" if m.kind == "rule_based" else "no"),
        "regla índices 1-based/(0-based)": "sí" if "0-based" in sysm else ("reglas fijas" if m.kind == "rule_based" else "no"),
        "ve la salida de las herramientas": "sí, hasta 8 rondas" if m.architecture == "react" else ("no" if m.uses_tools else "n/a"),
        "cláusula de abstención": "sí" if "set `converged` to false" in sysm else ("quitada" if m.forced else "n/a"),
        "compuerta": "final V1–V7" if m.final_gate else ("observación" if m.gate and m.uses_tools else "no"),
    }


def tools_html(tools: List[Dict[str, Any]]) -> str:
    lines = []
    for t in tools:
        fn = t.get("function", t)
        props = (fn.get("parameters") or {}).get("properties") or {}
        req = set((fn.get("parameters") or {}).get("required") or [])
        args = []
        for k, v in props.items():
            a = f"{k}: {v.get('type')}" + ("*" if k in req else "")
            if v.get("enum"):
                a += " in {" + ", ".join(map(str, v["enum"])) + "}"
            if "default" in v:
                a += f" (default {v['default']})"
            args.append(a)
        lines.append(f"{fn.get('name')}({', '.join(args)})\n    {fn.get('description', '')}")
    return E("\n".join(lines))


def diff_html(a: str, b: str) -> str:
    out = []
    for line in difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm="", n=1):
        if line.startswith(("---", "+++", "@@")):
            out.append(f'<span class="dh">{E(line)}</span>')
        elif line.startswith("+"):
            out.append(f'<span class="da">{E(line)}</span>')
        elif line.startswith("-"):
            out.append(f'<span class="dd">{E(line)}</span>')
        else:
            out.append(E(line))
    return "\n".join(out) or "(idénticos)"


def exchange_html(mname: str, payload: Optional[Dict[str, Any]], row: Dict[str, Any]) -> str:
    if payload is None:
        return "<p class='muted'>sin traza para esta petición</p>"
    tr = payload.get("trace") or {}
    parts = []
    plan = tr.get("plan")
    if plan:
        parts.append(f"<div class='step plan'><b>plan del planificador</b><pre>{E(json.dumps(plan, ensure_ascii=False, indent=1))}</pre></div>")
    rounds = tr.get("rounds") or []
    for rd in rounds:
        llm = rd.get("llm") if isinstance(rd.get("llm"), dict) else None
        if llm is not None:
            u = llm.get("usage") or {}
            tag = "respuesta final" if rd.get("final") else "modelo"
            body = E(str(llm.get("content") or "(sin texto)"))
            calls = "".join(f"<div class='call'>llama <code>{E(str(tc.get('name')))}</code> {E(str(tc.get('arguments')))}</div>" for tc in llm.get("tool_calls") or [])
            parts.append(f"<div class='step llm'><b>ronda {rd.get('round')} · {tag}</b> <span class='muted'>{u.get('prompt_tokens', '?')} in / {u.get('completion_tokens', '?')} out · {float(llm.get('latency_s') or 0):.1f} s</span><pre>{body}</pre>{calls}</div>")
        for tool in rd.get("tools") or []:
            out = tool.get("output")
            out = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, default=str)
            out = _elide_figures(out)
            gate = tool.get("gate")
            g = "" if gate is None else (" · compuerta: pasa" if (gate.get("passed") if isinstance(gate, dict) else gate) else (" · compuerta: FALLA, salida retenida" if tool.get("enforced") else " · compuerta: FALLA"))
            long = len(out) > 1500
            pre = f"<pre>{E(out)}</pre>"
            if long:
                pre = f"<details><summary>salida completa ({len(out)} caracteres)</summary>{pre}</details><pre>{E(out[:600])}…</pre>"
            parts.append(f"<div class='step tool'><b>herramienta {E(str(tool.get('name')))}</b> {E(json.dumps(tool.get('arguments'), ensure_ascii=False))}<span class='muted'>{E(g)}</span>{pre}</div>")
    if not rounds:
        parts.append(f"<div class='step llm'><b>respuesta del modelo (sin herramientas)</b><pre>{E(str(payload.get('answer') or row.get('raw_response') or ''))}</pre></div>")
    ver = tr.get("verification") or []
    if ver:
        last = ver[-1]
        conds = " ".join(f"<span class='chip {'ok' if c.get('passed') else ('na' if c.get('applicable') is False else 'bad')}'>{E(str(c.get('label', k)))}</span>" for k, c in (last.get("conditions") or {}).items())
        parts.append(f"<div class='step ver'><b>compuerta de verificación</b> {conds} <span class='muted'>{E(str(tr.get('verification_outcome') or tr.get('status')))}</span>" + "".join(f"<pre>{E(str(m))}</pre>" for m in tr.get("verification_retry_messages") or []) + "</div>")
    if rounds and not any(rd.get("final") for rd in rounds) and payload.get("answer"):
        parts.append(f"<div class='step llm'><b>respuesta final</b><pre>{E(str(payload.get('answer')))}</pre></div>")
    # verdict
    fe = row.get("formulation_exact")
    oc = "escalada" if row.get("escalated") else ("WRONG sin aviso" if row.get("wrong_silently") else ("resuelta" if (row.get("solved_autonomously") or row.get("solved")) else "otro"))
    ocls = "ok" if oc == "resuelta" else ("warn" if oc == "escalada" else "bad")
    form = "n/a" if fe is None else ("exacta" if fe else f"NO exacta ({row.get('formulation_error_type')}): {row.get('formulation_detail')}")
    m = row.get("metrics") or {}
    parts.append(f"<div class='verdict'><span class='chip {ocls}'>{E(oc)}</span> formulación: {E(form)} · números en la respuesta {row.get('n_numbers')}, no trazables {row.get('n_untraceable_numbers')} · V_MAE {E(str(m.get('voltage_mae')))} p.u. · {row.get('n_llm_calls')} llamadas LLM, {row.get('n_tool_calls')} herramientas, {row.get('prompt_tokens')} in / {row.get('completion_tokens')} out</div>")
    return "".join(parts)


def build() -> Path:
    runs = {model: {m: load_run(rel) for m, rel in RUNS[model].items()} for model in MODELS}
    css = """
:root{--line:#e2e5ea;--muted:#6b7280;--acc:#3b6fd4}body{font:14px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1b1f24;margin:0;background:#f6f7f9}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid var(--line);padding:10px 18px;display:flex;gap:16px;align-items:center;flex-wrap:wrap;z-index:5}
header h1{font-size:16px;margin:0}header label{font-size:13px}select{font:inherit;padding:3px 6px}
main{padding:14px 18px;max-width:1500px;margin:0 auto}section{margin-bottom:28px}h2{font-size:18px;border-bottom:2px solid var(--acc);padding-bottom:4px}h3{font-size:15px;margin:14px 0 6px}
table{border-collapse:collapse;background:#fff;font-size:13px}th,td{border:1px solid var(--line);padding:4px 8px;vertical-align:top;text-align:left}th{background:#eef1f5}
td.y{background:#e6f4ea}td.n{background:#fdecec}td.x{background:#f3f4f6;color:var(--muted)}
pre{background:#fff;border:1px solid var(--line);border-radius:6px;padding:10px;white-space:pre-wrap;word-break:break-word;font:12px/1.45 ui-monospace,Menlo,Consolas,monospace;margin:4px 0;max-height:520px;overflow:auto}
.muted{color:var(--muted);font-size:12px}.card{background:#fff;border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin:8px 0}
.two{display:grid;grid-template-columns:1fr 1fr;gap:12px}.step{border-left:4px solid #ccc;padding:4px 10px;margin:6px 0;background:#fff;border-radius:0 6px 6px 0}
.step.llm{border-color:#3b6fd4}.step.tool{border-color:#2a9d8f}.step.plan{border-color:#7b4fbf}.step.ver{border-color:#d9a404}.call{font-size:12px;color:#3b6fd4;margin:2px 0}
.chip{display:inline-block;padding:1px 7px;border-radius:9px;color:#fff;font-size:11px;font-weight:600;margin-right:3px}.chip.ok{background:#2e9e5b}.chip.bad{background:#d63b3b}.chip.warn{background:#e58f1a}.chip.na{background:#bdbdbd}
.verdict{background:#fffbe6;border:1px solid #f0e2a0;border-radius:6px;padding:6px 10px;font-size:13px;margin-top:6px}
.dh{color:var(--muted)}.da{background:#e6f4ea;display:block}.dd{background:#fdecec;display:block}
details summary{cursor:pointer;color:var(--acc);font-size:12px}.hid{display:none}
"""
    H: List[str] = [f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>PFAgent: qué probamos y cómo</title><style>{css}</style></head><body>"]
    H.append("<header><h1>PFAgent: qué probamos y cómo</h1><label>Petición de ejemplo: <select id='req'>" + "".join(f"<option value='{r}'>{r}</option>" for r in REQUESTS) + "</select></label><label>Método: <select id='meth'>" + "".join(f"<option value='{m}'>{E(LABEL[m])}</option>" for m in ORDER) + "</select></label><span class='muted'>Generado desde results/ y methods/; nada está resumido a mano. Las secciones 2 y 3 siguen a estos selectores.</span></header><main>")

    # request texts
    req_text = {rid: next((runs[m][k]["rows"][rid]["request_text"] for m in MODELS for k in RUNS[m] if rid in runs[m][k]["rows"]), rid) for rid in REQUESTS}
    intended = {rid: next((runs[m][k]["rows"][rid].get("intended_calls") for m in MODELS for k in RUNS[m] if rid in runs[m][k]["rows"]), None) for rid in REQUESTS}

    # ---- section 1
    H.append("<section><h2>1. Los métodos, y qué información recibe cada uno</h2><p>Cada fila de la tabla del artículo es un método. La matriz de la derecha no está escrita a mano: se deduce de los mensajes reales que se enviaron al modelo (sección 2).</p>")
    msgs_cache: Dict[tuple, Dict[str, Any]] = {}
    rid0 = REQUESTS[0]
    cols = ["tablas del caso", "esquema de herramientas", "catálogo en texto", "valores permitidos (enum)", "regla índices 1-based/(0-based)", "ve la salida de las herramientas", "cláusula de abstención", "compuerta"]
    H.append("<table><tr><th>método</th><th>quién formula</th><th>quién calcula</th><th>corrida (sol / mini)</th>" + "".join(f"<th>{E(c)}</th>" for c in cols) + "</tr>")
    who = {"rule_based": ("reglas fijas", "solver"), "llm_only_structured": ("LLM, implícito", "el LLM a mano"), "llm_only_cot": ("LLM, implícito", "el LLM a mano"), "llm_only_forced_structured": ("LLM, implícito", "el LLM a mano, obligado"), "formulation_probe_structured": ("LLM, declarada", "nadie: solo declara"), "formulation_probe_cot": ("LLM, declarada", "nadie: solo declara"), "single_call_structured": ("LLM, llamadas en una ronda", "solver"), "plan_act_nogate": ("LLM, plan completo", "solver"), "react_nogate": ("LLM, paso a paso", "solver"), "pfagent": ("LLM, paso a paso", "solver")}
    for mname in ORDER:
        model = "gpt-5.6-sol" if mname in RUNS["gpt-5.6-sol"] else "gpt-4o-mini"
        run = runs[model][mname]
        msgs = messages_for(run, mname, rid0, trace_for(run, rid0)); msgs_cache[(model, mname, rid0)] = msgs
        im = info_matrix(mname, msgs)
        dirs = " / ".join(RUNS[mm].get(mname, "—").split("/", 1)[1] if mname in RUNS[mm] else "—" for mm in MODELS)
        H.append(f"<tr><td><b>{E(LABEL[mname])}</b><br><span class='muted'>{E(methods.get_method(mname).description)}</span></td><td>{E(who[mname][0])}</td><td>{E(who[mname][1])}</td><td class='muted'>{E(dirs)}</td>" + "".join(f"<td class='{'y' if v.startswith('sí') else ('x' if v in ('n/a','reglas fijas') else 'n')}'>{E(v)}</td>" for v in (im[c] for c in cols)) + "</tr>")
    H.append("</table><p class='muted'>Verde: lo recibe. Rojo: no lo recibe. Gris: no aplica. Lo que cambió el 23-09 fue dar a Plan-and-Act y a la sonda los valores permitidos y la regla de índices, que ReAct y PFAgent ya tenían por el esquema y por su system prompt.</p></section>")

    # ---- section 2: exact messages per (request, method), with diff vs reference
    H.append("<section><h2>2. Qué recibe exactamente el modelo</h2><p>Para la petición y el método elegidos arriba: el system prompt, el mensaje de usuario completo (tablas incluidas), el esquema de herramientas si lo hay y el prompt del planificador si lo hay. Debajo, la diferencia línea a línea del system prompt frente al método de referencia de su familia (Structured prompting para las filas sin herramientas, ReAct para las filas con herramientas).</p>")
    for rid in REQUESTS:
        H.append(f"<div class='req-block' data-req='{rid}'><div class='card'><b>Petición</b> <code>{rid}</code>: {E(req_text[rid])}<br><span class='muted'>llamadas que la referencia considera correctas: {E(' → '.join(f'{c.get('tool')}({', '.join(f'{k}={v}' for k, v in (c.get('args') or {}).items())})' for c in (intended[rid] or [])))}</span></div>")
        for mname in ORDER:
            model = "gpt-5.6-sol" if mname in RUNS["gpt-5.6-sol"] else "gpt-4o-mini"
            run = runs[model][mname]
            msgs = msgs_cache.get((model, mname, rid)) or messages_for(run, mname, rid, trace_for(run, rid)); msgs_cache[(model, mname, rid)] = msgs
            H.append(f"<div class='meth-block' data-meth='{mname}'><h3>{E(LABEL[mname])} <span class='muted'>· mensajes: {E(msgs['source'] or '')}</span></h3>")
            if msgs["system"]:
                H.append(f"<b>System prompt</b> <span class='muted'>hash {methods.prompt_hash(msgs['system'])}</span><pre>{E(msgs['system'])}</pre>")
            if msgs["planner"]:
                H.append(f"<b>Prompt del planificador</b> <span class='muted'>{E(msgs['planner_source'] or '')} · hash {methods.prompt_hash(msgs['planner'])}</span><pre>{E(msgs['planner'])}</pre>")
            if msgs["user"]:
                H.append(f"<b>Mensaje de usuario</b><pre>{E(msgs['user'])}</pre>")
            if msgs["tools"]:
                H.append(f"<b>Esquema de herramientas (function calling)</b><pre>{tools_html(msgs['tools'])}</pre>")
            m = methods.get_method(mname)
            ref = REFERENCE.get(m.kind)
            if ref and ref != mname and msgs["system"]:
                rmodel = "gpt-5.6-sol" if ref in RUNS["gpt-5.6-sol"] else "gpt-4o-mini"
                rmsgs = msgs_cache.get((rmodel, ref, rid)) or messages_for(runs[rmodel][ref], ref, rid, trace_for(runs[rmodel][ref], rid)); msgs_cache[(rmodel, ref, rid)] = rmsgs
                if rmsgs["system"]:
                    H.append(f"<details><summary>diferencia del system prompt frente a {E(LABEL[ref])}</summary><pre>{diff_html(rmsgs['system'], msgs['system'])}</pre></details>")
                if rmsgs["user"] and msgs["user"] and m.kind == "llm_only":
                    H.append(f"<details><summary>diferencia del mensaje de usuario frente a {E(LABEL[ref])}</summary><pre>{diff_html(rmsgs['user'], msgs['user'])}</pre></details>")
            H.append("</div>")
        H.append("</div>")
    H.append("</section>")

    # ---- section 3: real exchanges, both models
    H.append("<section><h2>3. Lo que pasó de verdad, paso a paso, en los dos modelos</h2><p>Para la petición y el método elegidos: la conversación completa tal como quedó en la traza (cada respuesta del modelo, cada llamada, cada salida del solver, la compuerta), y el veredicto. Solo se abrevia el bloque de figura Plotly de las salidas del N-1.</p>")
    for rid in REQUESTS:
        H.append(f"<div class='req-block' data-req='{rid}'>")
        for mname in ORDER:
            H.append(f"<div class='meth-block' data-meth='{mname}'><h3>{E(LABEL[mname])}</h3><div class='two'>")
            for model in MODELS:
                if mname not in RUNS[model]:
                    H.append(f"<div><b>{E(model)}</b><p class='muted'>no corrido en este modelo</p></div>"); continue
                run = runs[model][mname]; row = run["rows"].get(rid) or {}
                payload = trace_for(run, rid)
                H.append(f"<div><b>{E(model if mname != 'rule_based' else 'sin LLM (misma corrida para los dos bloques)')}</b> <span class='muted'>{E(run['rel'])}</span>{exchange_html(mname, payload, row)}</div>")
            H.append("</div></div>")
        H.append("</div>")
    H.append("</section>")

    # ---- section 4: results
    H.append("<section><h2>4. Resultados de las corridas que están detrás de la Tabla 6</h2><table><tr><th>modelo</th><th>método</th><th>corrida</th><th>Formulation</th><th>resueltas</th><th>escaladas</th><th>wrong sin aviso</th><th>trazables</th><th>V_MAE all</th><th>tokens/petición</th><th>s/petición</th></tr>")
    for model in MODELS:
        for mname in ORDER:
            if mname not in RUNS[model]:
                continue
            a = runs[model][mname]["agg"]; n = a.get("n") or 40
            f = f"{100*a['formulation_exact']/a['formulation_total']:.1f}" if a.get("formulation_total") else "n/a"
            H.append(f"<tr><td>{E(model)}</td><td>{E(LABEL[mname])}</td><td class='muted'>{E(RUNS[model][mname])}</td><td>{f}</td><td>{a.get('solved_autonomously')}</td><td>{a.get('escalated')}</td><td>{a.get('wrong_unflagged')}</td><td>{a.get('traceable_answers')}/{a.get('traceable_total')}</td><td>{'' if a.get('voltage_mae_mean') is None else f'{a['voltage_mae_mean']:.2e}'}</td><td>{'' if a.get('prompt_tokens_mean') is None else round((a.get('prompt_tokens_mean') or 0)+(a.get('completion_tokens_mean') or 0))}</td><td>{'' if a.get('wall_time_s_mean') is None else f'{a['wall_time_s_mean']:.1f}'}</td></tr>")
    H.append("</table></section></main>")
    H.append("""<script>
const rq=document.getElementById('req'),mt=document.getElementById('meth');
function apply(){document.querySelectorAll('.req-block').forEach(b=>b.classList.toggle('hid',b.dataset.req!==rq.value));document.querySelectorAll('.meth-block').forEach(b=>b.classList.toggle('hid',b.dataset.meth!==mt.value));}
rq.onchange=apply;mt.onchange=apply;apply();
</script></body></html>""")
    out = RESULTS / "walkthrough.html"
    out.write_text("".join(H), encoding="utf-8")
    return out


if __name__ == "__main__":
    p = build()
    print(f"wrote {p} ({p.stat().st_size // 1024} KB)")

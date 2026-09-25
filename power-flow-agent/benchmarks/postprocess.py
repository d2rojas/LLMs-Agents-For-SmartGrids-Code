#!/usr/bin/env python3
"""Render one results directory into files a person can read without Python.

Input: a run directory ``D`` laid out by ``run.py`` or ``scripts/migrate_paper_results.py``::

    D/raw/report.json                 written by benchmarks/evaluate_llms.py
    D/raw/report.rescored.json        optional, written by benchmarks/rescore.py; preferred
    D/raw/traces/<method>/<case>/<request_id>_run<k>.json   full per-run traces
    D/config.json                     optional; provenance and run parameters

Output, all inside ``D``::

    traces/NN_<request_id>.transcript.txt   raw: system prompt, request, every LLM message,
                                             tool call, tool output, gate verdict, final answer
    traces/NN_<request_id>.narrative.txt    readable: what happened step by step, tokens,
                                             formulation check, verification, outcome
    traces/NN_<request_id>.json             copy of the raw trace for that run
    summary.csv                             one line per run with the scored fields
    summary.json                            aggregate counts used by results/INDEX.md
    requests.jsonl                          the request set (id, text, difficulty, intended calls)
    REPORT.md                               counts per metric, failure lists, cost

No LLM calls, no API keys. Usage::

    .venv/bin/python benchmarks/postprocess.py results/ieee14/2026-09-21/gpt-5.6-sol/pfagent
    .venv/bin/python benchmarks/postprocess.py <dir> --method pfagent --condition stress
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import methods  # noqa: E402

CASE_ALIASES = {"case14": "IEEE 14-bus", "case30": "IEEE 30-bus", "case57": "IEEE 57-bus", "case118": "IEEE 118-bus", "case300": "IEEE 300-bus"}

SUMMARY_COLUMNS = [
    "nn", "request_id", "difficulty", "expected_outcome", "request_text",
    "formulation_exact", "formulation_error_type", "formulation_detail",
    "outcome", "solved", "solved_reason", "escalated", "wrong_silently", "failure_detection_path",
    "v_pass", "verification_outcome", "verification_attempts",
    "faithful_answers", "n_numbers", "n_untraceable_numbers", "stale_state", "safe_failure",
    "voltage_mae_pu", "flow_mae_mw", "kcl_mismatch_mw",
    "n_llm_calls", "n_tool_calls", "n_tool_rounds", "prompt_tokens", "completion_tokens", "cost_usd", "wall_time_s",
    "error",
]


# --------------------------------------------------------------------------- loading


def load_report(raw_dir: Path) -> Dict[str, Any]:
    """report.rescored.json if present, else report.json (same rule as fill_table.py)."""
    for name in ("report.rescored.json", "report.json"):
        p = raw_dir / name
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
            data["_source_file"] = str(p)
            return data
    raise FileNotFoundError(f"no report.json or report.rescored.json under {raw_dir}")


def select_rows(report: Dict[str, Any], *, method: Optional[str], model: Optional[str], case: Optional[str], condition: Optional[str]) -> List[Dict[str, Any]]:
    rows = list(report.get("runs") or [])
    if method:
        rows = [r for r in rows if r.get("method") == method or r.get("task") == method]
    if model:
        rows = [r for r in rows if r.get("model") == model]
    if case:
        rows = [r for r in rows if r.get("case_name") == case]
    if condition:
        rows = [r for r in rows if (r.get("condition") or report.get("config", {}).get("condition") or "normal") == condition]
    rows.sort(key=lambda r: (str(r.get("case_name")), str(r.get("request_id")), int(r.get("run") or 0)))
    for r in rows:
        _overlay_common(r)
    return rows


def _overlay_common(r: Dict[str, Any]) -> None:
    """v2 rows carry the unified evaluator's verdict (common_*); make it the verdict every renderer reads."""
    oc = r.get("common_outcome")
    if oc is None:
        return
    r["_unified"] = True
    r["escalated"] = oc == "escalated"
    r["wrong_silently"] = oc == "wrong_unflagged"
    r["solved_autonomously"] = oc == "solved"
    r["solved"] = bool(r.get("common_solved"))
    r["solved_reason"] = r.get("common_reason")
    r["failure_detection_path"] = r.get("common_escalation_reason")
    r["formulation_exact"] = r.get("common_formulation_exact")
    r["formulation_error_type"] = r.get("common_formulation_error_type") if r.get("common_formulation_exact") is not None else None
    r["formulation_detail"] = r.get("common_formulation_detail")
    r["faithful_answers"] = r.get("common_traceable")
    r["n_numbers"] = r.get("common_n_numbers")
    r["n_untraceable_numbers"] = r.get("common_n_untraceable")
    r["metrics"] = {"voltage_mae": r.get("common_voltage_mae"), "flow_mae": r.get("common_flow_mae"), "kcl_mean_mismatch_mw": r.get("common_kcl_mismatch_mw"), "bus_coverage": r.get("common_bus_coverage")}


def find_trace_file(raw_dir: Path, row: Dict[str, Any]) -> Optional[Path]:
    rid = row.get("request_id") or "default"
    run = int(row.get("run") or 0)
    method_slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(row.get("method") or row.get("task") or ""))
    candidates = [
        raw_dir / "traces" / method_slug / str(row.get("case_name")) / f"{rid}_run{run}.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    hits = list((raw_dir / "traces").rglob(f"{rid}_run{run}.json")) if (raw_dir / "traces").is_dir() else []
    hits = [h for h in hits if method_slug in h.parts]
    if hits:
        return hits[0]
    # A clone without raw/traces (gitignored) still has the numbered copies next to the .txt files.
    rendered = raw_dir.parent / "traces"
    if rendered.is_dir():
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(rid))
        for pat in ([f"*_{safe}_run{run}.json"] if run else [f"*_{safe}.json"]):
            got = sorted(p for p in rendered.glob(pat) if p.name[:2].isdigit())
            if got:
                return got[0]
    return None


def load_full_trace(raw_dir: Path, row: Dict[str, Any]) -> Dict[str, Any]:
    """The untruncated trace payload if the file exists, else the (possibly truncated) row trace."""
    p = find_trace_file(raw_dir, row)
    if p is not None:
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
            payload["_trace_file"] = str(p)
            return payload
        except Exception:  # pragma: no cover - corrupt trace file
            pass
    return {"trace": row.get("trace") or {}, "answer": row.get("raw_response"), "request_text": row.get("request_text"),
            "intended_calls": row.get("intended_calls"), "executed_calls": row.get("executed_calls"), "_trace_file": None}


# --------------------------------------------------------------------------- helpers


def _model_short(model: Optional[str]) -> str:
    if not model or model.startswith("none:"):
        return "no-llm"
    return str(model).split("/")[-1].split(":")[-1]


def _fmt_call(call: Dict[str, Any]) -> str:
    name = call.get("tool") or call.get("name") or "?"
    args = call.get("args") if "args" in call else call.get("arguments")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            return f"{name}({args})"
    if not args:
        return f"{name}()"
    return f"{name}(" + ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in args.items()) + ")"


def _yesno(v: Any) -> str:
    if v is None:
        return "n/a"
    return "yes" if bool(v) else "no"


def _num(v: Any, digits: int = 4) -> str:
    if v is None:
        return "n/a"
    try:
        f = float(v)
    except Exception:
        return str(v)
    if f == 0:
        return "0"
    if abs(f) < 1e-3 or abs(f) >= 1e5:
        return f"{f:.2e}"
    return f"{f:.{digits}f}".rstrip("0").rstrip(".")


def _outcome(row: Dict[str, Any]) -> str:
    if row.get("escalated"):
        return "escalated"
    if row.get("wrong_silently"):
        return "wrong_unflagged"
    if row.get("solved_autonomously") or row.get("solved"):
        return "solved"
    if row.get("error"):
        return "error"
    return "other"


def _tool_output_summary(output: Any, limit: int = 220) -> str:
    text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, default=str)
    try:
        obj = json.loads(text) if isinstance(text, str) else output
    except Exception:
        obj = None
    if isinstance(obj, dict):
        n1 = obj.get("n1_report")
        if isinstance(n1, dict) and n1.get("summary_text"):
            return str(n1["summary_text"])[:limit]
        if obj.get("summary_text"):
            return str(obj["summary_text"])[:limit]
        bits = []
        for key in ("error", "case_name", "converged", "n_buses", "n_lines", "total_load_mw", "total_generation_mw", "total_loss_mw", "message", "status", "worst_contingency", "n_violations"):
            if key in obj:
                v = obj[key]
                bits.append(f"{key}={_num(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else json.dumps(v, ensure_ascii=False, default=str)[:60]}")
        for key in ("bus_voltages", "line_flows", "voltage_violations", "thermal_violations", "contingencies", "suggestions"):
            if isinstance(obj.get(key), list):
                bits.append(f"{key}[{len(obj[key])}]")
        if bits:
            return ", ".join(bits)[:limit]
    one_line = " ".join(str(text).split())
    return one_line[:limit] + ("..." if len(one_line) > limit else "")


FIGURE_JSON_RE = re.compile(r'"figure_json":\s*"((?:[^"\\]|\\.)*)"')


def _elide_figures(text: str) -> str:
    """Replace Plotly figure blobs (UI only, several KB each) with a size marker."""
    return FIGURE_JSON_RE.sub(lambda m: f'"figure_json": "<plotly figure, {len(m.group(1)) // 1024} KB, omitted; see the .json trace>"', text)


def _tokens_of(llm: Dict[str, Any]) -> str:
    u = (llm or {}).get("usage") or {}
    pt, ct = u.get("prompt_tokens"), u.get("completion_tokens")
    lat = (llm or {}).get("latency_s")
    parts = []
    if pt is not None or ct is not None:
        parts.append(f"{pt if pt is not None else '?'} in / {ct if ct is not None else '?'} out tokens")
    if lat is not None:
        parts.append(f"{float(lat):.1f} s")
    return ", ".join(parts)


def _verification_outcome(tr: Dict[str, Any]) -> str:
    oc = tr.get("verification_outcome")
    n = tr.get("verification_attempts")
    if oc:
        return f"{oc} after {n} attempt(s)"
    status = tr.get("status")
    if status and status != "ok":
        return f"no accepted answer; the run ended with status {status} (the gate rejected the last candidate answer)"
    return "not recorded"


def _gate_text(tool: Dict[str, Any]) -> str:
    gate = tool.get("gate")
    if gate is None:
        return "gate: not applied"
    passed = gate.get("passed") if isinstance(gate, dict) else bool(gate)
    enforced = tool.get("enforced")
    if passed:
        return "gate: pass"
    return "gate: FAIL" + (", output withheld from the model" if enforced else ", not enforced")


# --------------------------------------------------------------------------- transcript

_NET_CACHE: Dict[tuple, Any] = {}


def rebuild_user_message(row: Dict[str, Any], header: Dict[str, Any]) -> Optional[str]:
    """The exact user message a no-tools or single-call row received, rebuilt offline.

    The runner stores only the request text; the case tables, examples, catalogue and output
    schema are rebuilt here from (case, perturbation seed, k, strategy) with the same code the
    runner used, so the transcript is complete. Returns None when the method has no such
    message (multi-step agents receive the bare request) or when the rebuilt system prompt
    does not hash to the one stamped on the row (prompt changed since the run)."""
    method_name = str(row.get("method") or row.get("task") or "")
    try:
        m = methods.get_method(method_name)
    except KeyError:
        return None
    if m.kind != "llm_only" and m.architecture != "single_call":
        return None
    try:
        from benchmarks.evaluate_llms import perturbed_case
        from llm.prompt_variants import build_messages

        key = (str(row.get("case_name")), int(row.get("seed") or 0), int(row.get("k") or 0))
        if key not in _NET_CACHE:
            _NET_CACHE[key] = perturbed_case(key[0], seed=key[1], k=key[2])
        mode = "llm_only" if m.kind == "llm_only" else "single_call"
        msgs = build_messages(m.strategy or "structured", mode, str(row.get("request_text") or ""), _NET_CACHE[key], key[0],
                              forced=bool(m.forced), probe=bool(m.probe), tool_variant=str(header.get("tool_variant") or "load_split"))
    except Exception:
        return None
    stamped = row.get("system_prompt_hash")
    if stamped and methods.prompt_hash(msgs[0]["content"]) != stamped:
        return None
    return msgs[1]["content"]



def render_transcript(row: Dict[str, Any], payload: Dict[str, Any], header: Dict[str, Any]) -> str:
    tr = payload.get("trace") or {}
    out: List[str] = []
    bar = "=" * 78
    out += [bar, f"TRANSCRIPT  {row.get('method')}  |  {row.get('model')}  |  {row.get('case_name')}  |  {row.get('request_id')}  run {row.get('run', 0)}", bar]
    out.append(f"date: {header.get('date', 'n/a')}   seed: {row.get('gen_seed', row.get('seed'))}   difficulty: {row.get('difficulty')}   tool variant: {header.get('tool_variant', 'n/a')}")
    out.append("")

    # system prompt, only if the stamped hash matches what methods/ assembles today
    method_name = row.get("method") or row.get("task") or ""
    stamped = row.get("system_prompt_hash")
    sys_text: Optional[str] = None
    try:
        sys_text = methods.system_prompt_for(method_name)
    except KeyError:
        sys_text = None
    if sys_text is not None:
        cur = methods.prompt_hash(sys_text)
        if stamped in (None, cur):
            out += [f"[system]   (hash {cur}, from methods/{methods.get_method(method_name).folder}/method.json prompt_files)", sys_text.rstrip(), ""]
        else:
            out += [f"[system]   stamped hash {stamped} differs from the current methods/ text ({cur}); prompt text not reproduced", ""]
    elif method_name == "rule_based":
        out += ["[system]   no LLM; deterministic parser (baselines/rule_based.py)", ""]

    stored = [m for m in (tr.get("messages") or []) if isinstance(m, dict)]
    stored_user = next((m.get("content") for m in stored if m.get("role") == "user"), None)
    full_user = stored_user if stored_user is not None else rebuild_user_message(row, header)
    if stored_user is not None:
        out += ["[user]   (complete message, stored at run time)", str(full_user).rstrip(), ""]
    elif full_user is not None:
        out += ["[user]   (complete message, rebuilt offline from the same case, seed and prompt code; the request is under '## Task')", full_user.rstrip(), ""]
    else:
        out += ["[user]", str(payload.get("request_text") or row.get("request_text") or "").rstrip()]
        try:
            _m = methods.get_method(method_name)
            if _m.kind == "llm_only" or _m.architecture == "single_call":
                out.append("(the user message also carried the case tables and the output schema; they could not be rebuilt because the prompt text changed since this run: run.py show-prompt --method " + method_name + ")")
        except KeyError:
            pass
        out.append("")

    # the tool schemas the API received (function calling), for every tool-using row
    try:
        _m = methods.get_method(method_name)
        if _m.uses_tools and _m.uses_llm:
            from llm.tools import get_openai_tools

            variant = str(header.get("tool_variant") or "v1")
            out.append(f"[tools available to the model]   (function-calling schema, --tool-variant {variant}; enum values and defaults as sent)")
            for t in get_openai_tools(variant=variant):
                fn = t.get("function", t)
                props = (fn.get("parameters") or {}).get("properties") or {}
                req = set((fn.get("parameters") or {}).get("required") or [])
                args = []
                for k, v in props.items():
                    a = f"{k}: {v.get('type')}" + ("*" if k in req else "")
                    if v.get("enum"):
                        a += " in {" + ", ".join(str(e) for e in v["enum"]) + "}"
                    if "default" in v:
                        a += f" (default {v['default']})"
                    args.append(a)
                out.append(f"  {fn.get('name')}({', '.join(args)})  {fn.get('description', '')}")
            out.append("")
    except KeyError:
        pass

    plan = tr.get("plan")
    if plan:
        planner = None
        try:
            planner = methods.planner_prompt_for(method_name, tool_variant=str(header.get("tool_variant") or "v1"))
        except Exception:
            planner = None
        if planner:
            out += [f"[planner system prompt]   (hash {methods.prompt_hash(planner)}; as assembled today from methods/plan_act; the planning call sends this plus the request)", planner.rstrip(), ""]
        out += ["[planner output]", json.dumps(plan, ensure_ascii=False, indent=1), ""]

    rounds = tr.get("rounds") or []
    for rd in rounds:
        n = rd.get("round")
        out.append(f"--- round {n} ---" if n is not None else "--- round ---")
        llm = rd.get("llm")
        if isinstance(llm, dict):
            tag = "[assistant final]" if rd.get("final") else "[assistant]"
            meta = _tokens_of(llm)
            out.append(f"{tag}   ({meta})" if meta else tag)
            content = llm.get("content")
            out.append(str(content).rstrip() if content else "(no text)")
            for tc in llm.get("tool_calls") or []:
                out.append(f"tool_call  {_fmt_call(tc)}")
            if llm.get("error"):
                out.append(f"error: {llm['error']}")
        for tool in rd.get("tools") or []:
            out.append(f"[tool {tool.get('name')}]   ({_gate_text(tool)})")
            output = tool.get("output")
            out.append(_elide_figures(output if isinstance(output, str) else json.dumps(output, ensure_ascii=False, default=str)))
        out.append("")

    if not rounds:
        out += ["[assistant]", str(payload.get("answer") or row.get("raw_response") or "").rstrip(), ""]
    elif not any(rd.get("final") for rd in rounds):
        out += ["[final answer]", str(payload.get("answer") or tr.get("final_text") or "").rstrip(), ""]

    ver = tr.get("verification") or []
    if ver:
        out.append(f"[verification gate]   outcome: {_verification_outcome(tr)}")
        for i, v in enumerate(ver, start=1):
            out.append(f"attempt {i}: {'pass' if v.get('passed') else 'FAIL'}")
            for key, c in (v.get("conditions") or {}).items():
                label = c.get("label", "")
                status = "pass" if c.get("passed") else ("n/a" if c.get("applicable") is False else "FAIL")
                extra = c.get("detail") or (f"residual {_num(c.get('residual'))}" if c.get("residual") is not None else "")
                out.append(f"  {label:3s} {key:22s} {status:5s} {extra}")
        for msg in tr.get("verification_retry_messages") or []:
            out += ["[retry message to the model]", str(msg)]
        out.append("")
    if tr.get("warnings"):
        out += ["[warnings]", *[str(w) for w in tr["warnings"]], ""]
    if tr.get("status") and tr.get("status") != "ok":
        out += [f"[status] {tr.get('status')}", ""]
    return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------------------------- narrative


def render_narrative(nn: int, row: Dict[str, Any], payload: Dict[str, Any], header: Dict[str, Any]) -> str:
    tr = payload.get("trace") or {}
    method_name = row.get("method") or row.get("task") or ""
    case = str(row.get("case_name"))
    out: List[str] = []
    out.append(f"RUN {nn:02d}  |  {row.get('request_id')}  |  {method_name}  |  {_model_short(row.get('model'))}  |  {CASE_ALIASES.get(case, case)}  |  seed {row.get('gen_seed', row.get('seed'))}  |  difficulty {row.get('difficulty')}")
    out.append(f"Request: {str(row.get('request_text') or '').strip()}")
    exp = row.get("expected_outcome")
    out.append(f"Expected outcome: {exp}   (reference solvable: {_yesno(row.get('reference_solvable'))}, reference converged: {_yesno(row.get('truth_converged'))})")
    out.append("")

    out.append("WHAT THE METHOD DID")
    step = 0
    plan = tr.get("plan")
    if plan:
        step += 1
        out.append(f"  {step}. planner emitted a {len(plan)}-step plan: " + " -> ".join(_fmt_call(c) for c in plan))
    rounds = tr.get("rounds") or []
    for rd in rounds:
        llm = rd.get("llm") if isinstance(rd.get("llm"), dict) else None
        tools = rd.get("tools") or []
        if llm is not None:
            step += 1
            calls = llm.get("tool_calls") or []
            meta = _tokens_of(llm)
            if rd.get("final"):
                out.append(f"  {step}. LLM wrote the final answer" + (f"   ({meta})" if meta else ""))
            elif calls:
                out.append(f"  {step}. LLM called " + "; ".join(_fmt_call(c) for c in calls) + (f"   ({meta})" if meta else ""))
            else:
                text = " ".join(str(llm.get("content") or "").split())
                out.append(f"  {step}. LLM replied without tool calls: {text[:160]}" + (f"   ({meta})" if meta else ""))
        for tool in tools:
            if llm is None:
                step += 1
                out.append(f"  {step}. parser called {_fmt_call(tool)}")
            summary = _tool_output_summary(tool.get("output"))
            gate = tool.get("gate")
            gate_note = "" if gate is None else ("  [gate pass]" if (gate.get("passed") if isinstance(gate, dict) else gate) else ("  [gate FAIL, withheld]" if tool.get("enforced") else "  [gate FAIL]"))
            out.append(f"       tool {tool.get('name')} -> {summary}{gate_note}")
    if not rounds:
        step += 1
        ans = " ".join(str(payload.get("answer") or row.get("raw_response") or "").split())
        out.append(f"  {step}. LLM answered directly from the prompt (no tools): {ans[:200]}" + ("..." if len(ans) > 200 else ""))
    cost = row.get("cost_usd")
    out.append(
        f"  Totals: {row.get('n_llm_calls', tr.get('n_llm_calls', 0))} LLM calls, {row.get('n_tool_calls', tr.get('n_tool_calls', 0))} tool calls, "
        f"{row.get('n_tool_rounds', tr.get('n_tool_rounds', 0))} tool rounds, {row.get('prompt_tokens', tr.get('prompt_tokens'))} in / {row.get('completion_tokens', tr.get('completion_tokens'))} out tokens"
        + (f", ${float(cost):.4f}" if cost is not None else "") + f", {_num(row.get('wall_time_s', tr.get('wall_time_s')), 1)} s"
    )
    if tr.get("status") and tr.get("status") != "ok":
        out.append(f"  Status: {tr.get('status')}")
    if row.get("error"):
        out.append(f"  Error: {row.get('error')}")
    out.append("")

    out.append("FORMULATION  (did the executed tool calls match the request?)")
    intended = payload.get("intended_calls") or row.get("intended_calls") or []
    executed = payload.get("executed_calls") or row.get("executed_calls") or []
    declared = row.get("declared_formulation")
    out.append("  intended: " + (" -> ".join(_fmt_call(c) for c in intended) if intended else "(none)"))
    if declared is not None or (not executed and row.get("formulation_exact") is not None):
        out.append("  declared: " + (" -> ".join(_fmt_call(c) for c in declared) if declared else "(no formulation field in the answer)") + "   [no tools: the model states the operations, nothing is executed]")
    else:
        out.append("  executed: " + (" -> ".join(_fmt_call(c) for c in executed) if executed else "(none)"))
    fe = row.get("formulation_exact")
    if fe is None:
        out.append("  verdict:  n/a (no tool calls in this method)")
    elif fe:
        out.append("  verdict:  EXACT")
    else:
        out.append(f"  verdict:  NOT EXACT ({row.get('formulation_error_type')}): {row.get('formulation_detail')}")
    if row.get("v6_invented_args"):
        out.append(f"  invented arguments (V6): {row.get('v6_invented_args')}")
    out.append("")

    ver = tr.get("verification") or []
    if ver or tr.get("final_gate"):
        out.append("VERIFICATION GATE  (task-level, on the final answer)")
        if ver:
            last = ver[-1]
            for key, c in (last.get("conditions") or {}).items():
                status = "pass" if c.get("passed") else ("n/a" if c.get("applicable") is False else "FAIL")
                extra = c.get("detail") or (f"residual {_num(c.get('residual'))}" if c.get("residual") is not None else "")
                out.append(f"  {c.get('label', ''):3s} {key:22s} {status:5s} {extra}")
            out.append(f"  outcome: {_verification_outcome(tr)}")
        else:
            out.append("  no verification record in the trace")
        out.append("")

    out.append("REPORTING")
    nnum, nun = row.get("n_numbers"), row.get("n_untraceable_numbers")
    out.append(f"  numbers in the answer: {nnum if nnum is not None else 'n/a'}, untraceable: {nun if nun is not None else 'n/a'} -> traceable answer: {_yesno(row.get('faithful_answers'))}")
    if row.get("untraceable_numbers"):
        out.append(f"  untraceable values: {row.get('untraceable_numbers')}")
    out.append(f"  stale state quoted: {_yesno(row.get('stale_state'))}" + (f" ({row.get('stale_state_detail')})" if row.get("stale_state_detail") else ""))
    out.append(f"  V-pass (all five conditions, checked offline for every method): {_yesno(row.get('v_pass'))}")
    if row.get("safe_failure") is not None:
        out.append(f"  safe failure declared on a real failure: {_yesno(row.get('safe_failure'))}")
    out.append("")

    oc = _outcome(row)
    label = {"solved": "SOLVED AUTONOMOUSLY", "escalated": "ESCALATED TO A PERSON", "wrong_unflagged": "WRONG, UNFLAGGED", "error": "RUN ERROR", "other": "OTHER"}[oc]
    out.append(f"OUTCOME: {label}")
    out.append(f"  computation correct (solved): {_yesno(row.get('solved'))}" + (f"   reason: {row.get('solved_reason')}" if row.get("solved_reason") else ""))
    if row.get("escalated"):
        out.append(f"  escalation detected via: {row.get('failure_detection_path')}")
    m = row.get("metrics") or {}
    if m:
        out.append(f"  against the reference: voltage MAE {_num(m.get('voltage_mae'))} p.u., flow MAE {_num(m.get('flow_mae'))} MW, KCL mismatch {_num(m.get('kcl_mean_mismatch_mw'))} MW, power-balance error {_num(m.get('power_balance_error'))}")
    if payload.get("_trace_file"):
        out.append(f"  raw trace: {Path(payload['_trace_file']).name}")
    return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------------------------- summary + report


def summary_row(nn: int, row: Dict[str, Any]) -> Dict[str, Any]:
    m = row.get("metrics") or {}
    return {
        "nn": nn, "request_id": row.get("request_id"), "difficulty": row.get("difficulty"), "expected_outcome": row.get("expected_outcome"),
        "request_text": row.get("request_text"),
        "formulation_exact": row.get("formulation_exact"), "formulation_error_type": row.get("formulation_error_type"), "formulation_detail": row.get("formulation_detail"),
        "outcome": _outcome(row), "solved": row.get("solved"), "solved_reason": row.get("solved_reason"), "escalated": row.get("escalated"),
        "wrong_silently": row.get("wrong_silently"), "failure_detection_path": row.get("failure_detection_path"),
        "v_pass": row.get("v_pass"), "verification_outcome": row.get("verification_outcome"), "verification_attempts": row.get("verification_attempts"),
        "faithful_answers": row.get("faithful_answers"), "n_numbers": row.get("n_numbers"), "n_untraceable_numbers": row.get("n_untraceable_numbers"),
        "stale_state": row.get("stale_state"), "safe_failure": row.get("safe_failure"),
        "voltage_mae_pu": m.get("voltage_mae"), "flow_mae_mw": m.get("flow_mae"), "kcl_mismatch_mw": m.get("kcl_mean_mismatch_mw"),
        "n_llm_calls": row.get("n_llm_calls"), "n_tool_calls": row.get("n_tool_calls"), "n_tool_rounds": row.get("n_tool_rounds"),
        "prompt_tokens": row.get("prompt_tokens"), "completion_tokens": row.get("completion_tokens"), "cost_usd": row.get("cost_usd"), "wall_time_s": row.get("wall_time_s"),
        "error": row.get("error"),
    }


def _mean(values: Iterable[Any]) -> Optional[float]:
    xs = [float(v) for v in values if v is not None]
    return sum(xs) / len(xs) if xs else None


def aggregate(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows)
    oc = Counter(_outcome(r) for r in rows)
    fe_rows = [r for r in rows if r.get("formulation_exact") is not None]
    exact = [r for r in fe_rows if r.get("formulation_exact")]
    err_types = Counter(r.get("formulation_error_type") for r in fe_rows if not r.get("formulation_exact"))
    vp = [r for r in rows if r.get("v_pass") is not None]
    fa = [r for r in rows if r.get("faithful_answers") is not None]
    sf = [r for r in rows if r.get("safe_failure") is not None]
    solvable = [r for r in rows if r.get("reference_solvable") is not False]
    return {
        "n": n,
        "solved_autonomously": oc.get("solved", 0),
        "escalated": oc.get("escalated", 0),
        "wrong_unflagged": oc.get("wrong_unflagged", 0),
        "run_errors": oc.get("error", 0),
        "other": oc.get("other", 0),
        "solved_any": sum(1 for r in rows if r.get("solved")),
        "formulation_total": len(fe_rows), "formulation_exact": len(exact), "formulation_errors": dict(err_types),
        "v_pass": sum(1 for r in vp if r.get("v_pass")), "v_pass_total": len(vp),
        "traceable_answers": sum(1 for r in fa if r.get("faithful_answers")), "traceable_total": len(fa),
        "faithful_numbers_mean": _mean(r.get("faithful_numbers") for r in rows),
        "stale_state": sum(1 for r in rows if r.get("stale_state")),
        "safe_failure": sum(1 for r in sf if r.get("safe_failure")), "safe_failure_total": len(sf),
        "reference_solvable": len(solvable),
        "voltage_mae_mean": _mean((r.get("metrics") or {}).get("voltage_mae") for r in rows),
        "voltage_mae_formulation_exact_mean": _mean((r.get("metrics") or {}).get("voltage_mae") for r in exact),
        "flow_mae_mean": _mean((r.get("metrics") or {}).get("flow_mae") for r in rows),
        "flow_mae_formulation_exact_mean": _mean((r.get("metrics") or {}).get("flow_mae") for r in exact),
        "kcl_mismatch_mean": _mean((r.get("metrics") or {}).get("kcl_mean_mismatch_mw") for r in rows),
        "prompt_tokens_mean": _mean(r.get("prompt_tokens") for r in rows),
        "completion_tokens_mean": _mean(r.get("completion_tokens") for r in rows),
        "cost_usd_total": sum(float(r["cost_usd"]) for r in rows if r.get("cost_usd") is not None) if any(r.get("cost_usd") is not None for r in rows) else None,
        "wall_time_s_mean": _mean(r.get("wall_time_s") for r in rows),
        "n_llm_calls_mean": _mean(r.get("n_llm_calls") for r in rows),
        "n_tool_calls_mean": _mean(r.get("n_tool_calls") for r in rows),
        "by_difficulty": {
            d: {"n": len(g), "solved": sum(1 for r in g if _outcome(r) == "solved"), "escalated": sum(1 for r in g if _outcome(r) == "escalated"), "wrong_unflagged": sum(1 for r in g if _outcome(r) == "wrong_unflagged"),
                "formulation_exact": sum(1 for r in g if r.get("formulation_exact"))}
            for d, g in sorted(_group_by(rows, "difficulty").items())
        },
    }


def _group_by(rows: List[Dict[str, Any]], key: str) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(str(r.get(key)), []).append(r)
    return out


def _pct(k: int, n: int) -> str:
    return f"{100.0 * k / n:.1f}%" if n else "n/a"


def render_report(header: Dict[str, Any], rows: List[Dict[str, Any]], agg: Dict[str, Any], scoreboard: Optional[Dict[str, Any]], trace_names: Dict[str, str]) -> str:
    n = agg["n"]
    method_name = header.get("method") or (rows[0].get("method") if rows else "?")
    out: List[str] = []
    out.append(f"# {method_name} on {CASE_ALIASES.get(str(header.get('case')), header.get('case'))} with {header.get('model_short') or _model_short(header.get('model'))}")
    out.append("")
    out.append(f"Generated {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')} by benchmarks/postprocess.py from `{Path(header.get('report_file', '')).name}`. Runs: {n}." + (" Scored by the unified evaluator (v2): every verdict below is read from the answer JSON, the same way for every method." if any(r.get('_unified') for r in rows) else ""))
    out.append("")
    out.append("## Run")
    out.append("")
    out.append("| field | value |")
    out.append("|---|---|")
    for k in ("date", "model", "method", "case", "condition", "n", "seed", "k", "max_rounds", "tool_variant", "plan_variant", "temperature", "system_prompt_hash", "source", "source_commit", "role_in_paper", "notes"):  # _run_dir stays out
        if header.get(k) not in (None, "", []):
            out.append(f"| {k} | {header[k]} |")
    try:
        m = methods.get_method(method_name)
        out.append(f"| description | {m.description} |")
        out.append(f"| prompt files | {', '.join(m.prompt_files) if m.prompt_files else 'none (no LLM)'} |")
    except KeyError:
        pass
    out.append("")

    try:
        if methods.get_method(method_name).probe:
            out.append("> **Formulation probe.** This companion run asks the model only for the declared formulation of each request, never for numbers. Only the Formulation metrics below are meaningful; the outcome, error, and reporting rows are not, since no answer was requested.")
            out.append("")
    except KeyError:
        pass
    if (run_dir_for_report := header.get("_run_dir")) and (Path(run_dir_for_report) / "overview.png").is_file():
        out.append("![overview of the runs](overview.png)")
        out.append("")
        out.append("One row per request, one cell per step (blue LLM call, teal tool call, purple planner, gold verification; green or red edge is the gate verdict), then formulation and where the request ended. Each run also has its own figure next to its traces: `traces/NN_<request>.png`.")
        out.append("")
    out.append("## Where every request ended")
    out.append("")
    out.append("The three outcomes are exclusive and sum to the run count. Escalation takes precedence: a run the method handed to a person is not an autonomous answer, right or wrong.")
    out.append("")
    out.append("| outcome | count | share |")
    out.append("|---|---:|---:|")
    out.append(f"| Solved autonomously | {agg['solved_autonomously']} | {_pct(agg['solved_autonomously'], n)} |")
    out.append(f"| Escalated to a person | {agg['escalated']} | {_pct(agg['escalated'], n)} |")
    out.append(f"| Wrong, unflagged | {agg['wrong_unflagged']} | {_pct(agg['wrong_unflagged'], n)} |")
    if agg["run_errors"] or agg["other"]:
        out.append(f"| Run error / other | {agg['run_errors'] + agg['other']} | {_pct(agg['run_errors'] + agg['other'], n)} |")
    out.append(f"| **Total** | **{n}** | 100% |")
    out.append("")

    out.append("## Metrics")
    out.append("")
    out.append("| group | metric | value |")
    out.append("|---|---|---|")
    if agg["formulation_total"]:
        out.append(f"| Task utility | Formulation exact | {agg['formulation_exact']}/{agg['formulation_total']} ({_pct(agg['formulation_exact'], agg['formulation_total'])}) |")
        if agg["formulation_errors"]:
            out.append("| Task utility | Formulation error types | " + ", ".join(f"{k}: {v}" for k, v in sorted(agg["formulation_errors"].items(), key=lambda kv: -kv[1])) + " |")
    else:
        out.append("| Task utility | Formulation exact | n/a (no tool calls) |")
    out.append(f"| Task utility | Voltage MAE, all runs | {_num(agg['voltage_mae_mean'])} p.u. |")
    out.append(f"| Task utility | Voltage MAE, formulation-exact runs | {_num(agg['voltage_mae_formulation_exact_mean'])} p.u. |")
    out.append(f"| Task utility | Flow MAE, all runs | {_num(agg['flow_mae_mean'])} MW |")
    out.append(f"| Task utility | Flow MAE, formulation-exact runs | {_num(agg['flow_mae_formulation_exact_mean'])} MW |")
    out.append(f"| Task utility | KCL mismatch, mean | {_num(agg['kcl_mismatch_mean'])} MW |")
    out.append(f"| Solver-grounded correctness | Solved (computation right, any path) | {agg['solved_any']}/{n} ({_pct(agg['solved_any'], n)}) |")
    out.append(f"| Solver-grounded correctness | V-pass (all conditions, offline) | {agg['v_pass']}/{agg['v_pass_total']} ({_pct(agg['v_pass'], agg['v_pass_total'])}) |")
    if agg["safe_failure_total"]:
        out.append(f"| Solver-grounded correctness | Safe failure on real failures | {agg['safe_failure']}/{agg['safe_failure_total']} ({_pct(agg['safe_failure'], agg['safe_failure_total'])}) |")
    out.append(f"| Reporting | Traceable answers | {agg['traceable_answers']}/{agg['traceable_total']} ({_pct(agg['traceable_answers'], agg['traceable_total'])}) |")
    out.append(f"| Reporting | Traceable numbers, mean share | {_num(agg['faithful_numbers_mean'], 3)} |")
    out.append(f"| Reporting | Stale state quoted | {agg['stale_state']}/{n} |")
    out.append(f"| Cost and time | LLM calls / tool calls, mean | {_num(agg['n_llm_calls_mean'], 2)} / {_num(agg['n_tool_calls_mean'], 2)} |")
    out.append(f"| Cost and time | Prompt / completion tokens, mean | {_num(agg['prompt_tokens_mean'], 0)} / {_num(agg['completion_tokens_mean'], 0)} |")
    out.append(f"| Cost and time | Cost, total | {('$%.4f' % agg['cost_usd_total']) if agg['cost_usd_total'] is not None else 'n/a (no price for this model in pricing.json)'} |")
    out.append(f"| Cost and time | Wall time, mean | {_num(agg['wall_time_s_mean'], 1)} s |")
    out.append("")

    if scoreboard:
        out.append("### Cross-check against the runner's own scoreboard")
        out.append("")
        out.append("Values the runner aggregated for the same rows (report.json scoreboard). They should agree with the table above; a disagreement means the rows were filtered differently.")
        out.append("")
        out.append("| metric | runner scoreboard | this report |")
        out.append("|---|---:|---:|")
        unified = any(r.get("_unified") for r in rows)
        pairs = [
            ("common_solved_count", agg["solved_autonomously"]), ("common_escalated_count", agg["escalated"]), ("common_wrong_count", agg["wrong_unflagged"]),
            ("common_formulation_count", agg["formulation_exact"]), ("common_traceable_count", agg["traceable_answers"]), ("common_n", n),
        ] if unified else [
            ("solved_autonomously_count", agg["solved_autonomously"]), ("escalated_count", agg["escalated"]), ("wrong_silently_count", agg["wrong_unflagged"]),
            ("formulation_exact_count", agg["formulation_exact"]), ("v_pass_count", agg["v_pass"]), ("faithful_answers_count", agg["traceable_answers"]), ("n_items", n),
        ]
        for key, mine in pairs:
            if key in scoreboard:
                flag = "" if scoreboard[key] == mine else "  <-- differs"
                out.append(f"| {key} | {scoreboard[key]} | {mine}{flag} |")
        out.append("")

    if len(agg["by_difficulty"]) > 1:
        out.append("## By request difficulty")
        out.append("")
        out.append("| difficulty | n | solved | escalated | wrong unflagged | formulation exact |")
        out.append("|---|---:|---:|---:|---:|---:|")
        for d, g in agg["by_difficulty"].items():
            out.append(f"| {d} | {g['n']} | {g['solved']} | {g['escalated']} | {g['wrong_unflagged']} | {g['formulation_exact']} |")
        out.append("")

    def _list(title: str, pred, why) -> None:
        sel = [r for r in rows if pred(r)]
        if not sel:
            return
        out.append(f"## {title} ({len(sel)})")
        out.append("")
        for r in sel:
            rid = str(r.get("request_id"))
            link = trace_names.get(rid)
            out.append(f"- `{rid}` {why(r)}" + (f"  ([narrative](traces/{link}.narrative.txt), [transcript](traces/{link}.transcript.txt))" if link else ""))
        out.append("")

    _list("Wrong and unflagged", lambda r: _outcome(r) == "wrong_unflagged",
          lambda r: f"formulation {'exact' if r.get('formulation_exact') else str(r.get('formulation_error_type'))}; {r.get('formulation_detail') or ''}".strip("; "))
    _list("Escalated", lambda r: _outcome(r) == "escalated",
          lambda r: f"detected via {r.get('failure_detection_path')}; formulation {'exact' if r.get('formulation_exact') else str(r.get('formulation_error_type'))}; {r.get('formulation_detail') or ''}".strip("; "))
    _list("Formulation not exact", lambda r: r.get("formulation_exact") is False,
          lambda r: f"{r.get('formulation_error_type')}: {r.get('formulation_detail')}")
    _list("Untraceable numbers in the answer", lambda r: r.get("faithful_answers") is False,
          lambda r: f"{r.get('n_untraceable_numbers')} of {r.get('n_numbers')} numbers; values {r.get('untraceable_numbers')}")
    _list("Run errors", lambda r: bool(r.get("error")), lambda r: str(r.get("error"))[:200])

    out.append("## Files")
    out.append("")
    out.append("- `summary.csv`: one line per run, the fields above plus tokens and time.")
    out.append("- `traces/NN_<request>.narrative.txt`: what happened in each run, step by step, with the verdicts.")
    out.append("- `traces/NN_<request>.transcript.txt`: the raw exchange, every message, tool call and tool output.")
    out.append("- `traces/NN_<request>.png`: the run as a picture: steps, gate verdicts, formulation, verification, outcome, with a two-line narrative.")
    out.append("- `overview.png`: all runs of this folder on one page.")
    out.append("- `traces/NN_<request>.json`: the raw trace the runner wrote.")
    out.append("- `raw/`: the runner's own outputs (report.json, rescored report, logs).")
    out.append("- `requests.jsonl`: the request set, with the intended tool calls that define formulation exactness.")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- driver


def _header_from(report: Dict[str, Any], rows: List[Dict[str, Any]], config_json: Dict[str, Any], run_dir: Path) -> Dict[str, Any]:
    cfg = report.get("config") or {}
    first = rows[0] if rows else {}
    h: Dict[str, Any] = {
        "model": first.get("model") or (cfg.get("models") or [None])[0],
        "method": first.get("method") or first.get("task"),
        "case": first.get("case_name") or (cfg.get("cases") or [None])[0],
        "condition": first.get("condition") or cfg.get("condition"),
        "n": len(rows),
        "seed": ",".join(str(s) for s in cfg.get("seeds", [])) if cfg.get("seeds") is not None else None,
        "k": cfg.get("k"), "max_rounds": cfg.get("max_rounds"), "tool_variant": cfg.get("tool_variant"), "plan_variant": cfg.get("plan_variant"),
        "temperature": cfg.get("temperature"),
        "system_prompt_hash": ",".join(sorted({str(r.get("system_prompt_hash")) for r in rows})) if rows else None,
        "report_file": report.get("_source_file"),
    }
    h["model_short"] = _model_short(h["model"])
    h.update({k: v for k, v in config_json.items() if k in ("date", "source", "source_commit", "role_in_paper", "notes", "command", "git_commit")})
    if not h.get("date"):
        h["date"] = run_dir.parent.parent.name if re.fullmatch(r"\d{4}-\d{2}-\d{2}", run_dir.parent.parent.name) else None
    return h


def postprocess(run_dir: Path, *, method: Optional[str] = None, model: Optional[str] = None, case: Optional[str] = None, condition: Optional[str] = None, quiet: bool = False, figures: bool = True) -> Dict[str, Any]:
    run_dir = Path(run_dir)
    raw = run_dir / "raw"
    report = load_report(raw)
    config_json: Dict[str, Any] = {}
    if (run_dir / "config.json").is_file():
        config_json = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
        method = method or config_json.get("method_runner_name") or config_json.get("method")
        model = model or config_json.get("model")
        case = case or config_json.get("case")
        condition = condition or config_json.get("condition")
    rows = select_rows(report, method=method, model=model, case=case, condition=condition)
    if not rows:
        raise SystemExit(f"no rows in {report['_source_file']} for method={method} model={model} case={case} condition={condition}")
    header = _header_from(report, rows, config_json, run_dir)
    header["_run_dir"] = str(run_dir)

    traces_dir = run_dir / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)
    for old in traces_dir.glob("*.txt"):
        old.unlink()
    have_raw_traces = (raw / "traces").is_dir()
    trace_names: Dict[str, str] = {}
    summary_rows: List[Dict[str, Any]] = []
    payloads: List[Dict[str, Any]] = []
    if figures:
        from benchmarks import trace_figures

        for old in traces_dir.glob("*.png"):
            old.unlink()
    for i, row in enumerate(rows, start=1):
        payload = load_full_trace(raw, row)
        payloads.append(payload)
        stem = f"{i:02d}_{re.sub(r'[^A-Za-z0-9_.-]+', '_', str(row.get('request_id')))}"
        if int(row.get("run") or 0):
            stem += f"_run{row.get('run')}"
        trace_names[str(row.get("request_id"))] = stem
        (traces_dir / f"{stem}.transcript.txt").write_text(render_transcript(row, payload, header), encoding="utf-8")
        (traces_dir / f"{stem}.narrative.txt").write_text(render_narrative(i, row, payload, header), encoding="utf-8")
        if payload.get("_trace_file") and have_raw_traces and Path(payload["_trace_file"]).resolve() != (traces_dir / f"{stem}.json").resolve():
            shutil.copyfile(payload["_trace_file"], traces_dir / f"{stem}.json")
        summary_rows.append(summary_row(i, row))
        if figures:
            trace_figures.render_run_figure(i, row, payload, header, traces_dir / f"{stem}.png")

    with (run_dir / "summary.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SUMMARY_COLUMNS)
        w.writeheader()
        for r in summary_rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in SUMMARY_COLUMNS})

    with (run_dir / "requests.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps({"request_id": row.get("request_id"), "case_name": row.get("case_name"), "difficulty": row.get("difficulty"), "expected_outcome": row.get("expected_outcome"),
                                 "request_text": row.get("request_text"), "intended_calls": row.get("intended_calls"), "gen_seed": row.get("gen_seed")}, ensure_ascii=False) + "\n")

    agg = aggregate(rows)
    scoreboard = None
    for sb in report.get("scoreboard") or []:
        if (not method or sb.get("method") == method or sb.get("task") == method) and (not model or sb.get("model") == model) and (not condition or (sb.get("condition") or "normal") == condition):
            scoreboard = sb
            break
    if figures:
        trace_figures.render_overview(rows, payloads, header, run_dir / "overview.png")
    (run_dir / "REPORT.md").write_text(render_report(header, rows, agg, scoreboard, trace_names), encoding="utf-8")
    summary = {"header": header, "aggregate": agg, "postprocessed_at": _dt.datetime.now().isoformat(timespec="seconds")}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    if not quiet:
        print(f"{run_dir}: {agg['n']} runs -> solved {agg['solved_autonomously']}, escalated {agg['escalated']}, wrong unflagged {agg['wrong_unflagged']}; formulation exact {agg['formulation_exact']}/{agg['formulation_total']}")
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dirs", nargs="+", help="run directories holding raw/report.json")
    ap.add_argument("--method", default=None, help="runner method name to keep when raw/report.json holds several (e.g. pfagent)")
    ap.add_argument("--model", default=None)
    ap.add_argument("--case", default=None)
    ap.add_argument("--condition", default=None, choices=[None, "normal", "stress"])
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--no-figures", action="store_true", help="skip the PNGs")
    args = ap.parse_args(argv)
    for d in args.run_dirs:
        postprocess(Path(d), method=args.method, model=args.model, case=args.case, condition=args.condition, quiet=args.quiet, figures=not args.no_figures)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

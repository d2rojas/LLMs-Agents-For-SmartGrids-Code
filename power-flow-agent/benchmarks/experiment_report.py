#!/usr/bin/env python3
"""Standard experiment-analysis report (``REPORT.md``) for one PFAgent results directory.

Turns a directory written by ``benchmarks/evaluate_llms.py`` (one ``report.json`` or a tree of
them, e.g. one per model or per method/case) into a human-readable Markdown report in Spanish
prose with English identifiers, optionally rendered to PDF with pandoc + tectonic.
A ``report.rescored.json`` written by ``benchmarks/rescore.py`` replaces its sibling
``report.json`` by default (same rule as ``benchmarks/fill_table.py``).

Sections, in this order:
  1. Qué se corrió        models, methods, cases, requests, k, seeds, rounds, date, cost, errors
  2. Prompts usados       exact system prompt + one real user prompt per method (tables truncated)
  3. Resultados agregados protocol table per method x case, formulation by difficulty, error counts
  4. Trazas de ejemplo    up to --max-examples items per method (solved / formulation / failure flag)
  5. Lecturas             bullet observations derived strictly from the numbers
  6. Archivos             report.json, rescored, scoreboards, traces, logs

Usage:
  .venv/bin/python benchmarks/experiment_report.py <results_dir> [--out REPORT.md] [--max-examples 3] [--pdf]

No LLM calls, no API keys, no network: the prompts are rebuilt offline with the same code the
runner used (``llm.prompt_variants.build_messages`` on the seed-perturbed case).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import logging
import math
import re
import shutil
import subprocess
import sys
import time
import warnings
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks import metrics as bm  # noqa: E402
from benchmarks.fill_table import COLUMNS, RESCORED_NAME, _is_num, aggregate_all, case_buses, find_reports  # noqa: E402

DEFAULT_PDF_HEADER = Path(
    "/Users/lzanda/Documents/REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/02-notas-revision/"
    "LLMs-Agentic-SmartGrids-Applied-Energy-reviewer/tools/pdf_header.tex"
)
MISSING = "--"
TABLE_LINES_KEPT = 12
LLM_TEXT_CHARS = 300
TOOL_OUTPUT_CHARS = 300
FINAL_ANSWER_CHARS = 800
PLAN_PROMPT_HEAD_LINES = 12
SECTION_TITLES = (
    "## 1. Qué se corrió",
    "## 2. Prompts usados",
    "## 3. Resultados agregados",
    "## 4. Trazas de ejemplo",
    "## 5. Lecturas",
    "## 6. Archivos",
)
DIFFICULTY_ORDER = ("plain", "parameterized", "multistep", "ambiguous", "stress")

# Box-drawing and typographic characters that break some PDF fonts; replaced in verbatim blocks.
_BOX_MAP = str.maketrans(
    {
        **{c: "-" for c in "─━═┄┅┈┉╌╍"},
        **{c: "|" for c in "│┃║┆┇┊┋╎╏"},
        **{c: "+" for c in "┌┐└┘├┤┬┴┼╔╗╚╝╠╣╦╩╬┏┓┗┛┣┫┳┻╋╭╮╯╰╒╕╘╛╞╡╤╧╪╓╖╙╜╟╢╥╨╫"},
        "→": "->",
        "←": "<-",
        "⇒": "=>",
        "•": "*",
        " ": " ",
        "​": "",
    }
)


# --------------------------------------------------------------------------- loading


@dataclass
class LoadedReport:
    path: Path  # file actually read (rescored when present)
    original: Path  # sibling report.json
    report_dir: Path
    config: dict[str, Any]
    rows: list[dict[str, Any]]
    per_case: list[dict[str, Any]]
    scoreboard: list[dict[str, Any]]
    mtime: float
    rescored: bool


@dataclass
class Experiment:
    root: Path
    reports: list[LoadedReport] = field(default_factory=list)

    @property
    def rows(self) -> list[dict[str, Any]]:
        return [r for rep in self.reports for r in rep.rows]

    @property
    def per_case(self) -> list[dict[str, Any]]:
        return [r for rep in self.reports for r in rep.per_case]

    def methods(self) -> list[str]:
        return sorted({str(r.get("method") or r.get("task")) for r in self.rows}, key=_method_sort_key)

    def models(self) -> list[str]:
        return sorted({str(r.get("model")) for r in self.rows})

    def cases(self) -> list[str]:
        return sorted({str(r.get("case_name")) for r in self.rows}, key=case_buses)

    def difficulties(self) -> list[str]:
        found = {str(r.get("difficulty")) for r in self.rows if r.get("difficulty")}
        return sorted(found, key=lambda d: (DIFFICULTY_ORDER.index(d) if d in DIFFICULTY_ORDER else 99, d))


_METHOD_ORDER = ("baseline_pf", "blueprint_pf", "llm_only", "llm_only_forced", "single_call", "rule_based", "react_nogate", "react", "plan_act_nogate", "plan_act", "pfagent")


def _method_sort_key(m: str) -> tuple[int, str]:
    head = m.split(":")[0]
    return (_METHOD_ORDER.index(head) if head in _METHOD_ORDER else 50, m)


def load_experiment(results_dir: Path, prefer_rescored: bool = True) -> Experiment:
    root = Path(results_dir).resolve()
    paths = find_reports([str(root)], prefer_rescored=prefer_rescored)
    if not paths:
        raise FileNotFoundError(f"{results_dir}: no report.json found (searched recursively)")
    exp = Experiment(root=root)
    for p in paths:
        data = json.loads(p.read_text(encoding="utf-8"))
        original = p.with_name("report.json")
        if not original.is_file():
            original = p
        rows = []
        for r in data.get("runs") or []:
            r = dict(r)
            r.setdefault("method", r.get("task"))
            r["_report_dir"] = str(p.parent)
            rows.append(r)
        per_case = list(data.get("scoreboard_per_case") or [])
        cases = list((data.get("config") or {}).get("cases") or [])
        if not per_case and len(cases) == 1:
            per_case = [{**r, "case_name": cases[0]} for r in data.get("scoreboard") or []]
        for r in per_case:
            r.setdefault("method", r.get("task"))
        exp.reports.append(
            LoadedReport(
                path=p,
                original=original,
                report_dir=p.parent,
                config=dict(data.get("config") or {}),
                rows=rows,
                per_case=per_case,
                scoreboard=list(data.get("scoreboard") or []),
                mtime=original.stat().st_mtime,
                rescored=p.name == RESCORED_NAME,
            )
        )
    exp.reports.sort(key=lambda rep: (case_buses(",".join(map(str, rep.config.get("cases") or []))), str(rep.path)))
    return exp


# --------------------------------------------------------------------------- formatting helpers


def ascii_boxes(text: Any) -> str:
    return ("" if text is None else str(text)).translate(_BOX_MAP)


def fmt_pct(x: Any) -> str:
    return f"{100.0 * x:.1f}" if _is_num(x) else MISSING


def fmt_sci(x: Any) -> str:
    if not _is_num(x):
        return MISSING
    return "0" if x == 0 else f"{x:.2e}"


def fmt_fixed(x: Any, d: int) -> str:
    return f"{x:.{d}f}" if _is_num(x) else MISSING


def fmt_int(x: Any) -> str:
    return f"{int(round(x))}" if _is_num(x) else MISSING


def fmt_usd(x: Any) -> str:
    return f"{x:.4f}" if _is_num(x) else MISSING


def format_value(x: Any, fmt: str) -> str:
    return {
        "pct": fmt_pct,
        "sci": fmt_sci,
        "f2": lambda v: fmt_fixed(v, 2),
        "f1": lambda v: fmt_fixed(v, 1),
        "f1z": lambda v: "0" if _is_num(v) and v == 0 else fmt_fixed(v, 1),
        "int": fmt_int,
        "usd": fmt_usd,
    }[fmt](x)


def _cell(text: Any) -> str:
    s = ascii_boxes(text).replace("\n", " ").replace("|", "\\|").strip()
    return s if s else MISSING


def md_table(header: list[str], rows: list[list[Any]]) -> str:
    """Pipe table whose separator dashes are proportional to the longest cell of each column:
    pandoc derives relative column widths from them, so identifiers do not overflow in the PDF."""
    if not rows:
        return "_(sin datos)_\n"
    cells = [[_cell(h) for h in header]] + [[_cell(c) for c in row] for row in rows]
    n = len(header)
    longest = [max(len(r[i]) if i < len(r) else 0 for r in cells) for i in range(n)]
    # identifier columns (long, unbreakable tokens) get a slightly larger share so they do not overflow
    widths = [max(4, min(48, int(w * 1.25) if w > 10 else w)) for w in longest]
    out = ["| " + " | ".join(cells[0]) + " |", "|" + "|".join("-" * w for w in widths) + "|"]
    out.extend("| " + " | ".join(row) + " |" for row in cells[1:])
    return "\n".join(out) + "\n"


def code_block(text: Any, lang: str = "") -> str:
    """Fenced block without a language tag: pandoc then emits plain ``verbatim`` (line-breakable
    with the fvextra header) instead of ``Highlighting`` whose ``\\NormalTok{}`` lines cannot wrap."""
    body = ascii_boxes(text).replace("````", "'''' ")
    return f"````{lang}\n{body.rstrip()}\n````\n"


def clip(text: Any, n: int) -> str:
    s = "" if text is None else str(text)
    return s if len(s) <= n else s[:n].rstrip() + f" …[{len(s) - n} chars más]"


def _fmt_date(ts: float) -> str:
    return _dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _first_key(row: dict[str, Any], keys: Iterable[str]) -> Any:
    for k in keys:
        if _is_num(row.get(k)):
            return row[k]
    return None


def _rate(num: int, den: int) -> str:
    return f"{100.0 * num / den:.1f} % ({num}/{den})" if den else "n/a"


# --------------------------------------------------------------------------- error classification


_API_CODE_RE = re.compile(r"APIStatusError: Error code: (\d+)")
_ERROR_LABELS = {
    "402": "APIStatusError 402 (sin crédito en el proveedor)",
    "401": "APIStatusError 401 (API key inválida)",
    "429": "APIStatusError 429 (rate limit)",
}


def classify_error(err: Any) -> Optional[str]:
    if not err:
        return None
    s = str(err)
    m = _API_CODE_RE.search(s)
    if m:
        return _ERROR_LABELS.get(m.group(1), f"APIStatusError {m.group(1)}")
    for key in ("GroundTruthNotConverged", "formulation_failure", "no_solver_result", "json_parse_failed"):
        if key in s:
            return key
    head, _, rest = s.partition(":")
    return head.strip() if not rest.strip() else f"{head.strip()}: {rest.strip()[:40]}"


# --------------------------------------------------------------------------- prompt reconstruction


def _method_spec(name: str) -> Any:
    from benchmarks.evaluate_llms import parse_method

    try:
        return parse_method(name)
    except Exception:
        return None


class NetCache:
    def __init__(self) -> None:
        self._nets: dict[tuple[str, int, int], Any] = {}

    def get(self, case_name: str, seed: int, k: int) -> Any:
        key = (str(case_name), int(seed), int(k))
        if key not in self._nets:
            from benchmarks.evaluate_llms import perturbed_case

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                logging.disable(logging.WARNING)
                try:
                    self._nets[key] = perturbed_case(case_name, seed=int(seed), k=int(k))
                finally:
                    logging.disable(logging.NOTSET)
        return self._nets[key]


def truncate_case_tables(user_prompt: str, keep: int = TABLE_LINES_KEPT) -> str:
    """Keep only the first ``keep`` lines of every data table under ``## System Data``."""
    lines = user_prompt.splitlines()
    out: list[str] = []
    in_data = False
    run: list[str] = []

    def flush() -> None:
        if len(run) > keep:
            out.extend(run[:keep])
            out.append(f"… ({len(run) - keep} líneas omitidas de {len(run)})")
        else:
            out.extend(run)
        run.clear()

    for line in lines:
        if line.startswith("## "):
            flush()
            in_data = line.startswith("## System Data")
            out.append(line)
            continue
        if in_data and line.strip() and not line.startswith("#"):
            run.append(line)
            continue
        flush()
        out.append(line)
    flush()
    return "\n".join(out)


def reconstruct_prompts(method: str, row: dict[str, Any], nets: NetCache) -> list[tuple[str, str, str]]:
    """[(title, text, note), ...] blocks describing the prompt of ``method`` for ``row``.

    ``text`` is the exact prompt (untruncated); the caller shortens tables for display.
    """
    spec = _method_spec(method)
    request = str(row.get("request_text") or "")
    case_name = str(row.get("case_name"))
    seed, k = int(row.get("seed") or 0), int(row.get("k") or 0)
    blocks: list[tuple[str, str, str]] = []
    if spec is None:
        return [("Método desconocido", request, "no se pudo inferir el tipo de método; se muestra la request")]

    if spec.kind == "rule_based":
        return [("Sin prompt", request, "rule_based no usa LLM: la request se analiza con un parser de expresiones regulares")]

    if spec.kind in ("llm_only", "task"):
        try:
            net = nets.get(case_name, seed, k)
            if spec.kind == "task":
                from benchmarks.evaluate_llms import TASKS

                system, user = TASKS[spec.name].prompt_builder(case_name, net)
            else:
                from llm.prompt_variants import build_messages

                msgs = build_messages(spec.strategy, "llm_only", request, net, case_name, forced=bool(spec.forced))
                system, user = msgs[0]["content"], msgs[1]["content"]
        except Exception as exc:  # offline reconstruction must never break the report
            return [("Prompt no reconstruible", request, f"build_messages falló ({type(exc).__name__}: {exc}); se muestra la request")]
        note = f"strategy={spec.strategy}, forced={bool(spec.forced)}, sin herramientas" if spec.kind == "llm_only" else "task legado"
        blocks.append(("System prompt", system, note))
        blocks.append(("User prompt (primer item)", user, f"case={case_name}, seed={seed}, k={k}, request_id={row.get('request_id')}"))
        return blocks

    # engine methods
    from llm.engine import FINAL_ANSWER_INSTRUCTION, _plan_system_prompt
    from llm.prompts import SYSTEM_PROMPT_EN

    if spec.architecture == "single_call":
        try:
            from llm.prompt_variants import build_messages

            net = nets.get(case_name, seed, k)
            msgs = build_messages(spec.strategy, "single_call", request, net, case_name)
            blocks.append(("System prompt", msgs[0]["content"], f"strategy={spec.strategy}; la red ya está cargada (preload_case)"))
            blocks.append(("User prompt (primer item)", msgs[1]["content"], f"case={case_name}, seed={seed}, k={k}, request_id={row.get('request_id')}"))
        except Exception as exc:
            blocks.append(("Prompt no reconstruible", request, f"build_messages falló ({type(exc).__name__}: {exc}); se muestra la request"))
        blocks.append(("FINAL_ANSWER_INSTRUCTION (ronda final)", FINAL_ANSWER_INSTRUCTION, "se añade como mensaje de usuario antes de la respuesta final"))
        return blocks

    arch = f"architecture={spec.architecture}, gate={spec.gate}, memory={spec.memory}"
    blocks.append(("System prompt (SYSTEM_PROMPT_EN)", SYSTEM_PROMPT_EN, arch))
    blocks.append(("User prompt (primer item) = request_text", request, f"case={case_name}, seed={seed}, k={k}, request_id={row.get('request_id')}"))
    if spec.architecture == "plan_act":
        # v1 catalogue only: this reconstruction does not thread the row's actual
        # --tool-variant through (spec carries no such field), same as before the
        # 2026-09-21 fix that made the live prompt itself variant-aware.
        plan_prompt = _plan_system_prompt("v1")
        head = "\n".join(plan_prompt.splitlines()[:PLAN_PROMPT_HEAD_LINES])
        blocks.append(("PLAN_SYSTEM_PROMPT (cabecera)", head + "\n…", f"primeras {PLAN_PROMPT_HEAD_LINES} líneas de {len(plan_prompt)} caracteres; catálogo de tools omitido"))
        blocks.append(("FINAL_ANSWER_INSTRUCTION (ronda final)", FINAL_ANSWER_INSTRUCTION, "se añade tras ejecutar el plan"))
    return blocks


# --------------------------------------------------------------------------- traces


def load_trace_payload(row: dict[str, Any]) -> tuple[Optional[dict[str, Any]], str]:
    """(full trace file payload or None, source label)."""
    from benchmarks.rescore import load_full_trace

    report_dir = Path(row.get("_report_dir") or ".")
    payload = load_full_trace(row, [report_dir / "traces"])
    if payload is not None:
        return payload, "archivo de traza completo"
    return None, "traza truncada del report"


def _gate_text(gate: Any, enforced: Any) -> str:
    if not isinstance(gate, dict):
        return "gate: n/a (no es un resultado de flujo)"
    status = "PASS" if gate.get("passed") else "FAIL"
    reasons = ",".join(gate.get("reasons") or []) or "-"
    mm = gate.get("mismatch_mw")
    mm_s = f", mismatch={mm:.3g} MW" if _is_num(mm) else ""
    return f"gate: {status} (reasons={reasons}{mm_s}){' -> números retenidos' if enforced else ''}"


def render_rounds(trace: Optional[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    rounds = (trace or {}).get("rounds") or []
    if not rounds:
        lines.append("(sin rondas de herramientas: una sola llamada al LLM)")
    for rec in rounds:
        phase = rec.get("phase")
        tag = f"Ronda {rec.get('round')}" + (f" [{phase}]" if phase else "") + (" [final]" if rec.get("final") else "")
        lines.append(f"--- {tag} ---")
        llm = rec.get("llm")
        if isinstance(llm, dict):
            if llm.get("error"):
                lines.append(f"LLM error: {clip(llm['error'], LLM_TEXT_CHARS)}")
            content = llm.get("content")
            if content:
                lines.append(f"LLM: {clip(content, LLM_TEXT_CHARS)}")
            calls = llm.get("tool_calls") or []
            if calls and not rec.get("tools"):
                for tc in calls:
                    lines.append(f"tool_call: {tc.get('name')}({clip(tc.get('arguments'), 200)})")
        for tl in rec.get("tools") or []:
            args = tl.get("arguments")
            args_s = json.dumps(args, ensure_ascii=False, default=str) if isinstance(args, (dict, list)) else str(args)
            lines.append(f"tool: {tl.get('name')}({clip(args_s, 200)})")
            lines.append(f"  output: {clip(tl.get('output'), TOOL_OUTPUT_CHARS)}")
            lines.append(f"  {_gate_text(tl.get('gate'), tl.get('enforced'))}")
    if trace and trace.get("plan") is not None and not any(r.get("phase") == "plan" for r in rounds):
        lines.append(f"plan: {clip(json.dumps(trace['plan'], ensure_ascii=False), LLM_TEXT_CHARS)}")
    return lines


def _calls_text(calls: Any) -> str:
    if not calls:
        return "(ninguna)"
    parts = []
    for c in calls:
        if isinstance(c, dict):
            parts.append(f"{c.get('tool') or c.get('name')}({json.dumps(c.get('args') or {}, ensure_ascii=False)})")
        else:
            parts.append(str(c))
    return " -> ".join(parts)


def _flags(row: dict[str, Any]) -> list[str]:
    flags = []
    for key, label in (
        ("claimed_success_on_failure", "claimed_success_on_failure"),
        ("stale_state", "stale_state"),
        ("abstained", "abstained"),
        ("abstained_on_solvable", "abstained_on_solvable"),
    ):
        if row.get(key) is True:
            flags.append(label)
    return flags


def _has_failure_flag(row: dict[str, Any]) -> bool:
    return bool(_flags(row))


def select_examples(rows: list[dict[str, Any]], max_examples: int) -> list[tuple[str, dict[str, Any]]]:
    """Up to ``max_examples`` items: one solved, one failed formulation, one with a failure flag, then fill."""
    ordered = sorted(rows, key=lambda r: (case_buses(str(r.get("case_name"))), str(r.get("request_id")), int(r.get("run") or 0)))
    chosen: list[tuple[str, dict[str, Any]]] = []
    used: set[int] = set()

    def pick(label: str, pred: Any) -> None:
        if len(chosen) >= max_examples:
            return
        for r in ordered:
            if id(r) not in used and pred(r):
                chosen.append((label, r))
                used.add(id(r))
                return

    pick("resuelto (solved=True)", lambda r: r.get("solved") is True)
    pick("formulación fallida (formulation_exact=False)", lambda r: r.get("formulation_exact") is False)
    pick("con bandera de fallo (claimed/stale/abstained)", _has_failure_flag)
    pick("no resuelto", lambda r: r.get("solved") is not True)
    pick("primer item", lambda r: True)
    return chosen


def render_example(label: str, row: dict[str, Any]) -> str:
    payload, source = load_trace_payload(row)
    trace = (payload or {}).get("trace") if payload else row.get("trace")
    answer = (payload or {}).get("answer") if payload else None
    if answer is None:
        answer = row.get("raw_response")
    if answer is None and trace:
        answer = trace.get("final_text")
    body: list[str] = []
    body.append(f"request ({row.get('request_id')}, {row.get('case_name')}, difficulty={row.get('difficulty')}, seed={row.get('seed')}): {row.get('request_text')}")
    body.append(f"intended_calls: {_calls_text(row.get('intended_calls'))}")
    if row.get("executed_calls") is not None:
        executed = _calls_text(row.get("executed_calls"))
    elif not (trace or {}).get("rounds") and not int(row.get("n_tool_calls") or 0):
        executed = "(sin etapa de tools)"
    else:
        executed = "(no disponibles: formulation_failure o error)"
    body.append(f"executed_calls: {executed}")
    body.append(f"fuente de la traza: {source}")
    body.extend(render_rounds(trace))
    body.append("--- Respuesta final ---")
    body.append(clip(answer, FINAL_ANSWER_CHARS) if answer else "(sin respuesta)")
    body.append("--- Scoring ---")
    m = row.get("metrics") or {}
    body.append(
        "formulation="
        + str(row.get("formulation_error_type") if row.get("formulation_error_type") is not None else "n/a")
        + f" (exact={row.get('formulation_exact')}); V_MAE={fmt_sci(m.get('voltage_mae'))}; F_MAE={fmt_fixed(m.get('flow_mae'), 2)}; "
        + f"faithful={fmt_pct(row.get('faithful_numbers'))} %; solved={row.get('solved')} ({row.get('solved_reason')}); "
        + f"flags={','.join(_flags(row)) or '-'}; error={classify_error(row.get('error')) or '-'}; "
        + f"tokens={fmt_int((row.get('prompt_tokens') or 0) + (row.get('completion_tokens') or 0))}; cost_usd={fmt_usd(row.get('cost_usd'))}; "
        + f"wall={fmt_fixed(row.get('wall_time_s'), 1)} s"
    )
    return f"**Ejemplo: {label}**\n\n" + code_block("\n".join(body))


# --------------------------------------------------------------------------- sections


def section_what_ran(exp: Experiment) -> str:
    rows = exp.rows
    cfgs = [rep.config for rep in exp.reports]
    lines = [SECTION_TITLES[0], ""]
    lines.append("Directorio analizado:\n")
    lines.append(code_block(str(exp.root)))
    lines.append(f"- Reports leídos: {len(exp.reports)} (`{RESCORED_NAME}` usado en {sum(r.rescored for r in exp.reports)}; el resto `report.json`)")
    lines.append(f"- Modelos: {', '.join(f'`{m}`' for m in exp.models()) or MISSING}")
    lines.append(f"- Métodos: {', '.join(f'`{m}`' for m in exp.methods()) or MISSING}")
    lines.append(f"- Casos: {', '.join(f'`{c}`' for c in exp.cases()) or MISSING}")
    req = [c.get("requests") for c in cfgs if c.get("requests")]
    if req:
        srcs = Counter(json.dumps(r, sort_keys=True) for r in req)
        for js, n in srcs.items():
            r = json.loads(js)
            if r.get("source") == "generated":
                lines.append(
                    f"- Requests: generadas, N={r.get('n_per_case_seed')} por caso y seed, difficulties={r.get('difficulties') or 'todas'} ({n} report{'s' if n > 1 else ''})"
                )
            else:
                lines.append(f"- Requests: archivo `{r.get('source')}` ({n} report{'s' if n > 1 else ''})")
    else:
        lines.append("- Requests: request por defecto (sin generador)")
    diffs = exp.difficulties()
    if diffs:
        cnt = Counter(str(r.get("difficulty")) for r in rows)
        lines.append("- Items por dificultad: " + ", ".join(f"{d}={cnt.get(d, 0)}" for d in diffs))
    # Which exact system-prompt text produced these rows -- runs are attributable to a model,
    # case and seed but not to the prompt they were given, and a wording change (e.g. the
    # 2026-09-17 bus-indexing fix) otherwise makes two runs of the "same" method silently
    # incomparable. None means rule_based (no LLM system prompt) or a row from before this
    # field existed.
    hash_rows = [r for r in rows if r.get("system_prompt_hash")]
    if hash_rows:
        hash_cnt = Counter(str(r.get("system_prompt_hash")) for r in hash_rows)
        n_no_hash = len(rows) - len(hash_rows)
        if len(hash_cnt) == 1:
            (h, n), = hash_cnt.items()
            lines.append(f"- System prompt: hash `{h}` ({n} filas)" + (f"; {n_no_hash} filas sin hash (rule_based u otro método sin prompt)" if n_no_hash else ""))
        else:
            lines.append(
                "- **System prompt: MULTIPLE hashes en este reporte** -- "
                + ", ".join(f"`{h}`={n}" for h, n in sorted(hash_cnt.items()))
                + (f"; {n_no_hash} filas sin hash" if n_no_hash else "")
                + ". Los métodos de este reporte no vieron el mismo prompt; comparar columnas entre ellos no es apples-to-apples."
            )

    def _uniq(key: str) -> str:
        vals = sorted({json.dumps(c.get(key), sort_keys=True) for c in cfgs})
        return ", ".join(vals)

    lines.append(f"- runs por item: {_uniq('runs')}; k (perturbación ±10 %·k): {_uniq('k')}; seeds: {_uniq('seeds')}; max_rounds: {_uniq('max_rounds')}; temperature: {_uniq('temperature')}; timeout_s: {_uniq('timeout_s')}")
    mtimes = [rep.mtime for rep in exp.reports]
    if mtimes:
        lo, hi = min(mtimes), max(mtimes)
        lines.append(f"- Fecha de la corrida (mtime de report.json): {_fmt_date(lo)}" + (f" – {_fmt_date(hi)}" if hi - lo > 60 else ""))
    cost = sum(float(r.get("cost_usd") or 0.0) for r in rows)
    n_ok = sum(1 for r in rows if r.get("ok"))
    n_err = sum(1 for r in rows if r.get("error"))
    lines.append(f"- Costo total: {cost:.4f} USD ({len(rows)} items; costo medio {cost / len(rows) if rows else 0:.5f} USD/item)")
    toks = sum(int(r.get("prompt_tokens") or 0) + int(r.get("completion_tokens") or 0) for r in rows)
    lines.append(f"- Items totales: {len(rows)}; ok={n_ok}; con error={n_err}; tokens totales={toks}")
    lines.append(f"- Solved global: {_rate(sum(1 for r in rows if r.get('solved') is True), len(rows))}")
    errs = Counter(classify_error(r.get("error")) for r in rows if r.get("error"))
    lines.append("")
    lines.append("Errores por tipo:")
    lines.append("")
    if errs:
        err_rows = []
        for label, n in errs.most_common():
            methods = Counter(str(r.get("method")) for r in rows if classify_error(r.get("error")) == label)
            err_rows.append([label, n, ", ".join(f"{m} ({c})" for m, c in methods.most_common())])
        lines.append(md_table(["Tipo", "Items", "Métodos afectados"], err_rows))
    else:
        lines.append("_(ningún item con `error`)_\n")
    return "\n".join(lines) + "\n"


def section_prompts(exp: Experiment) -> str:
    lines = [SECTION_TITLES[1], ""]
    lines.append(
        "Los prompts se reconstruyen offline con el mismo código del runner (`llm.prompt_variants.build_messages` "
        "sobre la red perturbada con el seed del item). Las tablas de datos del caso se recortan a sus primeras "
        f"{TABLE_LINES_KEPT} líneas con un marcador `…`; el número de caracteres indicado corresponde al prompt completo. "
        "**Esta reconstrucción es ilustrativa, no histórica**: usa el código de `llm/prompts.py` de HOY, así que si el "
        "texto del prompt cambió después de que esta corrida se generó, lo que se ve aquí no es lo que el modelo "
        "recibió. El registro histórico real es el hash por fila (`system_prompt_hash`, ver sección 1 / "
        "`benchmarks/experiment_report.py::section_what_ran`), fijado en el momento de la corrida y nunca recalculado.\n"
    )
    nets = NetCache()
    rows = exp.rows
    for method in exp.methods():
        mrows = sorted(
            (r for r in rows if str(r.get("method")) == method),
            key=lambda r: (case_buses(str(r.get("case_name"))), str(r.get("request_id")), int(r.get("run") or 0)),
        )
        if not mrows:
            continue
        first = mrows[0]
        row_hash = first.get("system_prompt_hash")
        lines.append(f"### Método `{method}`" + (f" (system_prompt_hash real de esta fila: `{row_hash}`)" if row_hash else "") + "\n")
        for title, text, note in reconstruct_prompts(method, first, nets):
            shown = truncate_case_tables(text) if title.startswith("User prompt") else text
            reconstructed_note = " (reconstrucción con el código actual, no necesariamente histórica)" if title.startswith("System prompt") else ""
            lines.append(f"**{title}**{reconstructed_note} — {len(text)} caracteres" + (f"; {note}" if note else "") + "\n")
            lines.append(code_block(shown))
    return "\n".join(lines) + "\n"


_PROTOCOL_COLUMNS = [(c.name, c.keys, c.fmt) for c in COLUMNS]


def _rate_counts(items: list[dict[str, Any]], name: str) -> tuple[Optional[int], Optional[int]]:
    """(count, total) an item-level rate column was computed over, so a small-N run
    (e.g. N=5) never shows a bare "80.0" that reads as more precise than 4/5 is."""
    if name == "Form.":
        vals = [r.get("formulation_exact") for r in items]
        return sum(1 for v in vals if v is True), sum(1 for v in vals if v is not None)
    if name == "Solved":
        return sum(1 for r in items if r.get("solved") is True), len(items)
    if name == "Solver status":
        vals = [(r.get("metrics") or {}).get("convergence_match") for r in items if r.get("ok")]
        return sum(1 for v in vals if v), len(vals)
    if name == "SFR":
        vals = [r.get("safe_failure") for r in items]
        return sum(1 for v in vals if v is True), sum(1 for v in vals if v is not None)
    if name == "Faith.":
        # Per-answer (V4 and V5 together), not the per-number mean this used to be --
        # every item counts (an answer with no numbers, or no mutation, passes vacuously).
        vals = [r.get("faithful_answers") for r in items]
        return sum(1 for v in vals if v is True), sum(1 for v in vals if v is not None)
    if name == "Claim":
        vals = [r.get("claimed_success_on_failure") for r in items]
        return sum(1 for v in vals if v is True), sum(1 for v in vals if v is not None)
    if name == "Escalated":
        vals = [r.get("escalated") for r in items]
        return sum(1 for v in vals if v is True), len(items)
    if name == "Wrong (silent)":
        vals = [r.get("wrong_silently") for r in items]
        return sum(1 for v in vals if v is True), len(items)
    return None, None


def _pct_cell(val: Any, items: list[dict[str, Any]], name: str) -> str:
    text = fmt_pct(val)
    if text == MISSING:
        return text
    count, total = _rate_counts(items, name)
    return f"{text} ({count}/{total})" if total else text


def _protocol_cells(row: dict[str, Any], items: list[dict[str, Any]]) -> list[str]:
    # Claim / Escalated / Wrong (silent) are not paper-table columns (metricas_pfagent_
    # definiciones.md: they stay in the JSON and REPORT.md, not the LaTeX tables), but
    # the report still shows them here.
    cells = []
    for name, keys, fmt in _PROTOCOL_COLUMNS:
        val = _first_key(row, keys)
        if name == "Calls" and str(row.get("method", "")).startswith(("llm_only", "baseline_pf", "blueprint_pf")):
            cells.append("n/a")
        elif name == "Tok." and str(row.get("method")) == "rule_based":
            cells.append("n/a")
        elif fmt == "pct":
            cells.append(_pct_cell(val, items, name))
        else:
            cells.append(format_value(val, fmt))
    cells.append(_pct_cell(_first_key(row, ("claimed_success_on_failure_rate",)), items, "Claim"))
    # Escalated / Wrong (silent) / Solved (already a _PROTOCOL_COLUMNS entry) sum to
    # 100%: where every request in this row ends up. See benchmarks.scoring.escalation_check
    # -- replaces the old "Abst." (abstained_on_solvable), which mixed in a text heuristic
    # for methods with no actual handoff mechanism.
    cells.append(_pct_cell(_first_key(row, ("escalated_rate",)), items, "Escalated"))
    cells.append(_pct_cell(_first_key(row, ("wrong_silently_rate",)), items, "Wrong (silent)"))
    cells.append(fmt_usd(_first_key(row, ("cost_usd_total",))))
    return cells


def _protocol_header(with_model: bool, with_case: bool) -> list[str]:
    head = (["Model"] if with_model else []) + ["Method"] + (["Case"] if with_case else []) + ["N"]
    for name, _, _ in _PROTOCOL_COLUMNS:
        head.append(name)
    head.append("Claim")
    head.append("Escalated")
    head.append("Wrong (silent)")
    head.append("$")
    return head


def section_results(exp: Experiment) -> str:
    lines = [SECTION_TITLES[2], ""]
    lines.append(
        "Columnas del protocolo (medias por método × caso, del `scoreboard_per_case`), en los 4 grupos de "
        "`metricas_pfagent_definiciones.md`: **utilidad de tarea** Form. (formulación exacta de las tool calls), "
        "V_MAE (p.u., solo sobre peticiones con formulación exacta -- toda fila con herramientas que llega al "
        "solver con la formulación correcta da exactamente cero, ver benchmarks/scoring.py) y F_MAE (MW) sobre "
        "los items con resultado, Solved (respondió correctamente de extremo a "
        "extremo); **corrección solver-grounded** Solver status (convergencia reportada = convergencia real), "
        "B_mean (residual medio de KCL de los flujos reportados, MW); **fidelidad** Faith. (por respuesta, no "
        "por número: fracción de respuestas donde todo número es trazable a una salida de tool Y viene del "
        "solve posterior al último cambio de red) y SFR (fallos declarados con seguridad); **costo** Calls (tool "
        "calls medias) y Tok. (tokens medios). Fuera de los 4 grupos, solo en este reporte (no en las tablas del "
        "paper): Claim (éxito reclamado sobre un fallo), Escalated y Wrong (silent). Escalated y Wrong (silent) "
        "junto con solved_autonomously_rate (no la columna Solved de arriba, que puede solaparse con Escalated "
        "-- una abstención de verificación puede caer sobre un item cuyo cálculo de fondo sí era correcto) "
        "suman 100 %: dónde termina cada petición -- resuelta sola, entregada a una persona, o mal contestada sin "
        "aviso; solo cuenta como Escalated una arquitectura con mecanismo de traspaso real, ver "
        "benchmarks.scoring.escalation_check) y $ (costo total "
        "USD). Porcentajes en %.\n"
    )
    per_case = exp.per_case
    rows = exp.rows
    models = exp.models()
    with_model = len(models) > 1
    # several models: short aliases keep the 17-column table within the page width (legend below)
    alias = {m: f"M{i + 1}" for i, m in enumerate(models)} if with_model else {}
    legend = "Modelos: " + "; ".join(f"{alias[m]} = `{m}`" for m in models) + "\n" if with_model else ""
    table_rows = []
    for r in sorted(per_case, key=lambda r: (str(r.get("model")), _method_sort_key(str(r.get("method"))), case_buses(str(r.get("case_name"))))):
        lead = ([alias.get(str(r.get("model")), str(r.get("model")))] if with_model else []) + [str(r.get("method")), str(r.get("case_name")), fmt_int(r.get("n_items"))]
        row_items = [x for x in rows if str(x.get("model")) == str(r.get("model")) and str(x.get("method")) == str(r.get("method")) and str(x.get("case_name")) == str(r.get("case_name"))]
        table_rows.append(lead + _protocol_cells(r, row_items))
    lines.append("### Por método × caso\n")
    if legend:
        lines.append(legend)
    lines.append(md_table(_protocol_header(with_model, True), table_rows))

    if len(exp.cases()) > 1:
        lines.append("### Agregado por método (media ponderada por items sobre todos los casos)\n")
        agg_rows = []
        for model in models:
            mrows = [r for r in per_case if str(r.get("model")) == model and r.get("case_name")]
            for method, agg in sorted(aggregate_all(mrows).items(), key=lambda kv: _method_sort_key(kv[0])):
                items = [r for r in rows if str(r.get("model")) == model and str(r.get("method")) == method]
                claim_rate = bm.rate([r.get("claimed_success_on_failure") for r in items])["rate"]
                escalated_rate = bm.rate([r.get("escalated") for r in items])["rate"]
                wrong_silently_rate = bm.rate([r.get("wrong_silently") for r in items])["rate"]
                cells = []
                for name, _, fmt in _PROTOCOL_COLUMNS:
                    if name == "Calls" and method.startswith(("llm_only", "baseline_pf", "blueprint_pf")):
                        cells.append("n/a")
                    elif name == "Tok." and method == "rule_based":
                        cells.append("n/a")
                    elif fmt == "pct":
                        cells.append(_pct_cell(agg.get(name), items, name))
                    else:
                        cells.append(format_value(agg.get(name), fmt))
                cells.append(_pct_cell(claim_rate, items, "Claim"))
                cells.append(_pct_cell(escalated_rate, items, "Escalated"))
                cells.append(_pct_cell(wrong_silently_rate, items, "Wrong (silent)"))
                cost = sum(float(r.get("cost_usd_total") or 0.0) for r in mrows if str(r.get("method")) == method)
                cells.append(fmt_usd(cost))
                agg_rows.append(([alias.get(model, model)] if with_model else []) + [method, f"{agg['n_cases']} casos", fmt_int(agg["n_items"])] + cells)
        if legend:
            lines.append(legend)
        lines.append(md_table(_protocol_header(with_model, True), agg_rows))

    diffs = exp.difficulties()
    if diffs:
        lines.append("### Formulación exacta por dificultad (items con etapa de tools; `n/a` = sin tools)\n")
        frows = []
        for method in exp.methods():
            cells = [method]
            for d in diffs:
                sub = [r for r in rows if str(r.get("method")) == method and str(r.get("difficulty")) == d and r.get("formulation_exact") is not None]
                n_ok = sum(1 for r in sub if r.get("formulation_exact") is True)
                cells.append(f"{100.0 * n_ok / len(sub):.1f} ({n_ok}/{len(sub)})" if sub else "n/a")
            frows.append(cells)
        lines.append(md_table(["Method"] + list(diffs), frows))
        lines.append("### Solved por dificultad (%, items resueltos / items)\n")
        srows = []
        for method in exp.methods():
            cells = [method]
            for d in diffs:
                sub = [r for r in rows if str(r.get("method")) == method and str(r.get("difficulty")) == d]
                n_ok = sum(1 for r in sub if r.get("solved") is True)
                cells.append(f"{100.0 * n_ok / len(sub):.1f} ({n_ok}/{len(sub)})" if sub else MISSING)
            srows.append(cells)
        lines.append(md_table(["Method"] + list(diffs), srows))

    verif_methods = [m for m in exp.methods() if any(r.get("verification_outcome") is not None for r in rows if str(r.get("method")) == m)]
    if verif_methods:
        lines.append(
            "### Verificación final (pfagent: V(x,c,z,y) aplicado a la respuesta final)\n\n"
            "`pass_first` = pasó al primer intento; `pass_retry` = pasó tras el único reintento con el veredicto "
            "añadido; `abstained` = falló dos veces, respuesta forzada a fallo declarado sin números; "
            "`retry_mutation` = el reintento intentó una herramienta que muta la red (bloqueada, nunca ejecutada; "
            "cuenta como abstención) — ver \"Integridad del reintento\" abajo. N = items con `final_gate` activo "
            "(no todos los métodos lo tienen).\n"
        )
        vrows = []
        for method in verif_methods:
            outcomes = [str(r.get("verification_outcome")) for r in rows if str(r.get("method")) == method and r.get("verification_outcome") is not None]
            n = len(outcomes)
            cnt = Counter(outcomes)
            def _voutcome(key: str) -> str:
                if not n:
                    return MISSING
                c = cnt.get(key, 0)
                return f"{fmt_pct(c / n)} ({c}/{n})"

            vrows.append(
                [
                    method,
                    fmt_int(n),
                    _voutcome("pass_first"),
                    _voutcome("pass_retry"),
                    _voutcome("abstained"),
                    _voutcome("abstained_retry_mutation"),
                ]
            )
        lines.append(md_table(["Method", "N", "pass_first", "pass_retry", "abstained", "retry_mutation"], vrows))

        n_mutation_attempts = sum(1 for r in rows if r.get("verification_outcome") == "abstained_retry_mutation")
        if n_mutation_attempts or any(r.get("verification_attempts") == 2 for r in rows):
            n_retried = sum(1 for r in rows if (r.get("verification_attempts") or 0) >= 2)
            lines.append(
                "\n### Integridad del reintento\n\n"
                f"De {n_retried} ítem(s) que llegaron a un reintento, {n_mutation_attempts} intentaron una "
                "herramienta que muta la red (bloqueada) en vez de corregir el reporte; se cuentan como "
                "abstención, no como \"pasó\". El mensaje de reintento ya no sugiere la corrección específica "
                "(p. ej. \"reconnect...\") y bloquea estructuralmente `modify_load`, `disconnect_line`, "
                "`reconnect_line`, `apply_remedial_action` y `load_case` mientras el reintento está en efecto.\n"
            )

    lines.append("### Tipos de error de formulación (conteo de items)\n")
    ftypes = sorted({str(r.get("formulation_error_type")) for r in rows if r.get("formulation_error_type") is not None})
    if ftypes:
        trows = []
        for method in exp.methods():
            cnt = Counter(str(r.get("formulation_error_type")) for r in rows if str(r.get("method")) == method and r.get("formulation_error_type") is not None)
            if cnt:
                trows.append([method] + [cnt.get(t, 0) for t in ftypes])
        lines.append(md_table(["Method"] + ftypes, trows))
    else:
        lines.append("_(ningún item con `formulation_error_type`)_\n")

    lines.append("### Errores de ejecución por método (conteo de items con `error`)\n")
    etypes = sorted({classify_error(r.get("error")) for r in rows if r.get("error")}, key=str)
    if etypes:
        erows = []
        for method in exp.methods():
            cnt = Counter(classify_error(r.get("error")) for r in rows if str(r.get("method")) == method and r.get("error"))
            if cnt:
                erows.append([method] + [cnt.get(t, 0) for t in etypes])
        lines.append(md_table(["Method"] + [str(t) for t in etypes], erows))
    else:
        lines.append("_(ningún item con `error`)_\n")
    return "\n".join(lines) + "\n"


def section_examples(exp: Experiment, max_examples: int) -> str:
    lines = [SECTION_TITLES[3], ""]
    lines.append(
        f"Hasta {max_examples} items por método: uno resuelto, uno con formulación fallida (si existe) y uno con alguna bandera de fallo "
        f"(claimed_success_on_failure, stale_state, abstained). Texto del LLM recortado a {LLM_TEXT_CHARS} caracteres, salidas de tools a "
        f"{TOOL_OUTPUT_CHARS}, respuesta final a {FINAL_ANSWER_CHARS}. Se lee la traza completa de `traces/` cuando existe.\n"
    )
    rows = exp.rows
    for method in exp.methods():
        mrows = [r for r in rows if str(r.get("method")) == method]
        lines.append(f"### Método `{method}`\n")
        for label, row in select_examples(mrows, max_examples):
            lines.append(render_example(label, row))
    return "\n".join(lines) + "\n"


def derive_observations(exp: Experiment) -> list[str]:
    """Bullet observations computed strictly from the numbers (no speculation)."""
    rows = exp.rows
    per_case = exp.per_case
    obs: list[str] = []
    if not rows:
        return ["Sin items."]

    def kind_of(method: str) -> str:
        spec = _method_spec(method)
        return spec.kind if spec else "unknown"

    def is_forced(method: str) -> bool:
        spec = _method_spec(method)
        return bool(spec and getattr(spec, "forced", False))

    methods = exp.methods()
    tool_methods = [m for m in methods if kind_of(m) in ("engine", "rule_based")]
    llm_only_methods = [m for m in methods if kind_of(m) in ("llm_only", "task")]

    # solver-grounded accuracy
    solver_rows = [r for r in per_case if str(r.get("method")) in tool_methods and _is_num(r.get("voltage_mae_mean"))]
    if solver_rows:
        worst = max(solver_rows, key=lambda r: r["voltage_mae_mean"])
        if worst["voltage_mae_mean"] < 1e-4:
            obs.append(
                f"Todos los métodos que llegan al solver ({', '.join(sorted({str(r['method']) for r in solver_rows}))}) tienen "
                f"V_MAE < 1e-4 p.u. en todos los casos (máximo {fmt_sci(worst['voltage_mae_mean'])} en {worst['method']}/{worst['case_name']})."
            )
        else:
            above = [f"{r['method']}/{r['case_name']} ({fmt_sci(r['voltage_mae_mean'])})" for r in solver_rows if r["voltage_mae_mean"] >= 1e-4]
            obs.append(f"V_MAE >= 1e-4 p.u. en {len(above)} filas método×caso con solver: {', '.join(above)}.")
    lo_rows = [r for r in per_case if str(r.get("method")) in llm_only_methods and _is_num(r.get("voltage_mae_mean"))]
    if lo_rows:
        best = min(lo_rows, key=lambda r: r["voltage_mae_mean"])
        worst = max(lo_rows, key=lambda r: r["voltage_mae_mean"])
        obs.append(
            f"LLM-only: V_MAE entre {fmt_sci(best['voltage_mae_mean'])} ({best['method']}/{best['case_name']}) y "
            f"{fmt_sci(worst['voltage_mae_mean'])} ({worst['method']}/{worst['case_name']}) p.u. sobre los items que devolvieron números."
        )
    elif llm_only_methods:
        obs.append("LLM-only: ningún método×caso tiene V_MAE (ningún item devolvió tensiones comparables).")

    # abstention in LLM-only
    lo_items = [r for r in rows if str(r.get("method")) in llm_only_methods]
    if lo_items:
        n_abs = sum(1 for r in lo_items if r.get("abstained") is True)
        obs.append(f"{_rate(n_abs, len(lo_items))} de abstención en LLM-only (respuesta con `converged=false` o arrays vacíos).")
        forced = [r for r in lo_items if is_forced(str(r.get("method")))]
        free = [r for r in lo_items if not is_forced(str(r.get("method")))]
        if forced and free:
            obs.append(
                f"Abstención con cláusula de escape: {_rate(sum(1 for r in free if r.get('abstained') is True), len(free))}; "
                f"sin cláusula (forced): {_rate(sum(1 for r in forced if r.get('abstained') is True), len(forced))}."
            )
        n_conv_mismatch = sum(1 for r in lo_items if r.get("solved_reason") == "convergence_mismatch")
        n_verr = sum(1 for r in lo_items if r.get("solved_reason") == "voltage_error")
        if n_conv_mismatch or n_verr:
            obs.append(f"En LLM-only, {n_conv_mismatch} items no resueltos por `convergence_mismatch` y {n_verr} por `voltage_error`.")

    # gate
    g_checked = sum(int(r.get("gate_checked") or 0) for r in rows)
    g_failed = sum(int(r.get("gate_failed") or 0) for r in rows)
    g_enforced = sum(int(r.get("gate_enforced") or 0) for r in rows)
    if g_checked:
        n_items_enf = sum(1 for r in rows if int(r.get("gate_enforced") or 0) > 0)
        obs.append(
            f"El gate verificó {g_checked} resultados de flujo, {g_failed} fallaron la verificación y se activó (retuvo números) "
            f"{g_enforced} veces en {n_items_enf} items."
        )
    elif tool_methods:
        obs.append("El gate no verificó ningún resultado de flujo (gate_checked=0 en todos los items).")

    # errors
    errs = Counter(classify_error(r.get("error")) for r in rows if r.get("error"))
    for label, n in errs.most_common():
        if str(label).startswith("APIStatusError 402"):
            obs.append(f"{n} items fallaron por crédito: {label}; cuentan como no resueltos (`run_failed`).")
        elif label == "GroundTruthNotConverged":
            obs.append(f"{n} items con `GroundTruthNotConverged`: la verdad de referencia no convergió y el item no puntúa.")
        elif label == "formulation_failure":
            obs.append(f"{n} items con `formulation_failure`: el método no formuló ninguna tool call.")
        elif label == "json_parse_failed":
            obs.append(f"{n} items con `json_parse_failed`: la respuesta LLM-only no fue JSON parseable.")
        else:
            obs.append(f"{n} items con error `{label}`.")
    if not errs:
        obs.append("Ningún item terminó con `error`.")

    # solved per method
    solved_by = {}
    for m in methods:
        sub = [r for r in rows if str(r.get("method")) == m]
        solved_by[m] = (sum(1 for r in sub if r.get("solved") is True), len(sub))
    ranked = sorted(solved_by.items(), key=lambda kv: (kv[1][0] / kv[1][1]) if kv[1][1] else -1.0)
    if len(ranked) >= 2:
        (wm, (wn, wd)), (bm_, (bn, bd)) = ranked[0], ranked[-1]
        obs.append(f"Solved más alto: `{bm_}` {_rate(bn, bd)}; más bajo: `{wm}` {_rate(wn, wd)}.")
    elif ranked:
        m, (n, d) = ranked[0]
        obs.append(f"Solved de `{m}`: {_rate(n, d)}.")

    # formulation per difficulty (tool methods)
    tool_items = [r for r in rows if str(r.get("method")) in tool_methods and r.get("formulation_exact") is not None]
    if tool_items:
        n_ok = sum(1 for r in tool_items if r.get("formulation_exact") is True)
        obs.append(f"Formulación exacta agregada sobre métodos con tools: {_rate(n_ok, len(tool_items))}.")
        by_d = {}
        for d in exp.difficulties():
            sub = [r for r in tool_items if str(r.get("difficulty")) == d]
            if sub:
                by_d[d] = (sum(1 for r in sub if r.get("formulation_exact") is True), len(sub))
        if len(by_d) >= 2:
            worst_d = min(by_d.items(), key=lambda kv: kv[1][0] / kv[1][1])
            best_d = max(by_d.items(), key=lambda kv: kv[1][0] / kv[1][1])
            obs.append(f"Formulación por dificultad: mejor `{best_d[0]}` {_rate(*best_d[1])}, peor `{worst_d[0]}` {_rate(*worst_d[1])}.")
        ftypes = Counter(str(r.get("formulation_error_type")) for r in tool_items if r.get("formulation_exact") is False)
        if ftypes:
            obs.append("Errores de formulación más frecuentes: " + ", ".join(f"`{t}`={n}" for t, n in ftypes.most_common(3)) + ".")

    # claimed success / stale
    claimed = [r for r in rows if r.get("claimed_success_on_failure") is True]
    if claimed:
        by_m = Counter(str(r.get("method")) for r in claimed)
        obs.append(f"{len(claimed)} items reclamaron éxito sobre un fallo (claimed_success_on_failure): " + ", ".join(f"`{m}`={n}" for m, n in by_m.most_common()) + ".")
    else:
        obs.append("Ningún item reclamó éxito sobre un fallo (claimed_success_on_failure=0).")
    n_fail = sum(1 for r in rows if r.get("is_failure") is True)
    if n_fail:
        n_safe = sum(1 for r in rows if r.get("safe_failure") is True)
        obs.append(f"De {n_fail} items en estado de fallo, {n_safe} lo declararon de forma segura (SFR {_rate(n_safe, n_fail)}).")
    stale = [r for r in rows if r.get("stale_state") is True]
    n_mut = sum(1 for r in rows if r.get("has_mutation") is True)
    if n_mut:
        obs.append(f"{len(stale)} de {n_mut} items con mutación de red reportaron estado obsoleto (stale_state).")

    # faithfulness
    def _mean(vals: list[float]) -> Optional[float]:
        return sum(vals) / len(vals) if vals else None

    f_tools = _mean([float(r["faithful_numbers"]) for r in rows if str(r.get("method")) in tool_methods and _is_num(r.get("faithful_numbers"))])
    f_lo = _mean([float(r["faithful_numbers"]) for r in rows if str(r.get("method")) in llm_only_methods and _is_num(r.get("faithful_numbers"))])
    if f_tools is not None and f_lo is not None:
        obs.append(f"Trazabilidad de números (Faith.): {fmt_pct(f_tools)} % con tools frente a {fmt_pct(f_lo)} % en LLM-only.")
    elif f_tools is not None:
        obs.append(f"Trazabilidad de números (Faith.) media con tools: {fmt_pct(f_tools)} %.")
    elif f_lo is not None:
        obs.append(f"Trazabilidad de números (Faith.) media en LLM-only: {fmt_pct(f_lo)} % (sin tools, todo número es no trazable salvo los copiados de la request).")

    # non-converged expectations (stress)
    nc = [r for r in rows if r.get("expected_outcome") and r.get("expected_outcome") != "converged"]
    if nc:
        n_match = sum(1 for r in nc if r.get("solved") is True)
        reasons = Counter(str(r.get("solved_reason")) for r in nc if r.get("solved") is True)
        kinds = Counter(str(r.get("expected_outcome")) for r in nc)
        obs.append(
            f"{len(nc)} items esperaban un resultado no convergido ({', '.join(f'{k}={n}' for k, n in kinds.most_common())}); "
            f"el método lo declaró correctamente (solved) en {_rate(n_match, len(nc))}"
            + (f", con solved_reason {', '.join(f'`{k}`={n}' for k, n in reasons.most_common())}" if reasons else "")
            + "."
        )

    # cost and tokens
    cost_by = Counter()
    for r in rows:
        cost_by[str(r.get("method"))] += float(r.get("cost_usd") or 0.0)
    total = sum(cost_by.values())
    if total > 0:
        m, c = cost_by.most_common(1)[0]
        obs.append(f"Costo total {total:.4f} USD; el método más caro fue `{m}` con {c:.4f} USD ({100.0 * c / total:.0f} %).")
    calls = [float(r.get("n_tool_calls") or 0) for r in rows if str(r.get("method")) in tool_methods]
    if calls:
        obs.append(f"Métodos con tools: {sum(calls) / len(calls):.2f} tool calls medias por item (máximo {int(max(calls))}).")

    # models
    models = exp.models()
    if len(models) > 1:
        parts = []
        for model in models:
            sub = [r for r in rows if str(r.get("model")) == model]
            parts.append(f"`{model}` {_rate(sum(1 for r in sub if r.get('solved') is True), len(sub))}")
        obs.append("Solved por modelo: " + "; ".join(parts) + ".")
    return obs


def section_readings(exp: Experiment) -> str:
    lines = [SECTION_TITLES[4], ""]
    lines.append("Observaciones generadas automáticamente a partir de los números del report (sin interpretación):\n")
    lines.extend(f"- {o}" for o in derive_observations(exp))
    return "\n".join(lines) + "\n"


def section_files(exp: Experiment) -> str:
    """Absolute paths in a verbatim block (inline code cannot be line-broken in the PDF)."""
    lines = [SECTION_TITLES[5], ""]
    lines.append(f"Rutas absolutas bajo `{exp.root.name}`. `report.rescored.json` (cuando existe) es el archivo leído para las métricas.\n")
    body: list[str] = []
    for rep in exp.reports:
        body.append(f"report: {rep.original}" + (f"   [leído: {rep.path.name}]" if rep.rescored else ""))
        for name in ("scoreboard.json", "scoreboard.csv", "scoreboard.md", "scoreboard_per_case.json", "scoreboard.rescored.json", "scoreboard_per_case.rescored.json"):
            if (rep.report_dir / name).is_file():
                body.append(f"  {name}: {rep.report_dir / name}")
        traces = rep.report_dir / "traces"
        if traces.is_dir():
            n = sum(1 for _ in traces.rglob("*.json"))
            body.append(f"  traces ({n} archivos): {traces}")
        for log in sorted(rep.report_dir.glob("*.log")):
            body.append(f"  log: {log}")
    logs_dir = exp.root / "logs"
    if logs_dir.is_dir():
        for log in sorted(logs_dir.glob("*.log")):
            body.append(f"log: {log}")
    for extra in ("per_system.csv", "scaling.csv"):
        if (exp.root / extra).is_file():
            body.append(f"{extra}: {exp.root / extra}")
    lines.append(code_block("\n".join(body)))
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- assembly


def build_report(exp: Experiment, max_examples: int = 3) -> str:
    title = f"# Informe de experimento: `{exp.root.name}`\n"
    intro = (
        f"Generado el {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')} por benchmarks/experiment_report.py a partir de "
        f"{len(exp.reports)} report(s) del directorio {exp.root.name} (ruta completa en la sección 1). Prosa en español; "
        "identificadores (métodos, métricas, campos) en inglés tal como aparecen en los datos.\n"
    )
    parts = [
        title,
        intro,
        section_what_ran(exp),
        section_prompts(exp),
        section_results(exp),
        section_examples(exp, max_examples),
        section_readings(exp),
        section_files(exp),
    ]
    return "\n".join(parts)


def build_pdf(md_path: Path, header: Optional[Path] = DEFAULT_PDF_HEADER, timeout_s: int = 900) -> tuple[bool, str]:
    """Render ``md_path`` to a sibling PDF with pandoc + tectonic. Never raises."""
    pdf_path = md_path.with_suffix(".pdf")
    if shutil.which("pandoc") is None:
        return False, "pandoc no está instalado; se omite el PDF"
    cmd = [
        "pandoc",
        str(md_path),
        "-o",
        str(pdf_path),
        "--pdf-engine=tectonic",
        "-V",
        "geometry:margin=1.6cm",
        "-V",
        "fontsize=10pt",
        "-V",
        "lang=es",
        # tighter column padding so the 17-column protocol tables fit the text width
        "-V",
        r"header-includes=\setlength{\tabcolsep}{3pt}",
    ]
    if header is not None and Path(header).is_file():
        cmd += ["-H", str(header)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except Exception as exc:  # missing tectonic, timeout, ...
        return False, f"pandoc falló: {type(exc).__name__}: {exc}"
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-5:]
        return False, "pandoc devolvió código " + str(proc.returncode) + ": " + " / ".join(tail)
    return True, str(pdf_path)


def generate(results_dir: Path, out: Optional[Path] = None, max_examples: int = 3, pdf: bool = False, prefer_rescored: bool = True) -> Path:
    exp = load_experiment(Path(results_dir), prefer_rescored=prefer_rescored)
    out_path = Path(out) if out else exp.root / "REPORT.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_report(exp, max_examples=max_examples), encoding="utf-8")
    print(f"written: {out_path} ({out_path.stat().st_size / 1024:.0f} KB; {len(exp.reports)} reports, {len(exp.rows)} items)")
    if pdf:
        ok, msg = build_pdf(out_path)
        print(("pdf: " if ok else "pdf omitido: ") + msg)
    return out_path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results_dir", help="results directory (one report.json or a tree of them)")
    ap.add_argument("--out", default=None, help="output Markdown path (default: <results_dir>/REPORT.md)")
    ap.add_argument("--max-examples", type=int, default=3, help="example traces per method (default 3)")
    ap.add_argument("--pdf", action="store_true", help="also render REPORT.pdf with pandoc + tectonic")
    ap.add_argument(
        "--prefer-rescored",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="use report.rescored.json when it sits next to a report.json (default: on)",
    )
    args = ap.parse_args(argv)
    t0 = time.perf_counter()
    generate(Path(args.results_dir), Path(args.out) if args.out else None, max_examples=args.max_examples, pdf=args.pdf, prefer_rescored=args.prefer_rescored)
    print(f"elapsed: {time.perf_counter() - t0:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

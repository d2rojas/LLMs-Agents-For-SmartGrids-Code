"""This case study's contribution to the shared evaluation site.

An adapter, on purpose. ``evaluation/design_page.py`` already builds this case
study's whole design page and is the thing that knows its content; rewriting it
onto the shared shell in one step would mean touching 669 lines of working code
for a change of chrome. So this module runs it, takes the tab bodies, the
stylesheet and the script out of what it produced, and hands them to
``visuals/build.py`` in the fragment protocol every case study uses.

That makes the two case studies share one site today. The next step is to move
``design_page`` onto ``visuals.shell`` directly, at which point this file
becomes the twenty lines that build the payload and the extraction below goes
away.

Usage (from power-flow-agent/):
    python -m evaluation.page_fragments /tmp/fragments.json

Normally invoked by ``python -m visuals.build`` from the repository root.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT.parent))  # so `visuals` is importable

from evaluation import design_page  # noqa: E402  (after the sys.path line above)
from visuals.shell import (  # noqa: E402
    DASH, GROUP_CORRECTNESS, GROUP_COST, GROUP_UTILITY, Count, E, NA, counted,
)

CASE_ID = "pfagent"
CASE_TITLE = "PFAgent"

# Where the standalone pages this adapter reads are written.
DESIGN = PROJECT_ROOT / "results" / "visuals" / "design.html"
HOME = PROJECT_ROOT / "results" / "visuals" / "index.html"

# Nothing about the section list is hard-coded here. The sections are whichever
# ones the design page emits, in its order and under its own labels, so this
# case study can add, drop or rename one without anybody editing this file.


def _rules(css: str) -> List[Tuple[str, str, bool]]:
    """Split a stylesheet into (selector, declarations, is_at_rule) triples.

    Written by hand because the alternative is a dependency, and the input is
    one generated stylesheet rather than arbitrary CSS.
    """
    out: List[Tuple[str, str, bool]] = []
    sel: List[str] = []
    i, n = 0, len(css)
    while i < n:
        ch = css[i]
        if ch == "{":
            depth, j = 1, i + 1
            while j < n and depth:
                if css[j] == "{":
                    depth += 1
                elif css[j] == "}":
                    depth -= 1
                j += 1
            selector = "".join(sel).strip()
            out.append((selector, css[i + 1 : j - 1], selector.startswith("@")))
            sel, i = [], j
            continue
        sel.append(ch)
        i += 1
    return out


def _own_selectors(css: str) -> set:
    """Every selector a stylesheet defines, one per comma-separated part."""
    owned = set()
    for selector, _body, at_rule in _rules(css):
        if at_rule:
            continue
        for part in selector.split(","):
            owned.add(part.strip())
    return owned


# Chrome the shared shell owns under different names. The standalone page put
# its navigation in a sticky ``header`` with a ``.tabs`` button bar; the shared
# page has a top strip and a sidebar instead, so these rules describe elements
# that no longer exist and can only interfere.
CHROME = ("header", "header h1", ".tabs", ".tabs button", ".tabs button.on", "body.embed header")


def _strip_shared(css: str, owned: set) -> str:
    """Keep only the rules the shared shell does not already define.

    The adapter injects this case study's own stylesheet after the shell's, so
    anything it redefines wins. Its ``body``, ``main`` and ``:root`` rules were
    written for a standalone page and break the shared layout when they land on
    top of it. Dropping every selector the shell owns leaves exactly the
    components that are this case study's own, and leaves one look.
    """
    kept: List[str] = []
    for selector, body, at_rule in _rules(css):
        if at_rule:
            continue  # the shell owns the responsive rules
        parts = [
            p.strip()
            for p in selector.split(",")
            if p.strip() and p.strip() not in owned and p.strip() not in CHROME
        ]
        if parts:
            kept.append(",".join(parts) + "{" + body.strip() + "}")
    return "\n".join(kept)


def _inner(html: str, open_tag: str, close_tag: str) -> str:
    """The text between the first ``open_tag`` and the last ``close_tag``."""
    i = html.find(open_tag)
    j = html.rfind(close_tag)
    if i < 0 or j < 0:
        return ""
    return html[i + len(open_tag) : j]


def _split_tabs(body: str) -> Dict[str, str]:
    """Every ``<div class='tab' id='tab-X'>`` block, by its key.

    The tabs are siblings written one after another, so each one runs from its
    own opening tag to the next one, or to the end. Cutting between markers
    rather than counting ``<div>`` depth keeps this correct even where the
    generated markup leaves a div unbalanced, which it does.
    """
    marks = list(re.finditer(r"<div class='tab[^']*' id='tab-([a-z0-9_-]+)'>", body))
    out: Dict[str, str] = {}
    for n, m in enumerate(marks):
        end = marks[n + 1].start() if n + 1 < len(marks) else len(body)
        chunk = body[m.end() : end].rstrip()
        if chunk.endswith("</div>"):
            chunk = chunk[: -len("</div>")]
        out[m.group(1)] = chunk
    return out


def _home() -> Tuple[str, str]:
    """This case study's home section and the styles it needs, from its own page.

    The standalone site keeps the home in ``index.html`` and the sections in
    ``design.html``. The shared site wants the home as the first section, so it
    is lifted from there rather than written a second time here.
    """
    if not HOME.exists():
        return "", ""
    html = HOME.read_text(encoding="utf-8")
    i = html.find("<section id='home'")
    if i < 0:
        return "", ""
    i = html.find(">", i) + 1
    j = html.find("</section>", i)
    return html[i:j], _inner(html, "<style>", "</style>")


def _built_design_html() -> str:
    """Run the design page and read it, leaving the working tree as it was.

    ``design_page.build()`` writes to a tracked file. Rebuilding the shared site
    would therefore show up as an uncommitted change to a page this adapter only
    wanted to read, in a tree this case study's own session owns. The previous
    contents are put back, so building the site changes nothing under git.
    """
    before = DESIGN.read_bytes() if DESIGN.exists() else None
    try:
        return design_page.build().read_text(encoding="utf-8")
    finally:
        if before is None:
            DESIGN.unlink(missing_ok=True)
        else:
            DESIGN.write_bytes(before)


# ------------------------------------------------- the sections the design page has no place for
#
# ``design.html`` answers what was set up: the prompts, the tool schemas, the gate,
# the run plan. It says nothing about what happened, and so the adapter above used
# to hand the shared site seven of its eleven sections and leave Results, Traces,
# Analysis and Implementation as empty placeholders. The four below fill them, from
# ``results/INDEX.json`` and each run's ``summary.csv`` and traces, which is what
# ``results/visuals/results.html`` reads. Taking them from the same files rather
# than from the aggregates in ``summary.json`` keeps this page on the standalone
# page's source instead of opening a third path to the same numbers, which is how
# the page and the report came to disagree in the first place.

RESULTS = PROJECT_ROOT / "results"
INDEX = RESULTS / "INDEX.json"

METHOD_ROWS: Tuple[Tuple[str, str], ...] = (
    ("rule_based", "Deterministic parser"),
    ("llm_only_structured", "Structured prompting"),
    ("llm_only_cot", "Chain-of-thought prompting"),
    ("plan_act_nogate", "Plan-and-Act, no gate"),
    ("react_nogate", "ReAct, no gate"),
    ("pfagent", "PFAgent, solver-grounded"),
)
SYSTEM_LABELS = {"ieee14": "IEEE 14-bus", "ieee30": "IEEE 30-bus", "ieee57": "IEEE 57-bus",
                 "ieee118": "IEEE 118-bus", "ieee300": "IEEE 300-bus"}

# The six columns are embedded for this system only. Seven hundred and twenty
# traces are forty-three megabytes on disk; embedding every one of them would put
# tens of megabytes into a page meant to be opened by double-clicking it. IEEE 14
# is the system that carries both models, which is the comparison the run plan is
# built around, so it is the one worth reading step by step here. Every other
# system keeps its verdicts and its links, and the standalone page covers them all.
EMBED_SYSTEM = "ieee14"

ANSWERED = "requests this method completed; a request the harness could not run is not counted"
DECLARED = "the requests whose answer declared a formulation; an escalated request declares none"
NUMBERED = "the requests whose answer carried numbers to trace to a tool output"
SOLVED_ON = "the requests this method solved"


def _runs() -> List[Dict[str, Any]]:
    """Every run the index lists, newest first, as ``results.html`` reads it."""
    if not INDEX.exists():
        return []
    return [r for r in json.loads(INDEX.read_text(encoding="utf-8")).get("runs", []) if r.get("kind") == "run"]


def _config(run: Dict[str, Any]) -> Dict[str, Any]:
    """What the run recorded about itself: the harness commit, the prompt, the tool."""
    f = RESULTS / run["path"] / "config.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def _rows(run: Dict[str, Any]) -> List[Dict[str, str]]:
    f = RESULTS / run["path"] / "summary.csv"
    if not f.exists():
        return []
    with f.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _outcome(r: Dict[str, str]) -> str:
    """The same three-way verdict the standalone page derives, by the same rule."""
    if r.get("outcome"):
        return r["outcome"]
    if str(r.get("solved", "")).lower() == "true":
        return "solved"
    return "escalated" if str(r.get("escalated", "")).lower() == "true" else "wrong_unflagged"


def _num(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _mean(xs: List[float]) -> Optional[float]:
    return sum(xs) / len(xs) if xs else None


def _cells(rows: List[Dict[str, str]], model: str) -> Tuple[List[str], str]:
    """One method's row of the comparison table, every figure over its own count."""
    done = [r for r in rows if _outcome(r) != "run_error"]
    errs = len(rows) - len(done)
    n = len(done)
    if not n:
        return [], ""
    answered = Count(n, len(rows), ANSWERED)
    solved = [r for r in done if _outcome(r) == "solved"]
    form = [r for r in done if str(r.get("formulation_exact", "")).strip() not in ("", "None")]
    trace = [r for r in done if str(r.get("faithful_answers", "")).strip() not in ("", "None")]

    def rate(k: int, tot: int, what: str) -> str:
        return counted(f"{100.0 * k / tot:.1f}" if tot else DASH, Count(k, tot, what))

    def err(key: str, subset: List[Dict[str, str]], what: str) -> str:
        xs = [x for x in (_num(r.get(key)) for r in subset) if x is not None]
        m = _mean(xs)
        if m is None:
            return counted(DASH, Count(0, len(subset), what))
        return counted(f"{m:.2e}" if 0 < abs(m) < 1e-2 else f"{m:.3f}", Count(len(xs), len(subset), what))

    tok = _mean([(_num(r.get("prompt_tokens")) or 0.0) + (_num(r.get("completion_tokens")) or 0.0) for r in done])
    tm = _mean([x for x in (_num(r.get("wall_time_s")) for r in done) if x is not None])
    cells = [
        rate(sum(1 for r in form if str(r.get("formulation_exact")).lower() == "true"), len(form), DECLARED),
        err("voltage_mae_pu", solved, SOLVED_ON),
        err("voltage_mae_pu", done, ANSWERED),
        err("kcl_mismatch_mw", solved, SOLVED_ON),
        err("kcl_mismatch_mw", done, ANSWERED),
        rate(len(solved), n, ANSWERED),
        rate(sum(1 for r in done if _outcome(r) == "escalated"), n, ANSWERED),
        rate(sum(1 for r in done if _outcome(r) == "wrong_unflagged"), n, ANSWERED),
        (NA if model == "no-llm" and not trace
         else rate(sum(1 for r in trace if str(r.get("faithful_answers")).lower() == "true"), len(trace), NUMBERED)),
        NA if model == "no-llm" else counted(f"{tok:,.0f}" if tok is not None else DASH, answered),
        counted(f"{tm:.1f}" if tm is not None else DASH, answered),
    ]
    n_cell = str(n) + (f"<br><span class='cnt'>{errs} run error{'s' if errs > 1 else ''}</span>" if errs else "")
    return cells, n_cell


PF_GROUPS = (
    (GROUP_UTILITY, ["Formulation exact %", "V_MAE (solved)", "V_MAE (all)",
                     "B_mean MW (solved)", "B_mean MW (all)"]),
    (GROUP_CORRECTNESS, ["Solved %", "Escalated %", "Wrong-unflagged %", "Traceable %"]),
    (GROUP_COST, ["Tokens", "Time s"]),
)


def _tag(run: Dict[str, Any]) -> str:
    m = re.search(r"__([A-Za-z0-9-]+)$", run.get("dir", ""))
    return m.group(1) if m else "main"


def _newest(runs: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """The newest run per (model, method), so a re-run replaces rather than duplicates.

    Picking whichever the index happened to list last is not a choice, and two
    runs of one method in one table are two rows that look like two methods. The
    GridDebug session hit the same shape in its own case study and found its
    table mixing four run sets that shared a date.
    """
    best: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for r in sorted(runs, key=lambda r: r["date"]):
        best[(r["model"], r["method"])] = r
    return best


def tab_results() -> str:
    from visuals.shell import card, comparison_table, note

    runs = [r for r in _runs() if _tag(r) == "main"]
    if not runs:
        return card("No runs yet", "<p class='muted'>results/INDEX.json lists no run.</p>")
    body: List[str] = []
    by_system: Dict[str, List[Dict[str, Any]]] = {}
    for r in runs:
        by_system.setdefault(r["case"], []).append(r)

    for system in sorted(by_system, key=lambda c: int(c.replace("ieee", ""))):
        chosen = _newest(by_system[system])
        rows_out: List[Tuple[str, List[str], List[str]]] = []
        # the ladder order outside, the model inside: comparison_table groups the
        # rows by model and keeps the order it is given within each block, so the
        # six methods have to be iterated in ladder order or the block comes out
        # in whatever order the index happened to list the runs
        for key, label in METHOD_ROWS:
            for (model, method), run in sorted(chosen.items()):
                if method != key:
                    continue
                cells, n_cell = _cells(_rows(run), model)
                if not cells:
                    continue
                # The date says when, the commit says with what. They are not the
                # same control and the second is the one that actually varies:
                # every table here spans four or five harness commits.
                #
                # The -dirty suffix is never trimmed. Truncating the id to eight
                # characters hid it on every row of every table here, which made
                # the page claim a provenance none of these runs has: a dirty id
                # names no commit, and the code that produced the row is in
                # nobody's history.
                cfg = _config(run)
                full = str(cfg.get("git_commit") or "")
                dirty = full.endswith("-dirty")
                sha = (full[:8] + " + uncommitted") if dirty else full[:8]
                name = (f"<b>{E(label)}</b><div class='muted'><code>{E(key)}</code> · {E(run['date'])}"
                        + (f" · <code{' class=' + chr(39) + 'bad' + chr(39) if dirty else ''}>{E(sha)}</code>"
                           if full else " · <code>no commit recorded</code>") + "</div>")
                rows_out.append((model, [name, n_cell], cells, run["path"]))
        if not rows_out:
            continue
        dates = sorted({r["date"] for r in chosen.values()})
        commits = [str(_config(r).get("git_commit") or "") for r in chosen.values()]
        shas = sorted({c[:8] for c in commits} - {""})
        n_dirty = sum(1 for c in commits if c.endswith("-dirty"))
        # Six methods on one system were not run in one sitting, and a table that
        # does not say so reads as one experiment. Each row carries its own date
        # under the method name; this says it out loud as well.
        when = (f"run of {E(dates[0])}" if len(dates) == 1
                else f"runs of {E(', '.join(dates))}, one date per row")
        body.append(card(
            f"{SYSTEM_LABELS.get(system, system)} · {when}",
            comparison_table(PF_GROUPS, rows_out, lead=("Model", "Method", "n")),
            note("The three column groups are the same three in every case study of this site, and every figure "
                 "carries above it the count it was computed over. The three outcomes are over the requests the "
                 "method completed, so a request the harness could not run sits outside the rates rather than "
                 "inside their denominator, and is reported separately under n. Formulation is scored over the "
                 "requests whose answer declared one, which an escalated request does not. V_MAE and B_mean are "
                 "given over the solved requests and over every request that reported a state. Traceable is not "
                 "applicable to a method that calls no tool, which is not the same as passing."
                 + ("" if len(shas) < 2 else
                    f" <b>These rows were produced by {len(shas)} different builds of the harness</b>, named under "
                    "each method beside its date, because the six methods were not run in one sitting on this "
                    "system. What is shared is what the comparison rests on: every row answered the same request "
                    "set, was scored by the same evaluator, called the same tool variant and ran at temperature 0. "
                    "What is not shared is the code that drove them, so a difference between two rows is a "
                    "difference between two builds as well as between two methods."),
                 "info"),
            *([note(f"<b>{n_dirty} of these {len(commits)} rows were run from a working tree with uncommitted "
                    "changes</b>, marked <code class='bad'>+ uncommitted</code> beside the commit. That id names "
                    "no commit: the code that produced those numbers is in nobody's history and cannot be "
                    "recovered, so the rows can be read but not reproduced. This is a property of how the runs "
                    "were launched, not of the results, and it is shown here rather than trimmed away because "
                    "the supplement's Reproducibility section promises the opposite.", "bad")]
              if n_dirty else [])))

    body.append(_request_section())
    return "".join(body)

def _fmt_args(a: Any) -> str:
    if not a:
        return "()"
    if isinstance(a, str):
        try:
            a = json.loads(a)
        except ValueError:
            return f"({a})"
    return "(" + ", ".join(f"{k}={json.dumps(v)}" for k, v in (a or {}).items()) + ")"


def _brief(text: Any, n: int = 150) -> str:
    t = " ".join(str("" if text is None else text).split())
    return t[:n] + "…" if len(t) > n else t


def _step_lines(payload: Dict[str, Any], row: Dict[str, str]) -> List[Tuple[str, str, str]]:
    """One line per step of a run, from its trace.

    A port of ``exampleRows`` in ``results/visuals/results.html``, kept in step
    with it on purpose: the two pages read the same trace files and should say
    the same thing about them. The kinds are the ones every case study uses.
    """
    tr = payload.get("trace") or {}
    out: List[Tuple[str, str, str]] = []
    plan = tr.get("plan") or []
    if plan:
        out.append(("plan", "plan: " + " → ".join(c.get("tool", "") + _fmt_args(c.get("args")) for c in plan),
                    json.dumps(plan, indent=1)[:6000]))
    rounds = tr.get("rounds") or []
    for rd in rounds:
        llm = rd.get("llm") if isinstance(rd.get("llm"), dict) else None
        if llm:
            calls = [f"{tc.get('name')}{_fmt_args(tc.get('arguments'))}" for tc in (llm.get("tool_calls") or [])]
            u = llm.get("usage") or {}
            if rd.get("final"):
                out.append(("final", "final answer: " + _brief(llm.get("content")), str(llm.get("content") or "")[:6000]))
            elif calls:
                out.append(("call", "calls → " + "; ".join(calls),
                            (llm.get("content") or "") + "\n\ntool calls:\n" + "\n".join(calls)
                            + f"\n\n[{u.get('prompt_tokens', '?')} in / {u.get('completion_tokens', '?')} out tokens]"))
            else:
                out.append(("model", "text: " + _brief(llm.get("content")), str(llm.get("content") or "")[:6000]))
        for tool in rd.get("tools") or []:
            raw = tool.get("output")
            body = raw if isinstance(raw, str) else json.dumps(raw)
            # a rendered plot is a base64 blob in the trace and nothing on a page
            body = re.sub(r'"figure_json"\s*:\s*"(?:[^"\\]|\\.)*"', '"figure_json": "<plot omitted>"', str(body or ""))
            g = tool.get("gate")
            mark = "" if g is None else (" [gate: pass]" if (g.get("passed") if isinstance(g, dict) else g) else " [gate: FAIL]")
            call = f"{tool.get('name')}{_fmt_args(tool.get('arguments'))}"
            out.append(("tool", f"{call} → {_brief(body, 110)}{mark}", (call + "\n\n" + body)[:6000]))
    if not rounds:
        out.append(("final", "answer: " + _brief(payload.get("answer") or row.get("raw_response")),
                    str(payload.get("answer") or row.get("raw_response") or "")[:6000]))
    elif not any(r.get("final") for r in rounds) and payload.get("answer"):
        out.append(("final", _brief(payload["answer"]), str(payload["answer"])[:6000]))
    for i, v in enumerate(tr.get("verification") or []):
        cs = v.get("conditions") or {}
        out.append(("gate",
                    f"gate attempt {i + 1}: {'PASS' if v.get('passed') else 'FAIL'} · "
                    + " ".join(f"{c.get('label', k)}{'✓' if c.get('passed') else ('·' if c.get('applicable') is False else '✗')}"
                               for k, c in cs.items()),
                    "\n".join(f"{c.get('label', k)} {k}: {'pass' if c.get('passed') else 'FAIL'}"
                              + (f" · {c['detail']}" if c.get("detail") else "") for k, c in cs.items())))
    for m in tr.get("verification_retry_messages") or []:
        out.append(("retry", "retry message: " + _brief(m), str(m)[:6000]))
    if tr.get("status") and tr["status"] != "ok":
        out.append(("status", "engine status: " + str(tr["status"]), str(tr["status"])))
    return out


def _trace(run: Dict[str, Any], row: Dict[str, str]) -> Optional[Dict[str, Any]]:
    stem = f"{int(row['nn']):02d}_{re.sub(r'[^A-Za-z0-9_.-]+', '_', row['request_id'])}"
    f = RESULTS / run["path"] / "traces" / f"{stem}.json"
    if " " in f.stem or not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return None


def _summary_cell(row: Dict[str, str], run: Dict[str, Any]) -> str:
    from visuals.shell import verdict

    form = ("exact" if str(row.get("formulation_exact", "")).lower() == "true"
            else E(str(row.get("formulation_error_type") or "not declared")))
    bits = [f"<span class='why'>formulation {form}</span>"]
    if row.get("verification_outcome"):
        bits.append(f"<span class='why'>gate {E(row['verification_outcome'])}</span>")
    return verdict(_outcome(row)) + "".join(bits)


def _request_section() -> str:
    from visuals.shell import card, note, request_rows

    runs = [r for r in _runs() if _tag(r) == "main" and r["case"] == EMBED_SYSTEM]
    if not runs:
        return ""
    out: List[str] = []
    by_model: Dict[str, List[Dict[str, Any]]] = {}
    for r in runs:
        by_model.setdefault(r["model"], []).append(r)
    # the parser has no model of its own and belongs in every block
    parser = [r for r in runs if r["model"] == "no-llm"]

    for model in sorted(m for m in by_model if m != "no-llm"):
        # the newest run of each method, by the same rule the table above uses, so
        # a row of that table and the runs unfolded under it are the same runs
        per_method = {method: run for (_m, method), run in _newest(by_model[model] + parser).items()}
        rows_by_method = {k: {x["request_id"]: x for x in _rows(v)} for k, v in per_method.items()}
        ids: List[str] = []
        for k, _l in METHOD_ROWS:
            for rid in rows_by_method.get(k, {}):
                if rid not in ids:
                    ids.append(rid)
        requests: List[Dict[str, Any]] = []
        for rid in ids:
            cells: Dict[str, str] = {}
            columns: List[Dict[str, Any]] = []
            text = difficulty = ""
            for key, label in METHOD_ROWS:
                run = per_method.get(key)
                row = rows_by_method.get(key, {}).get(rid)
                if run is None or row is None:
                    columns.append({"label": label, "empty": "no run in this set"})
                    continue
                text = text or row.get("request_text", "")
                difficulty = difficulty or row.get("difficulty", "")
                cells[key] = _summary_cell(row, run)
                payload = _trace(run, row)
                stem = f"{int(row['nn']):02d}_{re.sub(r'[^A-Za-z0-9_.-]+', '_', rid)}"
                # named, not linked: this page is written to site/ and the results
                # tree is not under it, so a relative link from here would be dead
                where = f"results/{run['path']}/traces/{stem}"
                columns.append({
                    "label": label, "model": run["model"], "verdict": _outcome(row),
                    "lines": _step_lines(payload, row) if payload else [],
                    "empty": "trace not readable" if not payload else "",
                    "footer": (f"{row.get('n_llm_calls') or '?'} model calls, {row.get('n_tool_calls') or '?'} solver "
                               f"calls · {row.get('prompt_tokens') or '?'} in / {row.get('completion_tokens') or '?'} out"
                               f"<br><span class='muted'>raw: <code>{E(where)}.transcript.txt</code></span>"),
                })
            requests.append({"id": rid, "tag": difficulty, "text": text, "cells": cells, "columns": columns})
        out.append(card(
            f"Every request of {SYSTEM_LABELS.get(EMBED_SYSTEM, EMBED_SYSTEM)} under {E(model)}",
            "<p>Click a request to unfold the six methods side by side. Each column is that run's own steps, read "
            "from the trace the run wrote: <span class='k plan'>plan</span> what it committed to, "
            "<span class='k call'>call</span> a tool, <span class='k tool'>tool</span> what the solver returned, "
            "<span class='k gate'>gate</span> the eleven conditions with their detail, "
            "<span class='k retry'>retry</span> what was handed back, <span class='k final'>final</span> what was "
            "surfaced. Click any line to expand it to the tool arguments, the whole solver output or the answer.</p>",
            request_rows(requests, list(METHOD_ROWS))))

    others = sorted({r["case"] for r in _runs() if _tag(r) == "main"} - {EMBED_SYSTEM},
                    key=lambda c: int(c.replace("ieee", "")))
    if others:
        out.append(card(
            "The other systems",
            f"<p>The tables above cover {E(', '.join(SYSTEM_LABELS.get(c, c) for c in others))} as well. Their step "
            "logs are not embedded here: the five systems hold seven hundred and twenty traces and forty-three "
            "megabytes, and this page is meant to be opened by double-clicking it. "
            f"{SYSTEM_LABELS.get(EMBED_SYSTEM, EMBED_SYSTEM)} is embedded because it is the only system run under "
            "both models, which is the comparison the run plan is built around.</p>",
            note("Every request of every system, with the same six columns, is in this case study's own page at "
                 "<code>power-flow-agent/results/visuals/results.html</code>, and each run end to end is in "
                 "<code>viewer.html</code> beside it. Both read the same files as this page.", "info")))
    return "".join(out)

def tab_traces() -> str:
    """The raw archive. What happened in a given run is on the results page now."""
    from visuals.shell import card, note

    runs = [r for r in _runs() if _tag(r) == "main"]
    if not runs:
        return card("Traces", "<p class='muted'>No run yet.</p>")
    body = [card(
        "Every run end to end",
        "<p>The narrative of each request, as the harness wrote it from the trace: what the method did, the "
        "formulation verdict, the state it reported, the gate's decision and the outcome. The transcript beside it "
        "in the results folder is the raw exchange, and the JSON next to both is what the results page reads.</p>",
        note("The six methods side by side, for any one request, are on the <b>Results</b> section rather than here: "
             "a verdict in that table is a count of those runs, so the runs belong under the number. This section is "
             "the archive the numbers come from.", "info"))]
    for run in sorted(runs, key=lambda r: (r["case"], r["model"], r["method"]))[:12]:
        d = RESULTS / run["path"] / "traces"
        if not d.is_dir():
            continue
        items = []
        for p in sorted(d.glob("*.narrative.txt")):
            if " " in p.stem:
                continue        # an iCloud copy, older than the rescores
            items.append(f"<details><summary><code>{E(p.name)}</code></summary>"
                         f"<pre>{E(p.read_text(encoding='utf-8'))}</pre></details>")
        if items:
            body.append(card(f"{E(run['case'])} / {E(run['model'])} / {E(run['method'])} · {E(run['date'])}", *items))
    return "".join(body)


def tab_analysis() -> str:
    """The report each run ends with, written from its rows by the harness."""
    from visuals.shell import card, markdown

    runs = [r for r in _runs() if _tag(r) == "main"]
    reports = [(r, RESULTS / r["path"] / "REPORT.md") for r in runs]
    reports = [(r, f) for r, f in reports if f.exists()]
    if not reports:
        return card("Analysis", "<p class='muted'>No results folder carries a REPORT.md yet.</p>")
    body = [card("What the reports are",
                 "<p>Every run ends with one, written by <code>benchmarks/experiment_report.py</code> from the rows "
                 "of that run. No model is called to write it. The numbers in it are computed by the same Python "
                 "that writes <code>summary.json</code>, and the cross-check in <code>tests/crosscheck_page.mjs</code> "
                 "asserts that this page and that aggregate agree on every one of them.</p>")]
    for run, f in sorted(reports, key=lambda x: (x[0]["case"], x[0]["model"], x[0]["method"]))[:12]:
        body.append("<div class='card'><h2><code>"
                    + E(f"{run['case']}/{run['date']}/{run['model']}/{run['method']}")
                    + "</code></h2>" + markdown(f.read_text(encoding="utf-8")) + "</div>")
    return "".join(body)


def tab_status() -> str:
    """Which methods have run, on what, and with which model."""
    from visuals.shell import card, chip, table

    runs = _runs()
    if not runs:
        return card("Where the implementation stands", "<p class='muted'>No run yet.</p>")
    seen: Dict[str, List[str]] = {}
    for r in runs:
        seen.setdefault(r["method"], [])
        tagged = f"{r['case']}·{r['model']}"
        if tagged not in seen[r["method"]]:
            seen[r["method"]].append(tagged)
    rows = []
    for key, label in METHOD_ROWS:
        where = seen.get(key, [])
        rows.append([f"<b>{E(label)}</b>", f"<code>{E(key)}</code>",
                     chip(f"run on {len(where)} system-model pairs", "ok") if where else chip("not run yet", "warn"),
                     E(", ".join(sorted(where))) or "<span class='muted'>—</span>"])
    extra = sorted({r["method"] for r in runs} - {k for k, _l in METHOD_ROWS})
    return card(
        "Where the implementation stands",
        f"<p>All six methods run today. {len(runs)} runs are indexed in "
        "<code>results/INDEX.json</code>, each with its rows, its traces and its report.</p>",
        table(["method", "name", "state", "run on"], rows),
        (f"<p class='muted'>Also in the index, outside the six-row ladder: "
         f"{E(', '.join(extra))}. These are variants kept for the appendix, not rows of the main table.</p>"
         if extra else ""))


def payload() -> Dict[str, Any]:
    from visuals import shell

    html = _built_design_html()
    owned = _own_selectors(shell.CSS)

    css = _strip_shared(_inner(html, "<style>", "</style>"), owned)
    # The page's driver is its last script block. Taking from the first
    # ``<script>`` instead would swallow every script the content embeds, and
    # with them the megabytes of page between the first and the last.
    tail = html[html.rfind("<script>") :]
    script = _inner(tail, "<script>", "</script>")
    tabs = _split_tabs(_inner(html, "<main>", "</main>"))

    # Section labels come from the page's own tab bar, so a rename there needs
    # no change here. A section with no button falls back to its key.
    labels = dict(re.findall(r"<button data-tab='([a-z0-9_-]+)'[^>]*>([^<]*)</button>", html))
    entries: List[Tuple[str, str]] = []

    home, home_css = _home()
    if home:
        tabs["home"] = home
        css = _strip_shared(home_css, owned) + css
        entries.append(("home", "Home"))
    entries += [(k, labels.get(k, k.replace("_", " ").capitalize())) for k in tabs if k != "home"]

    # design.html emits methods, scenarios, prompts, tools, gate and plan, and has
    # no place for what happened: this case study's Results, Traces, Analysis and
    # Implementation were empty placeholders on the shared site while its own
    # standalone pages carried them. They are built here instead, from the same
    # result files those pages read.
    for key, label, build in (("results", "Results", tab_results), ("traces", "Traces", tab_traces),
                              ("analysis", "Analysis", tab_analysis), ("status", "Implementation", tab_status)):
        tabs[key] = build()
        entries.append((key, label))

    # The design page drives its own tab bar; the shared shell drives the
    # sidebar instead, so that part of its script has to go or the two fight
    # over which section is visible.
    script = re.sub(r"const tabs=document\.querySelectorAll\('\.tabs button'\);.*?fromHash\(\);", "", script, flags=re.S)

    return {
        "id": CASE_ID,
        "title": CASE_TITLE,
        "brand": "PFAgent · power flow on IEEE test systems",
        "note": "IEEE 14 to 300-bus",
        "blurb": "Answer an operator's power-flow request on an IEEE test system: run the flow, change a load, "
                 "take a line out, scan every single outage.",
        "summary": [
            ("task", "power flow and contingencies"),
            ("solver", "PandaPower Newton-Raphson"),
            ("data", "IEEE 14, 30, 57, 118, 300"),
        ],
        "groups": [["", [list(e) for e in entries]]],
        "tabs": tabs,
        "css": css,
        "script": script,
    }


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "results" / "visuals" / "fragments.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload()), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

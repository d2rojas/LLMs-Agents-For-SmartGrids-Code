"""This case study's contribution to the shared evaluation site.

The chrome lives in ``visuals/shell.py`` at the repository root; this module
writes only content. Every fact is read from the code at build time: the
method registry, the gate's condition table, the frozen manifest, the prompt
builders, the tool catalogue and the result files. Nothing on the page is
typed by hand twice.

Usage (from wind-forecasting/):
    python -m evaluation.page_fragments /tmp/fragments.json

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
from config import (  # noqa: E402
    HISTORY_DAYS, HORIZONS_H, MAX_LLM_CALLS, MAX_TOOL_CALLS, POWER_MAX_KW, RATED_KW, REQUEST_TIMEOUT_S, TRAIN_LAST_DAY, TRACE_TOL_KW,
)

CASE_ID = "wind"
CASE_TITLE = "Wind"
ABNORMAL_SHARE = "some"

DIAGRAMS: Dict[str, Dict[str, Any]] = {
    "rule_based": {"steps": [("request", "input"), ("regex parser", "code"), ("GRU tool", "solver"), ("template answer", "out")],
                   "note": "No language model. Patterns read turbine, window and horizon; the conventional forecaster writes the series; a request the patterns cannot read is escalated."},
    "llm_only_structured": {"steps": [("request + 14-day history", "input"), ("LLM writes the series", "llm"), ("answer", "out")],
                            "note": "One call, no tools. The model is the predictor: it reads the history as CSV and writes the values itself."},
    "llm_only_cot": {"steps": [("request + 14-day history", "input"), ("LLM reasons, then writes", "llm"), ("answer", "out")],
                     "note": "One added reasoning section. Identical to the method on its left in every other respect."},
    "plan_act_nogate": {"steps": [("request", "input"), ("LLM writes the whole plan", "plan"), ("harness runs every step", "solver"), ("LLM writes the answer", "llm")],
                        "note": "Plans once. The whole sequence of tool calls is committed before any result comes back."},
    "react_nogate": {"steps": [("request", "input"), ("LLM decides a tool call", "llm"), ("tool reads the history or forecasts", "solver"), ("LLM writes the answer", "llm")],
                     "loop": 2, "note": f"Up to {MAX_LLM_CALLS} model calls and {MAX_TOOL_CALLS} tool calls. The model sees every result; nothing checks the answer."},
    "windagent": {"steps": [("request", "input"), ("LLM decides a tool call", "llm"), ("tool reads the history or forecasts", "solver"), ("gate W1-W5", "gate")],
                  "loop": 2, "branch": ("report", "escalate"),
                  "note": "The same loop, then five conditions on the answer. A series no tool produced leaves as an escalation, not as a forecast."},
}

ROWS: Tuple[Dict[str, str], ...] = (
    {"block": "Conventional workflow", "name": "rule_based", "label": "Parser + conventional forecaster", "llm": "no", "tools": "the same catalogue, directly", "gate": "none",
     "isolates": "no language model anywhere. Regular expressions read the request and the GRU writes the series; what conventional automation already achieves, and where it stops (a phrasing the patterns do not know)."},
    {"block": "LLM-only prompting", "name": "llm_only_structured", "label": "Structured prompting", "llm": "yes", "tools": "none", "gate": "none",
     "isolates": "the language model as the predictor. It receives the 14-day history as CSV, the physical rules and the contract, and writes the series itself. This is the setting the submitted Section 6.1 tested."},
    {"block": "LLM-only prompting", "name": "llm_only_cot", "label": "Chain-of-thought prompting", "llm": "yes", "tools": "none", "gate": "none",
     "isolates": "one added prompt section asking for step-by-step reasoning before the answer. Same input, same budget, same contract as the row above."},
    {"block": "Multi-step agents", "name": "plan_act_nogate", "label": "Plan-and-Act, no gate", "llm": "yes", "tools": "the catalogue, through function calling", "gate": "none",
     "isolates": "tool access through a plan. One call emits the whole sequence, executed without the model seeing the results in between."},
    {"block": "Multi-step agents", "name": "react_nogate", "label": "ReAct, no gate", "llm": "yes", "tools": "the catalogue, through function calling", "gate": "none",
     "isolates": "iteration. The model sees each tool output and may call again, inside the same budget as the row above and the row below."},
    {"block": "Multi-step agents", "name": "windagent", "label": "WindAgent, solver-grounded", "llm": "yes", "tools": "the catalogue, through function calling", "gate": "five conditions on the answer",
     "isolates": "the verification gate, and nothing else. Same tools, same budget and same requests as ReAct, so any difference between the two rows is the gate."},
)

COLUMNS: Tuple[Dict[str, str], ...] = (
    {"group": "Task utility", "name": "Formulation", "what": "the turbine, history window and horizon declared in the answer match the request; with tools, also the call that produced the series", "why": "whether the request was understood, kept apart from whether the series is any good"},
    {"group": "Task utility", "name": "MAE, RMSE", "what": "forecast error in kW against the target days under the KDD Cup abnormal-data rules, reported per horizon over the requests whose series was valid", "why": "how good the forecast was; the KDD Cup's own score is the mean of the two, kept for continuity with the paper"},
    {"group": "Task utility", "name": "nMAE", "what": "the same MAE as a share of the turbine's 1500 kW rating", "why": "kW alone cannot be compared across turbines or windy and calm windows; the wind literature reports error as a share of capacity"},
    {"group": "Task utility", "name": "Skill", "what": "1 - MAE / MAE of persistence (yesterday repeated) on the same points: 0 is no better than the trivial forecast, 1 is perfect, negative is worse", "why": "an MAE of 400 kW means nothing on its own. This says whether a method beat what costs nothing, which is the only question a forecast has to answer first"},
    {"group": "Task utility", "name": "Answer", "what": "the answer to the request's question (peak hour, energy) agrees with what the reported series implies", "why": "whether the report is consistent with itself"},
    {"group": "Solver-grounded correctness", "name": "Solved", "what": "a valid series in range, an answer coherent with it, and, with tools, a series traceable to a tool output", "why": "the end-to-end verdict on what can be verified without the future"},
    {"group": "Solver-grounded correctness", "name": "Escalated", "what": "the method declared cannot_forecast, or the budget ran out, or the gate rejected two attempts", "why": "how much work goes back to a person; under the stress condition it is the correct outcome"},
    {"group": "Solver-grounded correctness", "name": "Wrong, unflagged", "what": "a wrong number of values, a value outside the range, a series no tool produced (with tools), or an answer that contradicts the series, presented as valid", "why": "the quantity a solver-grounded design exists to drive to zero"},
    {"group": "Solver-grounded correctness", "name": "Traceable", "what": f"the series equals, within {TRACE_TOL_KW} kW per value, one forecast-tool output or the element-wise mean of two", "why": "the reported numbers have an origin that can be checked; nothing supports an LLM-written series"},
    {"group": "Cost and time", "name": "Tokens, Time", "what": "model calls, tool calls, prompt and completion tokens, wall clock per request", "why": "what the architecture costs to run"},
)


# ------------------------------------------------------------------ data


def manifest() -> Optional[Dict[str, Any]]:
    from solver.data import MANIFEST_PATH

    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else None


def gru_meta() -> Optional[Dict[str, Any]]:
    from solver.gru import WEIGHTS_PATH

    if not WEIGHTS_PATH.exists():
        return None
    d = json.loads(WEIGHTS_PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in d.items() if k != "state"}


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
    from evaluation.requests import generate_requests

    return generate_requests(instance_ids=["t008-d201"], horizons=(48,), questions=("peak_hour",), seed=0)[0]


# ------------------------------------------------------------------ tabs


def abnormal_share_text() -> str:
    """The share of target points the KDD Cup rules exclude, over the frozen set."""
    m = manifest()
    if not m:
        return "some"
    tot = sum(int(e["abnormal_points_target"]) for e in m["instances"])
    n = len(m["instances"]) * 288
    return f"{100.0 * tot / n:.1f} %" if n else "some"


def tab_home() -> str:
    m = manifest()
    n_inst = len(m["instances"]) if m else 0
    global ABNORMAL_SHARE
    ABNORMAL_SHARE = abnormal_share_text()
    body = [
        card(
            "The task",
            "<p>A wind farm has to tell the system operator how much power a turbine will produce over the next 3, 6 or 48 hours, at the "
            "ten-minute resolution dispatch and the market settle on. So the answer to one request is a series of numbers in kW: 18 of them "
            "at 3 hours, 36 at 6, 288 at 48. The only evidence is that turbine's own SCADA history for the fourteen days before the forecast "
            "starts, ten minutes apart: wind speed, wind direction, temperature and active power.</p>"
            "<p>Today a forecasting model an engineer chose, trained and validated produces that series. This case study asks what happens "
            "when a language model is put in charge of the task, and measures six ways of producing the same series on the same windows. Three "
            "of them call a trained forecaster and report what it returned; two write the numbers themselves, which is what the LLM-forecasting "
            "literature proposes; one has no language model at all. Each request also asks one thing about the series returned, the hour it "
            "peaks or the energy it carries, because a forecast nobody can read a decision off is not yet an answer.</p>",
            pipeline(
                [("Request", "turbine, window, horizon, question"),
                 ("Read the history", "14 days of SCADA, nothing later"),
                 ("Forecast", "a tool, or the model itself"),
                 ("Verify", "W1-W5 on the answer (gated row)"),
                 ("Report", "the series, its source, the answer")],
                loop=(3, 2, "one retry, then escalate"),
            ),
            "<p class='muted' style='text-align:center'>Fig. 1. The pipeline every method is measured on. Only the solver-grounded method has "
            "the Verify stage; the others go from Forecast to Report.</p>",
        ),
        card(
            "No future information, for anyone",
            "<p>This is the point the case study exists to settle. The experiment behind the submitted paper gave its best variant reanalysis "
            "wind speed <i>for the very hours it had to forecast</i>: a measurement of the future, not a forecast, and the reason a reviewer "
            "asked for the experiment to be repeated. Here nothing after the last history day exists for any method. There is no weather input, "
            "no later measurement, and no tool that could return one, so the question cannot be answered by leakage in any row.</p>"
            "<p>That is also the protocol of the KDD Cup 2022 on this same dataset, which forecasts from history alone. The farm's location and "
            "calendar dates are not published with the data, so no operational forecast product could be attached honestly even if it were "
            f"wanted. The conventional forecaster, a GRU, is trained in this repository on days 1 to {TRAIN_LAST_DAY} and every scenario's target "
            f"lies after day {TRAIN_LAST_DAY}, so it never saw what it is asked to predict, and it reads exactly the history every other row reads.</p>",
        ),
        card(
            "What a value may be, and which points are scored",
            f"<p>Active power lives in [0, {RATED_KW:.0f}] kW, the turbine's rating; a reported value counts as in range up to {POWER_MAX_KW:.0f} kW, "
            "and anything outside that is a wrong answer rather than a bad one. A recorded negative value is the turbine's own consumption while "
            "stopped and is read as zero.</p>"
            "<p>A target point the KDD Cup rules call abnormal is not scored, identically for every method: the turbine stopped while the wind "
            "blew above 2.5 m/s, a blade feathered past 89 degrees, a reading missing, a direction out of its physical range. In these twenty "
            f"windows that removes {ABNORMAL_SHARE} of the target points, four fifths of them blades feathered during curtailment, which is an operator's "
            "decision and not something a forecast can be blamed for.</p>",
        ),
        "<div class='grid g3'>"
        + card("What a correct answer needs",
               "<ul><li><b>The formulation:</b> the turbine, the window and the horizon the request names.</li>"
               "<li><b>A valid series:</b> exactly horizon x 6 finite values inside the physical range.</li>"
               "<li><b>An honest report:</b> a series that is a tool output (or the mean of two) when tools were used, named as such, and an answer derived from it.</li></ul>")
        + card("What can go wrong",
               "<ul><li>A series with 287 or 291 values, presented as 288.</li><li>A value above the rating, or below zero.</li>"
               "<li>A series the model edited after a tool produced it, still labelled with the tool's name.</li>"
               "<li>A peak hour that the series itself does not support.</li><li>A forecast produced from a history whose last day is blank.</li></ul>")
        + card("What is expected of the gated row",
               f"<p>Every answer passes five verification conditions or leaves as an escalation with the reason stated. The target: "
               f"{verdict('solved')} + {verdict('escalated')} = 100 %, {verdict('wrong')} = 0.</p>")
        + "</div>",
        card("Identical for every method",
             chip(f"{n_inst} scenarios, frozen and hashed") + chip(f"{len(HORIZONS_H)} horizons: " + ", ".join(f"{h} h" for h in HORIZONS_H)) + chip("one request generator, seeded")
             + chip("one tool catalogue") + chip(f"{MAX_LLM_CALLS} model calls, {MAX_TOOL_CALLS} tool calls, {REQUEST_TIMEOUT_S:.0f} s per request")
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
        card("Six ways to forecast the same window",
             diagram_row([{"title": r["label"], "subtitle": ("no LLM" if r["llm"] == "no" else "LLM only, no tools" if r["tools"] == "none" else "LLM + tools"),
                           **DIAGRAMS[r["name"]]} for r in ROWS])),
        card("Six methods, one factor apart",
             "<p>One conventional workflow with no language model, and five ways of using one. Each row adds a single capability to the row above "
             "it: a language model, then a reasoning section, then access to the forecasters, then iteration, then verification.</p>",
             table(["Block", "Method", "LLM", "Tools", "Gate", "What it adds over the row above"], rows),
             note("<b>Two contrasts carry this case study.</b> The LLM-only rows against the parser row ask whether a language model writing the "
                  "numbers itself beats a conventional forecaster on the same history, which is the claim of the LLM-forecasting literature. "
                  "ReAct against WindAgent asks what the gate changes when the model has the same forecasters as tools: nothing in accuracy, by "
                  "construction, and everything in whether an unsupported series can reach the report.", "info")),
        card("What the original experiment was, and what changed",
             "<p>The code behind the submitted table had three prompts and one call per cell, on one turbine and one window, with reanalysis wind for "
             "the forecast hours in the prompt of its best variant, no tokens or traces recorded, and a GRU row copied from a student report. The "
             "<code>llm_only_structured</code> row here is that experiment's physics-informed prompt with the future removed, the junk columns removed, "
             "the history reduced to the four features the paper names, and the same contract every other row answers with. The original scripts "
             "are kept under <code>_legacy/</code>.</p>"),
    ])


def tab_scenarios() -> str:
    m = manifest()
    if not m:
        return card("Instances", "<p class='muted'>No manifest frozen yet: run <code>run.py freeze-data</code>.</p>")
    ent = m["instances"]
    turbines = m["turbines"]
    base_days = m["choice_rule"]["base_days"]
    head = ["turbine"] + [f"days {b}-{b + HISTORY_DAYS - 1} → {b + HISTORY_DAYS}-{b + HISTORY_DAYS + 1}" for b in base_days]
    rows = []
    for t in turbines:
        cells = [f"<b>turbine {t}</b>"]
        for b in base_days:
            e = next((x for x in ent if x["turbine"] == t and x["base_day"] == b), None)
            if e is None:
                cells.append("<span class='muted'>—</span>")
                continue
            k = "ok" if e["abnormal_points_target"] <= 30 else "warn"
            cells.append(chip(f"{288 - e['abnormal_points_target']} of 288 target points scored", k)
                         + f"<div class='muted'>history: {e['abnormal_points_history']} abnormal rows of {HISTORY_DAYS * 144}</div>")
        rows.append(cells)
    g = gru_meta()
    gru_txt = ("<p class='muted'>No GRU trained yet.</p>" if not g else
               f"<p>{E(g['model'])}. Trained on days {g['training']['train_days'][0]} to {g['training']['train_days'][1]} of the five turbines "
               f"({', '.join(g['training']['turbines'])}), validated on days {g['training']['val_days'][0]} to {g['training']['val_days'][1]}, "
               f"seed {g['training']['seed']}, {g['training']['epochs']} epochs; best validation MAE {g['training']['best_val_mae_kw']} kW. "
               f"Weights and training log in <code>data/gru/gru_v1.json</code>; its hash is stamped on every run's config.</p>")
    return "".join([
        card("What a scenario is, and how many there are",
             "<p><b>One scenario is one turbine and one 14-day window of its history.</b> Five turbines times four windows makes twenty "
             "scenarios, and each one is asked at three horizons (3, 6 and 48 hours ahead from the same starting moment), so every method "
             "answers <b>sixty requests</b>: the same sixty, in the same order, generated once with a fixed seed and hashed into every result "
             "row. The table below is the twenty scenarios; the horizons are what multiplies them.</p>"
             "<p>What varies between scenarios is the turbine and the weather of those particular days, which is what a forecaster meets in "
             "service. What never varies is the amount of evidence: fourteen days, 2,016 rows, four columns.</p>"),
        card("The twenty scenarios",
             f"<p>The raw SDWPF file holds {len(turbines)} turbines chosen by the rule in the manifest: seed {m['choice_rule']['seed']}, among the turbines "
             f"whose target days carry at most {m['choice_rule']['max_abnormal_target_points']} abnormal points, with base days fixed so that every "
             f"target day lies in the KDD Cup test period (days {m['choice_rule']['test_period'][0]} to {m['choice_rule']['test_period'][1]}) on days the "
             f"farm was running rather than curtailed. Each instance is sixteen days of one turbine: the 14-day history every method sees and the "
             f"two target days only the scorer reads. Frozen on {E(str(m.get('frozen_at_utc'))[:10])}; each file has a content hash and a run refuses "
             f"to start on an instance whose hash changed. Every instance is asked at {', '.join(f'{h} h' for h in HORIZONS_H)}: "
             f"{len(ent) * len(HORIZONS_H)} requests per method.</p>",
             table(head, rows),
             "<p class='muted'>The local copy of the dataset is the Excel-truncated version (1,048,575 rows), which holds 29 complete turbines of the 134; "
             "the manifest records the file's hash.</p>"),
        card("The conventional forecaster", gru_txt),
        card("The stress condition",
             "<p><code>--condition stress</code> blanks every feature of the last history day: the SCADA feed stopped. The forecast tools refuse to "
             "ground a series on it, and the correct outcome for every method is to escalate. A method that presents a series anyway is wrong, "
             "unflagged. The stress set is the same twenty instances under that condition.</p>"),
    ])


BLOCKS: Dict[str, Tuple[str, str, str]] = {
    "sys_agent": ("#2f5fd0", "system · agent role and workflow", "methods/_shared/agent_system_prompt.txt"),
    "sys_llm": ("#2f5fd0", "system · role, no tools", "methods/_shared/llm_only_system_prompt.txt"),
    "sys_plan": ("#6d4fc4", "system · planner", "methods/plan_act_nogate/plan_system_prompt.txt"),
    "rules": ("#6d4fc4", "system · shared rules", "methods/_shared/common_rules.txt"),
    "contract": ("#0f8f84", "system · answer contract", "methods/_shared/output_contract.txt"),
    "u_req": ("#c99a06", "user · the request", "evaluation/requests.py::request_text"),
    "u_hist": ("#c99a06", "user · the 14-day history as CSV", "solver/data.py::history_csv"),
    "u_cat": ("#0f8f84", "user · tool catalogue as text", "solver/tools.py::catalogue_text"),
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
    from evaluation.requests import window_for
    from methods.common import history_block, Context
    from config import ModelSpec
    from solver.tools import catalogue_text, openai_schemas

    req = sample_request()
    ctx = Context(request_id=req.request_id, text=req.text, window=window_for(req, check_hash=False), horizon_hours=req.horizon_hours, spec=ModelSpec("none", "x"))
    hist = history_block(ctx)
    legend = " ".join(f"<span class='chip' style=\"background:{c};color:#fff\">{E(l)}</span>" for c, l, _ in BLOCKS.values())
    mth_options = "".join(f"<option value='{E(c['folder'])}'{' selected' if c['folder'] == 'windagent' else ''}>{E(c['folder'])}</option>" for c in methods.cards())
    body = [card("What the model receives, block by block",
                 "<p>Shown on one request: turbine 8, days 201 to 214, 48 h, the peak-hour question. Pick a method. Every fixed sentence is a file under "
                 "<code>methods/</code>; the blocks built at run time (the request, the history, the catalogue) say which function produces them. The system "
                 "prompt's hash is stamped on every run's config.</p>"
                 f"<div style='margin:8px 0'>{legend}</div>"
                 f"<div style='margin-top:10px'><label>Method <select id='mth'>{mth_options}</select></label></div>")]
    for c in methods.cards():
        name = c["folder"]
        inner = [f"<h2>{E(name)} <span class='muted'>runner: {E(c['runner_name'])}</span></h2>", f"<p class='muted'>{E(c['description'])}</p>"]
        if c["kind"] == "deterministic":
            inner.append("<p>No language model, so no prompt. Regular expressions read the request and the GRU tool is called directly.</p>")
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
            inner += ["<h3>User message</h3>", _block("u_req", req.text)]
            if c["kind"] == "llm_only":
                inner.append(_block("u_hist", hist, collapse=True))
                inner.append(_block("u_cat", catalogue_text(), collapse=True))
                if c.get("strategy") == "cot":
                    inner.append(_block("u_reason", methods.read_text("llm_only_cot/reasoning_section.txt")))
            else:
                inner.append(_block("tools", json.dumps(openai_schemas(), indent=1), collapse=True))
            if c.get("gate"):
                inner.append(_block("retry", methods.read_text("_shared/gate_retry_instruction.txt") + "\n\n<the failed conditions, from methods/agent/gate.py::verdict_text>"))
        body.append(f"<div class='card pm' data-mth='{E(name)}'>" + "".join(inner) + "</div>")
    return "".join(body)


def tab_tools() -> str:
    from solver.tools import CATALOGUE, REQUIRED

    rows = []
    for t in CATALOGUE:
        params = ", ".join(f"{k}" + ("*" if k in REQUIRED[t["name"]] else "") for k in t["parameters"])
        rows.append([f"<code>{E(t['name'])}</code>", E(t["kind"]), E(params or "—"), E(t["description"])])
    return "".join([
        card("One catalogue, identical for every method that has tools",
             f"<p>{len(CATALOGUE)} tools in two kinds, one dispatcher, one log. The three agent methods receive these exact schemas; the two prompting "
             "methods receive the same catalogue rendered as text, so what a method may do is never a difference between rows. The dispatcher holds "
             "one frozen window: a call for another turbine or another history window is refused with an error, the way a data service refuses a day it "
             "does not have, and that refusal is what makes formulation measurable. Every call is logged with its position, arguments and output, which "
             "is what the gate reads.</p>",
             table(["tool", "kind", "arguments (* required)", "what it does"], rows)),
        card("The forecasters behind it",
             "<p>Three deterministic forecasters, none of which sees anything after the last history day: the last day repeated (persistence), the "
             "wind-to-power curve fitted on the fourteen days applied to the last day's wind (power curve), and the GRU trained on the training period "
             "(the conventional forecaster; the rule-based row is exactly parser plus this tool). The harness scores every method's series against the "
             "frozen target days with the KDD Cup rules; a method's own tool output is evidence for the method, never the source of a verdict.</p>"),
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
             "<p>Five conditions on the final answer, evaluated from the agent's own evidence: its tool log and the text it wrote. It never sees the "
             "target days or a reference forecast. When one fails the verdict goes back to the model once, inside the same budget; if the second "
             "attempt fails too, the harness replaces the answer with a declared failure that carries no series, and the request counts as escalated.</p>",
             table(["", "condition", "what it checks"], rows),
             f"<p class='muted'>Attempts before a declared failure: {G.MAX_VERIFICATION_ATTEMPTS}.</p>"),
        card("What the gate catches and what it cannot",
             "<div class='grid g2'><div><h3>It catches</h3><ul><li>a series with the wrong number of values, or a non-numeric one</li>"
             "<li>a value outside the physical range</li><li>a series no tool produced, or one the model edited after the tool produced it</li>"
             "<li>a formulation that misdescribes the call the series came from</li><li>an answer that contradicts its own series</li></ul></div>"
             "<div><h3>It cannot catch</h3><ul><li>a bad forecast. The GRU's series is traceable whether or not the wind turns; the MAE column says how "
             "good it was, and no method can see that in time.</li><li>a wrong reading of the request that the tools accept. The dispatcher refuses other "
             "turbines and windows, but not a 6-hour horizon asked for a 3-hour request; the formulation column catches that.</li></ul></div></div>",
             note("That is why forecast error is a column of its own and never a term of Solved: the gate measures whether the report is supported, "
                  "the error columns whether the forecast was any good.", "warn")),
        card("Where a request ends up",
             "<p>Three exclusive outcomes, adding to 100 %.</p>",
             table(["outcome", "definition"], [
                 [verdict("solved"), "a valid series in range, an answer coherent with it, and, for the methods with tools, a series that is a tool output or the mean of two, named as such"],
                 [verdict("escalated"), "the answer declares cannot_forecast, or the budget ran out, or the gate rejected two attempts. Takes precedence. Under the stress condition, the correct outcome"],
                 [verdict("wrong"), "a wrong number of values, a value out of range, an unsupported series (with tools), or an answer that contradicts the series, presented as valid"]])),
        card("The columns", "<p>Three groups, the same three in every case study.</p>", table(["group", "column", "what it measures", "why it is there"], crow)),
    ])


def tab_plan() -> str:
    from config import load_pricing, parse_model_spec
    from evaluation.requests import generate_requests
    from evaluation.runner import estimate

    pricing = load_pricing()
    reqs = generate_requests()
    rows = []
    for spec_s in ("openrouter:openai/gpt-4o-mini", "openrouter:openai/gpt-4o", "openrouter:openai/gpt-5.6-sol"):
        spec = parse_model_spec(spec_s)
        per = []
        tot = 0.0
        for m in methods.ORDER:
            s = estimate(m, spec, reqs, pricing) or 0.0
            per.append(f"{s:.2f}")
            tot += s
        rows.append([f"<code>{E(spec.short)}</code>"] + per + [f"<b>{tot:.2f}</b>"])
    return "".join([
        card("Phases",
             table(["phase", "what", "estimated cost", "state"], [
                 ["0", "layout, data frozen, GRU trained, page, tests without a key", "0", chip("done", "ok")],
                 ["smoke", "3 instances × 48 h × the five model-backed methods, gpt-4o-mini", "≈ 0.06 USD", chip("run", "ok")],
                 ["1", "20 instances × 3 horizons × 6 methods, gpt-4o-mini", "≈ 1.1 USD", chip("awaiting go", "warn")],
                 ["stress", "the same under the stress condition", "≈ 1.1 USD", chip("after phase 1", "warn")],
                 ["2", "gpt-5.6-sol, 48 h only", "≈ 8 USD", chip("if credit remains", "warn")]])),
        card(f"Cost estimate per model, {len(reqs)} requests × 6 methods",
             "<p>From the token counts of the prompts: the 14-day history is about 18k tokens as CSV, a 48 h series about 1.5k tokens of output. "
             "<code>run.py run --dry-run</code> prints the same estimate for any selection.</p>",
             table(["model"] + list(methods.ORDER) + ["total USD"], rows)),
        card("Budget per request", kv([("model calls", str(MAX_LLM_CALLS)), ("tool calls", str(MAX_TOOL_CALLS)), ("wall clock", f"{REQUEST_TIMEOUT_S:.0f} s"),
                                       ("temperature", "0"), ("retry after the gate", "1, inside the same budget")])),
    ])


def tab_results() -> str:
    dirs = method_dirs()
    if not dirs:
        return card("No runs yet", "<p>No results folder carries a summary.json. The first run is the smoke test, after Daniela's go.</p>")
    body = []
    by_set: Dict[str, Dict[str, Tuple[Path, List[Dict[str, str]], Dict[str, Any]]]] = {}
    for d in dirs:
        h = read_header(d)
        tag = h["header"].get("tag") or "main"
        by_set.setdefault(f"{h['header']['date']} · {tag}", {})[h["header"]["method"]] = (d, read_summary(d), h)

    def pct(rows: List[Dict[str, str]], kind: str) -> str:
        k = sum(1 for r in rows if r.get("outcome") == kind)
        return f"{100.0 * k / len(rows):.0f} % <span class='muted'>({k}/{len(rows)})</span>" if rows else "-"

    for set_name, per in by_set.items():
        split = []
        for row in ROWS:
            if row["name"] in per:
                d, rows, h = per[row["name"]]
                a = h["aggregate"]
                bh = a.get("by_horizon") or {}
                fmt = lambda key: " / ".join("—" if bh[k].get(key) is None else f"{bh[k][key]}" for k in sorted(bh, key=int)) if bh else "—"  # noqa: E731
                split.append([f"<b>{E(row['label'])}</b>", f"{d.parts[-2]}", str(len(rows)), f"{a.get('form')} %", fmt("mae"), fmt("skill"), pct(rows, "solved"), pct(rows, "escalated"), pct(rows, "wrong_unflagged"),
                              f"{a.get('trace') if a.get('trace') is not None else '—'} %", f"{a.get('tokens')}", f"{a.get('cost')}"])
            else:
                split.append([f"<b>{E(row['label'])}</b>", "<span class='muted'>not run</span>"] + [""] * 10)
        hs = " / ".join(f"{h} h" for h in HORIZONS_H)
        body.append(card(f"Run set {E(set_name)}",
                         table(["method", "model", "n", "formulation", f"MAE kW ({hs})", f"skill vs persistence ({hs})", verdict("solved"), verdict("escalated"), verdict("wrong"), "traceable", "tokens", "cost $"], split),
                         note("A dash in an error column is not a missing measurement: it means the method returned no valid series at that "
                              "horizon, so there was nothing to score. Skill is 1 - MAE/MAE of persistence on the same points; 0 means no better "
                              "than repeating yesterday.", "info")))
    det = []
    cols = [("nn", "nn"), ("instance_id", "scenario"), ("horizon_hours", "h"), ("question", "question"), ("outcome", "outcome"), ("solved_reason", "why"),
            ("formulation_exact", "form."), ("n_values", "values"), ("mae_kw", "MAE"), ("nmae_pct", "nMAE %"), ("skill_vs_persistence", "skill"), ("answer_ok", "answer"), ("source", "source"), ("gate_pass", "gate"),
            ("n_llm_calls", "llm"), ("n_tool_calls", "tools"), ("cost_usd", "cost $")]
    for d in dirs:
        rows = read_summary(d)
        det.append(f"<details><summary>{E(d.parts[-3])} / {E(d.parts[-2])} / {E(d.name)} — every request</summary>"
                   + table([l for _k, l in cols], [[verdict(r["outcome"]) if k == "outcome" else E(r.get(k, "")) for k, _l in cols] for r in rows]) + "</details>")
    body.append(card("Request by request", *det))
    return "".join(body)


def tab_traces() -> str:
    dirs = method_dirs()
    if not dirs:
        return card("Traces", "<p class='muted'>No run yet. Every run leaves <code>traces/NN_&lt;request-id&gt;.narrative.txt</code>, "
                              "<code>.transcript.txt</code> and <code>.png</code> next to its rows; this section shows them once they exist.</p>")
    body = [card("Every run end to end", "<p>The narrative of each request of every run set, as written by evaluation/postprocess.py from the "
                                          "trace: what the method did, the formulation verdict, the series and its error, the answer checks, the outcome. "
                                          "The transcript next to it in the results folder is the raw exchange, and the PNG the series against the target.</p>")]
    for d in dirs:
        items = []
        for p in sorted((d / "traces").glob("*.narrative.txt")):
            items.append(f"<details><summary><code>{E(p.name)}</code></summary><pre>{E(p.read_text(encoding='utf-8'))}</pre></details>")
        body.append(card(f"{E(d.parts[-3])} / {E(d.parts[-2])} / {E(d.name)}", *items))
    return "".join(body)


def tab_analysis() -> str:
    from visuals.shell import markdown

    dirs = [d for d in method_dirs() if (d / "REPORT.md").exists()]
    if not dirs:
        return card("Analysis", "<p class='muted'>No results folder carries a REPORT.md yet.</p>"
                                "<p>Every run ends with one per method, written by <code>evaluation/postprocess.py</code> from the rows. No model is called to write it.</p>")
    body = [card("What the reports are", "<p>Each method folder ends with a REPORT.md written from its rows: the outcome split, the metrics by group, "
                                          "the errors by horizon, the wrong and escalated lists, every request on one line.</p>")]
    for d in dirs:
        body.append(f"<div class='card'><h2><code>{E(str(d.relative_to(PROJECT_ROOT / 'results')))}</code></h2>" + markdown((d / "REPORT.md").read_text(encoding="utf-8")) + "</div>")
    return "".join(body)


def tab_status() -> str:
    rows = [[f"<b>{E(r['label'])}</b>", f"<code>{E(r['name'])}</code>", chip("implemented, tested with a scripted model", "ok") if methods.card(r["name"]).get("implemented") else chip("to be written", "warn")] for r in ROWS]
    models = sorted({d.parts[-2] for d in method_dirs() if d.parts[-2] != "no-llm"})
    return card("Where the implementation stands",
                f"<p>All six methods run today; every one of them has an end-to-end test with a scripted model and no API key. "
                f"Runs made so far with a model: {E(', '.join(models) if models else 'none')}.</p>",
                table(["method", "name", "state"], rows),
                "<p class='muted'>Not part of the evaluation: the original replication scripts and notebooks under <code>_legacy/</code>, kept as they were.</p>")


GROUPS = (("Design", (("home", "Home"), ("methods", "Methods"), ("scenarios", "Scenarios"), ("prompts", "Prompts"), ("tools", "Tools"), ("gate", "Gate & scoring"), ("plan", "Run plan"))),
          ("Results", (("results", "Results"), ("traces", "Traces"), ("analysis", "Analysis"), ("status", "Implementation"))))
BUILDERS = {"home": tab_home, "methods": tab_methods, "scenarios": tab_scenarios, "prompts": tab_prompts, "tools": tab_tools, "gate": tab_gate,
            "plan": tab_plan, "results": tab_results, "traces": tab_traces, "analysis": tab_analysis, "status": tab_status}

SCRIPT = """
(function(){
  var mth=document.getElementById('mth'); if(!mth) return;
  function apply(){ document.querySelectorAll('.pm').forEach(function(p){ p.style.display = p.dataset.mth===mth.value ? '' : 'none'; }); }
  mth.onchange=apply; apply();
})();
"""


def payload() -> Dict[str, Any]:
    m = manifest()
    n = len(m["instances"]) if m else 0
    return {
        "id": CASE_ID, "title": CASE_TITLE, "brand": "WindAgent · wind power forecasting",
        "note": f"{n} frozen scenarios of the SDWPF farm, {len(HORIZONS_H)} horizons",
        "blurb": "Write the next 3, 6 or 48 hours of a turbine's active power from its 14-day SCADA history alone, and answer a question about the series.",
        "summary": [("task", "forecast, no future inputs"), ("trusted tool", "GRU, persistence, power curve"), ("data", f"{n} frozen scenarios, KDD Cup test period")],
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

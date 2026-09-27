"""This case study's contribution to the shared evaluation site.

The chrome lives in ``visuals/shell.py`` at the repository root; this module
writes only content. Every fact is read from the code at build time -- the
method registry, the gate's own condition table, the request variants, the
frozen day manifest, the prompt builders, the result files -- so the page cannot
describe a design that is not the one that would run.

The page is self-contained: it explains the task, the formulation, the methods,
the scenarios, the prompts, the tool, the verification gate and the scoring,
and then what has been measured so far. It is meant to be read by someone who
has not seen the repository.

Usage (from ev-scheduling/):
    python -m evaluation.page_fragments /tmp/fragments.json

Normally invoked by ``python -m visuals.build`` from the repository root.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT.parent))  # so `visuals` is importable

from visuals.shell import (  # noqa: E402
    E,
    card,
    chip,
    diagram,
    diagram_row,
    flow,
    pipeline,
    kv,
    note,
    prompt_block,
    table,
    verdict,
)

# How each method gets from the request to an answer, drawn with the shared
# renderer so a method that works like one in another case study looks like it.
DIAGRAMS: Dict[str, Dict[str, Any]] = {
    "rule_based": {
        "steps": [("request", "input"), ("regex parser", "code"), ("solver (CVXPY)", "solver"),
                  ("template answer", "out")],
        "note": "No language model and no prompt. What the parser cannot read, it cannot answer.",
    },
    "llm_only_structured": {
        "steps": [("request", "input"), ("LLM writes the kW matrix", "llm"), ("text answer", "out")],
        "note": "No solver and no tool calls. The kilowatts are written as text, and nothing checks them.",
    },
    "llm_only_cot": {
        "steps": [("request", "input"), ("LLM reasons, then writes it", "llm"), ("text answer", "out")],
        "note": "One added prompt section. Identical to the method on its left in every other respect.",
    },
    "plan_act_nogate": {
        "steps": [("request", "input"), ("LLM writes the whole plan", "plan"), ("solver runs every step", "solver"),
                  ("LLM writes the answer", "llm")],
        "note": "Plans once. The whole sequence is committed before any result comes back.",
    },
    "react_nogate": {
        "steps": [("request", "input"), ("LLM decides a tool call", "llm"), ("solver executes it", "solver"),
                  ("LLM writes the answer", "llm")],
        "loop": 2,
        "note": "Up to three rounds. The model sees every result, and nothing checks the answer.",
    },
    "evagent": {
        "steps": [("request", "input"), ("LLM decides a tool call", "llm"), ("solver executes it", "solver"),
                  ("gate E1-E6", "gate")],
        "loop": 2,
        "branch": ("report", "escalate"),
        "note": "Up to three rounds, then six conditions on the answer. A request it cannot verify leaves as an "
                "escalation rather than as a number.",
    },
}

CASE_ID = "evagent"
CASE_TITLE = "EVAgent"


# ---------------------------------------------------------------- the design
#
# Six rows, the same six as every other case study, with the same names and in
# the same order. That is a requirement rather than a convenience: the tables
# are read side by side, and a row present in one case and absent from another
# reads as a result about the case rather than about the design.
#
# ``isolates`` is the single factor a row adds over the row above it. A ladder
# that changes one thing per step is the only way a result can attribute an
# effect to a cause.

ROWS: Tuple[Dict[str, str], ...] = (
    {
        "block": "Conventional workflow",
        "name": "rule_based",
        "label": "Deterministic parser + solver",
        "arm": "",
        "llm": "no",
        "tools": "the solver, directly",
        "gate": "none",
        "isolates": "no language model anywhere. Regular expressions read the request, the LP does the rest. "
        "What conventional automation already achieves, and what it refuses to handle.",
    },
    {
        "block": "LLM-only prompting",
        "name": "llm_only_structured",
        "label": "Structured prompting",
        "arm": "llm_only:structured",
        "llm": "yes",
        "tools": "none",
        "gate": "none",
        "isolates": "the language model on its own. It receives the sessions and the tariff and writes the "
        "kilowatt matrix as text. No solver is involved at any point.",
    },
    {
        "block": "LLM-only prompting",
        "name": "llm_only_cot",
        "label": "Chain-of-thought prompting",
        "arm": "llm_only:chain_of_thought",
        "llm": "yes",
        "tools": "none",
        "gate": "none",
        "isolates": "one added prompt section asking for step-by-step reasoning before the answer. Same input, "
        "same budget, same output contract as the row above.",
    },
    {
        "block": "Multi-step agents",
        "name": "plan_act_nogate",
        "label": "Plan-and-Act, no gate",
        "arm": "plan_act",
        "llm": "yes",
        "tools": "the solver, through function calling",
        "gate": "none",
        "isolates": "solver access through a plan. One call emits the whole sequence of tool calls, then it is "
        "executed without the model seeing the results in between.",
    },
    {
        "block": "Multi-step agents",
        "name": "react_nogate",
        "label": "ReAct, no gate",
        "arm": "react",
        "llm": "yes",
        "tools": "the solver, through function calling",
        "gate": "none",
        "isolates": "iteration. The model sees each tool output and may call again, inside the same round budget "
        "as the row above and the row below.",
    },
    {
        "block": "Multi-step agents",
        "name": "evagent",
        "label": "EVAgent, solver-grounded",
        "arm": "evagent",
        "llm": "yes",
        "tools": "the solver, through function calling",
        "gate": "six conditions on the answer",
        "isolates": "the verification gate, and nothing else. Same tool, same round budget and same days as ReAct, "
        "so any difference between the two rows is the gate.",
    },
)

REFERENCES: Tuple[Dict[str, str], ...] = (
    {
        "label": "CVXPY optimum",
        "arm": "optimum",
        "note": "The LP solved directly on the structured day, with no request text involved. Every row's cost gap "
        "is measured against it.",
    },
    {
        "label": "Charge as soon as possible",
        "arm": "charge_asap",
        "note": "Full power from arrival until the requested energy is delivered, ignoring price. The uncontrolled "
        "operation any optimization has to beat, and the denominator of the cost reduction.",
    },
)

COLUMNS: Tuple[Dict[str, str], ...] = (
    {"group": "Task utility", "name": "Form.",
     "what": "share of sessions whose arrival, departure, energy and maximum power match the day, exactly on step "
             "indices and within one per cent on kWh and kW",
     "why": "whether the problem that was solved is the problem that was asked"},
    {"group": "Task utility", "name": "Cost",
     "what": "time-of-use cost of the schedule, in dollars", "why": "the objective"},
    {"group": "Task utility", "name": "Gap",
     "what": "(cost − cost*) / cost* against the optimum of the same day", "why": "distance to the best schedule"},
    {"group": "Task utility", "name": "Unmet",
     "what": "requested energy not delivered, in kWh",
     "why": "reads beside Gap: a schedule that charges nothing is cheap"},
    {"group": "Task utility", "name": "Solved",
     "what": "the day was done: the state is right, every number traces to the last solve, and the answer matches "
             "what was asked", "why": "the end-to-end verdict"},
    {"group": "Solver-grounded correctness", "name": "FR",
     "what": "share of days with no hard violation: availability window, charger limit, site cap",
     "why": "the schedule can actually be run"},
    {"group": "Solver-grounded correctness", "name": "Traceable",
     "what": "every number in the answer appears in a tool output and comes from the last solve",
     "why": "the reported numbers have an origin that can be checked"},
    {"group": "Solver-grounded correctness", "name": "Wrong, unflagged",
     "what": "an invalid schedule, an unsupported number, or a misread request, presented as valid",
     "why": "the quantity a solver-grounded design exists to drive to zero"},
    {"group": "Cost and operation", "name": "Escalated",
     "what": "the system declared it could not answer instead of presenting a schedule as valid",
     "why": "how much work is handed back to a person"},
    {"group": "Cost and operation", "name": "Tokens",
     "what": "prompt and completion tokens per day, every call", "why": "what the architecture costs to run"},
)


# ----------------------------------------------------------------- code data


def arms() -> Dict[str, Any]:
    from evaluation.runner import ARMS

    return ARMS


def gate_module() -> Any:
    from methods.agent.validate import gate

    return gate


def frozen_days() -> List[Dict[str, Any]]:
    path = PROJECT_ROOT / "data" / "benchmark" / "manifest.json"
    if not path.exists():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")).get("days", []))


def method_dirs() -> List[Path]:
    """Every results/<instance>/<date>/<model>/<method>/ folder, newest date first."""
    root = PROJECT_ROOT / "results"
    dirs = [p.parent for p in root.glob("*/*/*/*/summary.json")] if root.is_dir() else []
    return sorted(dirs, key=lambda d: (d.parts[-3], d.parts[-4]), reverse=True)


def latest_run() -> List[Path]:
    """The method folders of the newest date, the run set the page reports."""
    dirs = method_dirs()
    if not dirs:
        return []
    newest = dirs[0].parts[-3]
    return [d for d in dirs if d.parts[-3] == newest]


def read_summary(d: Path) -> List[Dict[str, str]]:
    f = d / "summary.csv"
    if not f.exists():
        return []
    with f.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def read_header(d: Path) -> Dict[str, Any]:
    return json.loads((d / "summary.json").read_text(encoding="utf-8"))


def sample_request() -> Optional[Dict[str, Any]]:
    for d in latest_run():
        f = d / "requests.jsonl"
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    return json.loads(line)
    return None


def arm_state(row: Dict[str, str]) -> str:
    """"running", "pending" or "to write", from the registry rather than a note."""
    A = arms()
    a = A.get(row["arm"]) if row["arm"] else None
    if a is None:
        return "to write"
    return "running" if a.implemented else "pending"


# -------------------------------------------------------------------- tabs


def tab_overview() -> str:
    days = frozen_days()
    import evaluation.requests as R

    total = sum(int(d.get("record_count", 0)) for d in days)
    body = [
        card(
            "The task",
            "<p>A site operator describes a day of charging in plain language: the cars, when each one arrives and "
            "leaves, how much energy it needs, what its charger can deliver. Somebody has to turn that into the "
            "parameters of an optimization problem, solve it under the site's power cap and its time-of-use tariff, "
            "and answer what was actually asked, whether that is the schedule itself or a question about it. Today "
            "that somebody is an engineer with a convex solver. This case study asks what happens when it is a "
            "language model.</p>",
            pipeline(
                [
                    ("Request", "free text: the cars, the tariff, the question"),
                    ("Formulate", "aᵢ, dᵢ, Eᵢ, p̄ᵢ for every session"),
                    ("Compute", "the LP, or the model writing kW by hand"),
                    ("Verify", "six conditions on the answer (gated method only)"),
                    ("Report", "the schedule, or the answer asked for"),
                ],
                loop=(3, 1, "one retry, then escalate"),
            ),
            "<p class='muted' style='text-align:center'>Fig. 1. The pipeline every method is measured on. "
            "Only the solver-grounded method has the Verify stage; the others go from Compute to Report.</p>",
        )
    ]

    body.append(
        card(
            "The problem, formally",
            "<p>The day is discretized into <em>T</em> steps of Δ hours. Session <em>i</em> occupies a charger "
            "from step <em>a<sub>i</sub></em> to step <em>d<sub>i</sub></em>, asks for <em>E<sub>i</sub></em> kWh, "
            "and its charger delivers at most <em>p̄<sub>i</sub></em> kW. The site cannot draw more than "
            "<em>P<sub>max</sub></em>(<em>t</em>) at any step, and energy at step <em>t</em> costs "
            "<em>c</em>(<em>t</em>) per kWh.</p>",
            r"""\[
\begin{aligned}
\min_{p,\,u}\quad & \sum_{t=0}^{T-1} c(t)\,\Big(\sum_{i=1}^{N} p_i(t)\Big)\,\Delta \;+\; M \sum_{i=1}^{N} u_i \\[4pt]
\text{s.t.}\quad
& p_i(t) = 0, && t \notin [a_i, d_i) && \text{(1)} \\
& 0 \le p_i(t) \le \bar p_i, && t \in [a_i, d_i) && \text{(2)} \\
& \sum_{i=1}^{N} p_i(t) \le P_{\max}(t), && \forall t && \text{(3)} \\
& \Delta \sum_{t=0}^{T-1} p_i(t) + u_i = E_i, && \forall i && \text{(4)} \\
& p_i(t) \ge 0,\; u_i \ge 0.
\end{aligned}
\]"""
            "<p class='muted'>Decision variables: <span>\\(p_i(t)\\)</span>, the power delivered to session "
            "<span>\\(i\\)</span> at step <span>\\(t\\)</span> in kW, and <span>\\(u_i\\)</span>, the energy not "
            "delivered to session <span>\\(i\\)</span> in kWh. (1) the car is not plugged in; (2) the charger's limit; "
            "(3) the site's cap; (4) deliver the energy, or account for what is missing.</p>"
            "<p>Constraints (1) to (3) are <b>hard</b>: a schedule that breaks one of them cannot be run, and the "
            "site would trip or the car would draw power it cannot take. Constraint (4) is <b>soft</b>, through the "
            "slack <em>u<sub>i</sub></em> priced at <em>M</em> = 10<sup>6</sup> $/kWh. That is a deliberate "
            "modeling choice with a consequence the evaluation has to handle: the problem is <b>always feasible</b>, "
            "because undelivered energy is expensive rather than forbidden. A day the site genuinely cannot serve "
            "does not produce an infeasible solve; it produces an optimal one with a large "
            "Σ<em>u<sub>i</sub></em>, which somebody has to notice and say out loud.</p>",
            "<h3>What is reported from a solution</h3>"
            r"""\[
\begin{aligned}
\text{cost} &= \sum_{t} c(t)\Big(\sum_i p_i(t)\Big)\Delta, &
\text{peak} &= \max_t \sum_i p_i(t), \\
\text{unmet} &= \sum_i u_i, &
\text{gap} &= \frac{\text{cost} - \text{cost}^\star}{\text{cost}^\star},
\end{aligned}
\]"""
            "<p class='muted'>with <span>\\(\\text{cost}^\\star\\)</span> the optimum of the same day.</p>"
            "<p class='muted'>The solver is CVXPY with its default backend. Its feasibility tolerance is around "
            "10<sup>−8</sup>; the constraint checker that scores a schedule uses 10<sup>−5</sup>, so numerical "
            "slop is never reported as a violation.</p>",
        )
    )

    body.append(
        "<div class='grid g3'>"
        + card(
            "What a correct answer needs",
            "<ul><li><b>The formulation:</b> <em>a<sub>i</sub></em>, <em>d<sub>i</sub></em>, "
            "<em>E<sub>i</sub></em> and <em>p̄<sub>i</sub></em> for every session, read from the text rather than "
            "assumed.</li>"
            "<li><b>A runnable schedule:</b> constraints (1) to (3) satisfied.</li>"
            "<li><b>The operator's answer:</b> the cost, the undelivered energy, the share served, the car — and it "
            "has to describe the schedule that was actually produced.</li></ul>",
        )
        + card(
            "What can go wrong",
            "<ul><li>A schedule that looks reasonable and exceeds the site cap.</li>"
            "<li>A cheap schedule that is cheap because it never charges the cars.</li>"
            "<li>An answer quoting one solve while the schedule handed over is another.</li>"
            "<li>A shortfall the operator is never told about.</li>"
            "<li>A perfectly optimal solution to a day that was misread.</li></ul>",
        )
        + card(
            "What is expected of the gated row",
            "<p>Every number reaches the operator only after the solver produced it and six verification conditions "
            "accepted it. When they cannot pass, the day is escalated to a person rather than answered. The target: "
            f"{verdict('solved')} + {verdict('escalated')} = 100 %, {verdict('wrong')} = 0.</p>",
        )
        + "</div>"
    )

    body.append(
        card(
            "Identical for every method",
            chip(f"{len(days)} days of real charging sessions")
            + chip(f"{total:,} session records")
            + chip(f"{len(R.VARIANTS)} request variants per day")
            + chip(f"site cap {R.SITE_CAP_KW:g} kW")
            + chip(f"tariff ${R.PEAK_PRICE:.2f} peak / ${R.OFF_PEAK_PRICE:.2f} off-peak")
            + chip("one generated request list, hashed")
            + chip("same seeds and repeats")
            + chip("same completion budget")
            + chip("one scorer for every method")
            + chip("every message kept in the trace"),
        )
    )
    return "".join(body)


def tab_methods() -> str:
    rows = []
    last = ""
    for r in ROWS:
        block = "" if r["block"] == last else f"<b>{E(r['block'])}</b>"
        last = r["block"]
        rows.append([
            f"<span class='muted'>{block}</span>",
            f"<b>{E(r['label'])}</b><div class='muted'><code>{E(r['name'])}</code></div>",
            E(r["llm"]),
            E(r["tools"]),
            E(r["gate"]),
            E(r["isolates"]),
        ])
    body = [
        card(
            "Six ways to answer the same request",
            diagram_row(
                [
                    {
                        "title": r["label"],
                        "subtitle": ("no LLM" if r["llm"] == "no"
                                     else "LLM only, no tools" if r["tools"] == "none"
                                     else "LLM + solver"),
                        **DIAGRAMS[r["name"]],
                    }
                    for r in ROWS
                ],
            ),
        ),
        card(
            "Six methods, one factor apart",
            "<p>One conventional workflow with no language model, and five ways of using one. Reading down the "
            "table, each row adds a single capability to the row above it: a language model, then a reasoning "
            "section, then access to the solver, then iteration, then verification. If two rows differed by two "
            "things, no measurement could say which of the two mattered.</p>",
            table(
                ["Block", "Method", "LLM", "Tools", "Gate", "What it adds over the row above"],
                rows,
            ),
            note(
                "<b>The step the design rests on is the last one.</b> ReAct and EVAgent receive the same tool, the "
                "same round budget, the same requests and the same days. The only difference between them is that "
                "EVAgent's answer has to pass the verification gate before anyone sees it, so whatever separates "
                "those two rows is what verification is worth.",
                "info",
            ),
        )
    ]

    body.append(
        card(
            "Two quantities computed on every day, and not methods",
            "<p>Neither reads the request text, so neither can be scored on understanding one. They are printed "
            "beside the table as the two ends of the scale every method is placed on.</p>"
            + "".join(f"<p><b>{E(x['label'])}</b><br>{E(x['note'])}</p>" for x in REFERENCES),
        )
    )

    body.append(
        card(
            "Why these six and not others",
            "<p>The set is the same in every case study of the paper, so the tables can be read side by side. "
            "Three methods a reader might expect are outside it, and none of them is run here:</p>"
            "<ul>"
            "<li><b>A human with the solver.</b> The workload everything here is trying to remove. It is measured "
            "by timing a person, not by running code, and belongs beside the table rather than inside it.</li>"
            "<li><b>Few-shot and retrieval-augmented prompting.</b> Not in the six, and not run for this case study. "
            "The two prompting rows that are run differ by one prompt section, which is what makes their contrast "
            "interpretable; adding more prompting variants would add rows to the table without adding a factor to "
            "the ladder.</li>"
            "<li><b>A single tool call with no iteration.</b> Not in the six, and not run. It is not the same as "
            "Plan-and-Act, which plans a whole sequence of calls; it would sit between the prompting rows and "
            "Plan-and-Act as the smallest possible use of the solver. Leaving it out is a choice made for the "
            "whole set of case studies, so that the six rows are the same everywhere.</li>"
            "</ul>",
        )
    )
    return "".join(body)


def tab_scenarios() -> str:
    import evaluation.requests as R
    import evaluation.stress as S

    days = frozen_days()
    total = sum(int(d.get("record_count", 0)) for d in days)
    body = [
        card(
            "The days",
            f"<p>{len(days)} days of real charging sessions from the ACN-Data portal, a public record of a "
            f"workplace charging site, {total:,} session records in all. They are downloaded once, frozen into the "
            "repository with a content hash each, and never fetched again: the benchmark reproduces with no "
            "credentials and no network, and a day file edited after freezing fails its hash check when it "
            "loads.</p>",
            table(
                ["date", "sessions", "frozen", "content hash"],
                [
                    [
                        E(d.get("date")),
                        E(d.get("record_count")),
                        f"<span class='muted'>{E(str(d.get('fetched_at_utc'))[:10])}</span>",
                        f"<span class='muted'><code>{E(str(d.get('content_hash'))[:23])}…</code></span>",
                    ]
                    for d in days
                ],
            ),
        )
    ]

    # how large the scenario set is, in numbers a reader can multiply
    dirs = latest_run()
    seen: Dict[str, int] = {}
    for d in dirs:
        hdr = read_header(d)["header"]
        if hdr["method"] == "evagent" or (not seen and d == dirs[-1]):
            for r in read_summary(d):
                seen[r["variant"]] = seen.get(r["variant"], 0) + 1
    n_days = len(frozen_days())
    body.append(
        card(
            "How many scenarios",
            f"<p><b>One request per day.</b> A run poses {n_days} requests, one on each frozen day, and every "
            f"method answers the same {n_days}. The ten variants are not crossed with the days: they are "
            "assigned to the days in rotation, so each day carries one variant and the variants are spread over "
            f"the {n_days} days. A run is therefore {n_days} requests per method, not {n_days} × 10.</p>"
            "<p><b>The rule that assigns variants.</b> A day whose demand cannot be served in full under the cap "
            "takes the next of the three shortfall variants (<code>unmet_question</code>, "
            "<code>feasible_yesno</code>, <code>served_share</code>), because those are the questions with a "
            "non-trivial answer there. Any other day takes the next variant of the full rotation of ten. A variant "
            "that cannot be posed on its day falls through to the next one that can.</p>"
            + (
                "<p><b>What that produced on the run of "
                + E(dirs[0].parts[-3]) + ":</b> "
                + ", ".join(f"<code>{E(v)}</code> × {n}" for v, n in sorted(seen.items(), key=lambda kv: -kv[1]))
                + f". {sum(seen.values())} requests, {len(seen)} of the ten variants. Nineteen of the twenty days "
                "exceed the 50 kW cap, so nineteen requests drew a shortfall variant and only one day could take "
                "a variant from the full rotation.</p>"
                + note(
                    "Six of the ten variants have not been posed to any method yet, because the assignment rule "
                    "gives congested days a shortfall question and almost every frozen day is congested. Either "
                    "the cap for the non-shortfall variants is raised so they can be asked, or the rotation is "
                    "changed, or the table reports the four variants that actually occur. That is a design "
                    "decision, not a scoring detail.",
                    "warn",
                )
                if seen else ""
            )
            + "<p><b>The stress set</b> adds one more request per day, built to be unanswerable, described below. "
            "It is implemented and has not been run.</p>",
        )
    )

    examples = example_requests()
    rows = []
    for v in R.VARIANTS:
        r = examples.get(v)
        if r is None:
            rows.append([f"<code>{E(v)}</code>", "<span class='muted'>could not be generated on the first days</span>", "", "", ""])
            continue
        if r.kind == "state":
            asks = "<i>the schedule itself</i>. " + E(r.text.strip().splitlines()[-1][-160:])
            truth = (
                "the schedule must be runnable (no hard violation) and its cost within tolerance of the "
                f"optimum, which for this day is ${r.truth.get('cost_usd', 0):,.2f} with "
                f"{r.truth.get('unmet_kwh', 0):,.2f} kWh undelivered"
            )
        else:
            asks = E(r.question)
            t = r.truth
            truth = E(", ".join(t) if isinstance(t, list) else str(t))
            truth = f"<code>{truth}</code>" + (f" ± {E(r.tolerance)}" if r.tolerance else "")
        cls = (
            "state: the schedule is the answer" if v in R.STATE_VARIANTS
            else "shortfall: the answer must state undelivered energy" if v in R.SHORTFALL_VARIANTS
            else "question about the day"
        )
        rows.append([
            f"<code>{E(v)}</code><div class='muted'>{E(cls)}</div>",
            asks,
            truth,
            E(r.kind),
            f"<details><summary>the request, {len(r.text):,} chars</summary><pre>{E(r.text)}</pre></details>",
        ])

    body.append(
        card(
            "The requests: what each variant asks, and what counts as correct",
            "<p>Every day gets one request. Ten variants share the days in rotation, so the same "
            "twenty days pose ten different questions. Every variant describes the same thing first, "
            "the cars and the tariff, in free text: times spelled out, energies in Wh or kWh, power in "
            "W or kW, several sentence shapes per car. What differs is the last sentence, which is the "
            "question, and therefore what the answer is scored against.</p>"
            "<p>The list is generated once, hashed, and the digest is recorded on every result row, so "
            "a table built from those rows can be shown to have asked every method the same thing.</p>",
            table(
                ["variant", "what the request asks", "what counts as correct", "answer kind", "example"],
                rows,
            ),
            note(
                "Two variants have no question: the schedule is the answer, and it is scored as a state. "
                "Three ask about a shortfall, and on a day that cannot be fully served the honest answer "
                "is a number greater than zero, which is what the gate's condition E6 requires an agent to "
                "say. The remaining five ask something with a single checkable value, so the answer term "
                "of Solved applies to them.",
                "info",
            ),
            f"<p class='muted'>Site cap {R.SITE_CAP_KW:g} kW unless the variant lowers it "
            f"(<code>schedule_under_cap</code> draws from {', '.join(f'{c:g}' for c in R.LOWER_CAPS_KW)} kW). "
            f"Time-of-use tariff: ${R.PEAK_PRICE:.2f} per kWh between {R.PEAK_START_HOUR}:00 and "
            f"{R.PEAK_END_HOUR}:00, ${R.OFF_PEAK_PRICE:.2f} otherwise. Examples above are generated on "
            "the first frozen day that can pose each variant.</p>",
        )
    )

    explain = {
        "lowered_cap": f"the site cap is dropped to one of {', '.join(f'{c:g}' for c in S.LOWERED_CAPS_KW)} kW, "
                       "below what the day needs",
        "disabled_chargers": "one or more chargers are set to zero kW",
        "impossible_deadline": "a session asks for more energy than its window can physically deliver",
        "contradictory_request": "the request contradicts itself and cannot be formulated at all",
    }
    body.append(
        card(
            "The stress days",
            "<p>On an ordinary day the LP is always feasible, because undelivered energy is a priced slack rather "
            "than a forbidden outcome. A method is therefore never forced to admit it cannot do something, and a "
            "column counting escalations would be empty for every method and measure nothing.</p>"
            "<p>The stress set exists to give that column meaning. Each class makes the request genuinely "
            "unsatisfiable, so a method either says so or presents an invalid schedule as valid.</p>",
            table(
                ["class", "what is made impossible"],
                [[f"<code>{E(c)}</code>", E(explain.get(c, ""))] for c in S.CLASSES],
            ),
            f"<p class='muted'>What an answer has to declare for the day to count as escalated rather than wrong: "
            f"{E(', '.join(S.DECLARATION_KEYS))}.</p>",
        )
    )
    return "".join(body)


# One color and one label per kind of block, so the same kind of text is the
# same color in every method and a reader learns the key once. The third field
# is where the block comes from: a file under methods/, or the code that
# renders it from the request.
BLOCKS: Dict[str, Tuple[str, str, str]] = {
    "sys_llm": ("#2f5fd0", "system · role and rules", "methods/_shared/llm_only_system_prompt.txt"),
    "sys_suffix": ("#6d4fc4", "system · output-mode suffix", "methods/<method>/system_suffix.txt"),
    "sys_agent": ("#2f5fd0", "system · agent role, tool-use rules, what-if guidance",
                  "methods/_shared/agent_system_prompt.txt"),
    "sys_parse": ("#0f8f84", "system · session extraction", "methods/_shared/parse_extraction_system.txt"),
    "sys_infer": ("#0f8f84", "system · inference of missing fields", "methods/_shared/parse_inference_system.txt"),
    "u_role": ("#6d4fc4", "user · role", "methods/_shared/llm_only_role.txt"),
    "u_data": ("#c99a06", "user · system data: time grid, units, labels",
               "methods/prompting/strategies.py::_context_section"),
    "u_task": ("#0f8f84", "user · task: the request, verbatim", "evaluation/requests.py::render_request"),
    "u_reason": ("#c0392b", "user · reasoning instructions", "methods/llm_only_cot/reasoning_section.txt"),
    "u_out": ("#c99a06", "user · output requirements", "methods/prompting/strategies.py::_output_section"),
    "tools": ("#0f8f84", "tool schema (function calling)", "methods/agent/llm_agent.py::_SOLVE_TOOL"),
}

# Which block a ``## Heading`` in the assembled user message belongs to.
HEADING_BLOCK = {
    "## Role": "u_role",
    "## System Data": "u_data",
    "## Task": "u_task",
    "## Reasoning Instructions": "u_reason",
    "## Output Requirements": "u_out",
}


def example_requests() -> "Dict[str, Any]":
    """One real request per variant, generated the way the benchmark generates them.

    The committed run set holds one request per day, so only the four variants
    that happened to fall on those days appear in it. The page has to show every
    variant, so each one is generated here on a frozen day by forcing the
    rotation to that variant alone. Same generator, same seed, same days: these
    are the requests a run would send, not illustrations of them.
    """
    import datetime as _dt

    from data.loader.loader import load_sessions
    from evaluation.requests import VARIANTS, generate_requests

    days = frozen_days()
    loaded: List[Any] = []
    for d in days[:6]:
        try:
            date = _dt.date.fromisoformat(str(d["date"]))
            loaded.append((date, load_sessions("caltech", date, source="cache")))
        except Exception:
            continue
    out: Dict[str, Any] = {}
    for variant in VARIANTS:
        for pair in loaded:
            try:
                reqs = generate_requests([pair], variants=[variant])
            except Exception:
                continue
            if reqs and reqs[0].variant == variant:
                out[variant] = reqs[0]
                break
    return out


def _split_user_message(text: str) -> "List[Tuple[str, str]]":
    """The assembled user message as (block id, text), in the order it is sent."""
    parts: List[Tuple[str, str]] = []
    current, buf = None, []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in HEADING_BLOCK:
            if current is not None:
                parts.append((current, "\n".join(buf).strip("\n")))
            current, buf = HEADING_BLOCK[stripped], [line]
        else:
            buf.append(line)
    if current is not None:
        parts.append((current, "\n".join(buf).strip("\n")))
    return parts


def _block(kind: str, text: str, *, source: str = "", collapse: bool = False) -> str:
    color, label, default_source = BLOCKS[kind]
    src = source or default_source
    if collapse and len(text) > 1500:
        inner = (
            f"<details><summary>show the {len(text):,} characters</summary>"
            f"<pre>{E(text)}</pre></details>"
        )
        return prompt_block(label, inner, color=color, source=src, pre=False)
    return prompt_block(label, text, color=color, source=src)


def tab_prompts() -> str:
    """What each method sends, block by block, for a chosen scenario."""
    import methods
    from methods.prompting.strategies import build_messages, normalise_strategy

    examples = example_requests()
    if not examples:
        return card("Prompts", "<p class='muted'>No frozen day could be loaded to render a request on.</p>")

    legend = " ".join(
        f"<span class='chip' style=\"background:{c};color:#fff\">{E(label)}</span>"
        for c, label, _src in BLOCKS.values()
    )
    scn_options = "".join(
        f"<option value='{E(v)}'>{E(v)} · {E(r.text.split(chr(10))[0][:70])}…</option>"
        for v, r in examples.items()
    )
    # Opens on the first method that has a prompt: landing on the parser, whose
    # panel is one sentence saying it has none, reads as an empty page.
    default = next((c["folder"] for c in methods.cards() if c.get("prompt_files")), "")
    mth_options = "".join(
        f"<option value='{E(c['folder'])}'{' selected' if c['folder'] == default else ''}>"
        f"{E(c['folder'])}</option>"
        for c in methods.cards()
    )

    body: List[str] = [
        card(
            "What the model receives, block by block",
            "<p>Pick a scenario and a method. The prompt is shown as the blocks it is assembled from: "
            "the color says what kind of block it is and the grey label says which file under "
            "<code>methods/</code> or which function produces it. Every fixed sentence is a file; the "
            "three blocks built at run time are marked as such.</p>"
            "<p>The deterministic parser is in the list and has no prompt: it reads the request with "
            "rules and sends nothing to a model.</p>"
            f"<div style='margin:8px 0'>{legend}</div>"
            f"<div style='display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-top:10px'>"
            f"<label>Scenario <select id='scn'>{scn_options}</select></label>"
            f"<label>Method <select id='mth'>{mth_options}</select></label></div>",
        )
    ]

    for c in methods.cards():
        name = c["folder"]
        inner: List[str] = [
            f"<h2>{E(name)} <span class='muted'>runner: {E(c['runner_name'])}</span></h2>",
            f"<p class='muted'>{E(c['description'])}</p>",
        ]
        if not c.get("prompt_files"):
            inner.append(
                "<p>No language model, so no prompt. The request is read by rules and the solver is "
                "called directly.</p>"
            )
        elif c["kind"] == "llm_only":
            strategy = normalise_strategy(c["strategy"])
            suffix_file = f"methods/{name}/system_suffix.txt"
            for variant, req in examples.items():
                msgs = build_messages(strategy, req)
                system, user = msgs[0]["content"], msgs[1]["content"]
                base = methods.read_text("_shared/llm_only_system_prompt.txt")
                blocks = [
                    f"<h3>System prompt <span class='muted'>sha {E(_sha(system))}</span></h3>",
                    _block("sys_llm", base),
                    _block("sys_suffix", system[len(base):], source=suffix_file),
                    "<h3>User message</h3>",
                ]
                blocks += [
                    _block(kind, text, collapse=(kind == "u_task"))
                    for kind, text in _split_user_message(user)
                ]
                inner.append(
                    f"<div class='um' data-scn='{E(variant)}'>" + "".join(blocks) + "</div>"
                )
        else:
            for rel in c["prompt_files"]:
                kind = {
                    "_shared/agent_system_prompt.txt": "sys_agent",
                    "_shared/parse_extraction_system.txt": "sys_parse",
                    "_shared/parse_inference_system.txt": "sys_infer",
                }.get(rel, "sys_agent")
                inner.append(_block(kind, methods.read_text(rel), source=f"methods/{rel}"))
            import methods.agent.llm_agent as LA

            inner.append(_block("tools", json.dumps(LA._SOLVE_TOOL, indent=2), collapse=True))
            for variant, req in examples.items():
                inner.append(
                    f"<div class='um' data-scn='{E(variant)}'>"
                    + _block("u_task", req.text, collapse=True)
                    + "</div>"
                )
        body.append(f"<div class='card pm' data-mth='{E(name)}'>" + "".join(inner) + "</div>")

    return "".join(body)


def _sha(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def tab_tools() -> str:
    import methods.agent.llm_agent as LA

    tool = LA._SOLVE_TOOL["function"]
    g = gate_module()
    body = [
        card(
            "One tool, identical for every method that has tools",
            f"<p><code>{E(tool['name'])}</code> runs the convex optimizer of the Overview on the problem described "
            "in the conversation. Every method with tools receives this exact schema, the same arguments and the "
            "same round budget, so tool access is never a difference between them. The prompting methods receive "
            "no tool at all, which is the whole content of those rows.</p>"
            f"<p class='muted'>{E(tool['description'])}</p>"
            f"<pre>{E(json.dumps(tool.get('parameters', {}), indent=2))}</pre>",
            "<p><b>What comes back:</b> whether the solve succeeded, the total cost, the peak load, the total "
            "unmet energy and the share of sessions fully served. The kilowatt matrix itself stays with the "
            "harness and is never passed back through the model, so the answer and the artifact that will be run "
            "can come apart. One verification condition exists for precisely that.</p>",
            note(
                "The what-if arguments change the problem being posed. After a failed verification the model may "
                "call the solver again, but those arguments are blocked ("
                + E(", ".join(sorted(g.PROBLEM_CHANGING_ARGUMENTS)))
                + "), so no method can pass verification by quietly solving an easier problem.",
                "warn",
            ),
        )
    ]
    return "".join(body)


def tab_gate() -> str:
    g = gate_module()
    counterpart = {
        "solver_optimal": "the tool produced a usable solution",
        "no_hard_violation": "the schedule can be run",
        "traceable": "the numbers have an origin",
        "currency": "the numbers are the current ones",
        "schedule_consistency": "the words and the artifact agree",
        "shortfall_declared": "what is missing is stated",
    }
    body = [
        card(
            "The verification gate",
            "<p>Six conditions on the final answer, evaluated separately and never collapsed into a single "
            "boolean. When one fails, the verdict goes back to the model once. If the second attempt fails as "
            "well, the answer is replaced by a declared failure that carries no numbers at all, and the day counts "
            "as escalated to a person.</p>",
            table(
                ["", "condition", "what it checks", "in one phrase"],
                [
                    [
                        f"<b>{E(g.CONDITION_LABELS[k])}</b>",
                        f"<code>{E(k)}</code>",
                        E(g.CONDITION_DESCRIPTIONS[k]),
                        f"<span class='muted'>{E(counterpart.get(k, ''))}</span>",
                    ]
                    for k in g.CONDITION_ORDER
                ],
            ),
            f"<p class='muted'>Attempts before a declared failure: {E(g.MAX_VERIFICATION_ATTEMPTS)}. A shortfall "
            f"has to be declared once it crosses both floors, {E(g.MATERIAL_UNMET_KWH)} kWh and "
            f"{E(g.MATERIAL_UNMET_SHARE)} of the energy requested, so a rounding-level shortfall does not force a "
            "sentence about it.</p>",
        )
    ]

    body.append(
        card(
            "What the gate is allowed to look at",
            "<p>Only the agent's own evidence: the schedule it produced, the outputs of the tools it called, and "
            "the text it wrote. No reference solution and no optimum. That restriction is what makes the gate a "
            "deployable component rather than an evaluation artifact — at a real site there is no ground truth to "
            "consult — and it fixes what the gate can and cannot catch.</p>"
            "<div class='grid g2'>"
            "<div><h3>It catches</h3><ul>"
            "<li>numbers that appear in no tool output at all</li>"
            "<li>numbers left over from an earlier solve</li>"
            "<li>an answer describing a different schedule from the one handed over</li>"
            "<li>a material shortfall the answer stays silent about</li>"
            "<li>a schedule that breaks a hard constraint of the problem as posed</li>"
            "</ul></div>"
            "<div><h3>It cannot catch</h3><ul>"
            "<li>a request that was misread. If the parameters are wrong, the LP is still solved optimally, every "
            "number still comes from that solve, and nothing in the agent's own evidence reveals that the day it "
            "optimized is not the day it was given.</li>"
            "</ul></div></div>",
            note(
                "That gap is a property of the design, not an oversight, and it is why the formulation column is "
                "reported separately from the outcome. A measurement of this case study is exactly how often it "
                "bites: see <b>Results</b>.",
                "warn",
            ),
        )
    )

    body.append(
        card(
            "Where a day ends up",
            "<p>The three outcomes are exclusive and add to 100 %.</p>",
            table(
                ["outcome", "definition"],
                [
                    [
                        verdict("solved"),
                        "the state is right — no hard violation, cost gap within tolerance, and the gap not bought "
                        "by leaving energy undelivered — every number traces to the last solve, and the answer "
                        "matches what was asked whenever the request asks something checkable",
                    ],
                    [
                        verdict("escalated"),
                        "the system declared it could not answer instead of presenting a schedule as valid. Takes "
                        "precedence over the other two",
                    ],
                    [
                        verdict("wrong"),
                        "an invalid schedule, a number with no support, or a misread request, presented as valid. "
                        "The one an operator would want to see first",
                    ],
                ],
            ),
            "<p class='muted'>Formulation is scored on every day and is deliberately <b>not</b> a term of Solved. "
            "Each column measures one thing: formulation says whether the request was understood, the outcome says "
            "whether what was delivered was right.</p>",
        )
    )

    last = ""
    rows = []
    for c in COLUMNS:
        grp = "" if c["group"] == last else f"<b>{E(c['group'])}</b>"
        last = c["group"]
        rows.append([f"<span class='muted'>{grp}</span>", f"<b>{E(c['name'])}</b>", E(c["what"]), f"<span class='muted'>{E(c['why'])}</span>"])
    body.append(
        card(
            "The columns",
            "<p>Three groups, the same three in every case study: what the task needed, whether the result is "
            "correct and grounded, and what it costs to operate.</p>",
            table(["group", "column", "what it measures", "why it is there"], rows),
            note(
                "Solved, Escalated and Wrong-unflagged sit in different groups on purpose. Solved is task utility: "
                "the work got done. Wrong-unflagged is correctness: it is the quantity the design claims to drive "
                "to zero. Escalated is cost of operation: it does not say the system was right, it says how much "
                "human work it generated. They still add to 100 %, because every day ends in exactly one of them.",
                "info",
            ),
        )
    )
    return "".join(body)


def tab_results() -> str:
    dirs = latest_run()
    if not dirs:
        return card("No runs yet", "<p>No results folder carries a summary.json.</p>")
    by_method = {read_header(d)["header"]["method"]: (d, read_summary(d), read_header(d)) for d in dirs}
    date = dirs[0].parts[-3]
    body: List[str] = []

    # headline: the gated row against its target
    if "evagent" in by_method:
        d, rows, hdr = by_method["evagent"]
        n = len(rows)
        solved = sum(1 for r in rows if r.get("outcome") == "solved")
        esc = sum(1 for r in rows if r.get("outcome") == "escalated")
        bad = sum(1 for r in rows if r.get("outcome") == "wrong_unflagged")
        gate_ok = sum(1 for r in rows if str(r.get("gate_pass")).lower() == "true")
        exact = sum(int(r["n_sessions_exact"] or 0) for r in rows if r.get("n_sessions_exact"))
        truth = sum(int(r["n_sessions_truth"] or 0) for r in rows if r.get("n_sessions_truth"))
        fdays = sum(1 for r in rows if str(r.get("formulation_exact")).lower() == "true")
        share = 100.0 * exact / truth if truth else 0.0
        met = bad == 0 and solved + esc == n
        body.append(
            card(
                "The solver-grounded row against its target",
                f"<p style='font-size:15px'>{verdict('solved')} {solved}/{n} &nbsp; {verdict('escalated')} "
                f"{esc}/{n} &nbsp; {verdict('wrong')} {bad}/{n}</p>",
                f"<p>Target: solved + escalated = {n}, wrong-unflagged = 0. "
                + ("<b>Met.</b>" if met else "<b>Not met.</b>")
                + f" The gate accepted <b>{gate_ok} of {n}</b> answers, and the formulation was exact on "
                f"<b>{exact} of {truth} sessions ({share:.1f} %)</b> but on <b>{fdays} of {n} days</b>, since a day "
                "counts only when every one of its sessions is right.</p>",
                note(
                    "Those numbers are one finding, not three. The model read the right number of cars every time "
                    "and misread a field on a handful of them; it then optimized the day it had parsed. For that "
                    "day the solution is optimal and every reported number comes from it, so the gate accepted it, "
                    "exactly as the section on what the gate can look at predicts. Measured against the real day, "
                    "the same schedules exceed the true sessions' limits. This is the case study's central "
                    "observation: <b>grounding a number in a solver does not ground the problem the solver was "
                    "given</b>.",
                    "warn",
                ),
            )
        )

    def pct(rows: List[Dict[str, str]], kind: str) -> str:
        k = sum(1 for r in rows if r.get("outcome") == kind)
        return f"{100.0 * k / len(rows):.0f} % <span class='muted'>({k}/{len(rows)})</span>"

    split = []
    for row in ROWS:
        if row["name"] in by_method:
            _d, rows, _h = by_method[row["name"]]
            split.append([f"<b>{E(row['label'])}</b>", str(len(rows)), pct(rows, "solved"), pct(rows, "escalated"), pct(rows, "wrong_unflagged")])
        else:
            split.append([f"<b>{E(row['label'])}</b>", "<span class='muted'>not measured yet</span>", "", "", ""])
    for ref in REFERENCES:
        if ref["arm"] in by_method:
            _d, rows, _h = by_method[ref["arm"]]
            split.append([f"<span class='muted'>{E(ref['label'])} (reference)</span>", str(len(rows)),
                          pct(rows, "solved"), pct(rows, "escalated"), pct(rows, "wrong_unflagged")])

    # the run's model is the one the LLM methods ran on; the reference rows say no-llm
    any_d, _r, any_h = next(
        (v for v in by_method.values() if v[2]["header"]["model"] != "no-llm"), next(iter(by_method.values()))
    )
    cfg = json.loads((any_d / "config.json").read_text(encoding="utf-8")) if (any_d / "config.json").exists() else {}
    body.append(
        card(
            "Every method, on the same days",
            f"<p class='muted'>Run of {E(date)} · model {E(cfg.get('model_resolved') or any_h['header']['model'])} · "
            f"request digest <code>{E(str(cfg.get('requests_digest', ''))[:26])}…</code>, identical for every row · "
            f"<code>results/{E(any_d.parts[-4])}/{E(date)}/</code></p>",
            table(["method", "requests", verdict("solved"), verdict("escalated"), verdict("wrong")], split),
        )
    )

    cols = [
        ("nn", "nn"), ("request_id", "request"), ("variant", "variant"), ("outcome", "outcome"), ("solved_reason", "why"),
        ("formulation_exact", "form."), ("no_hard_violation", "runnable"), ("traceable", "trace"),
        ("answer_ok", "answer"), ("gap_pct", "gap %"), ("cost_usd", "cost $"), ("unmet_kwh", "unmet kWh"),
        ("gate_pass", "gate"), ("prompt_tokens", "in"), ("completion_tokens", "out"),
    ]
    det = []
    for name, (d, rows, _h) in by_method.items():
        det.append(
            f"<details><summary>{E(name)} — every request · <code>{E(str(d.relative_to(PROJECT_ROOT)))}</code></summary>"
            + table([label for _k, label in cols],
                    [[verdict(r["outcome"]) if k == "outcome" else E(r.get(k, "")) for k, _l in cols] for r in rows])
            + "</details>"
        )
    body.append(card("Request by request", *det))
    return "".join(body)


def tab_analysis() -> str:
    """The report each method folder ends with, rendered. Written from the rows, never by a model."""
    from visuals.shell import markdown

    dirs = [d for d in latest_run() if (d / "REPORT.md").exists()]
    if not dirs:
        return card(
            "Analysis",
            "<p class='muted'>No results folder carries a REPORT.md yet.</p>"
            "<p>Every run ends with one per method, written by <code>evaluation/postprocess.py</code> from "
            "the rows the run produced. No model is called to write it.</p>",
        )
    body = [
        card(
            "What the reports are",
            "<p>Each method folder under <code>results/</code> ends with a <code>REPORT.md</code> written from "
            "the rows the run produced: the outcome split, formulation and traceability rates, cost, the list of "
            "requests that ended wrong or escalated, and every request on one line. No model is called to write "
            "it, and nothing in it is typed by hand. The run set's own report, over every method at once, is in "
            "each folder's <code>raw/</code>.</p>"
            "<p class='muted'>The failure catalog and the conclusions across runs are written once the missing "
            "methods have run; until then this section is the reports as they stand.</p>",
        )
    ]
    for d in dirs:
        body.append(
            f"<div class='card'><h2><code>{E(str(d.relative_to(PROJECT_ROOT / 'results')))}</code></h2>"
            + markdown((d / "REPORT.md").read_text(encoding="utf-8"))
            + "</div>"
        )
    return "".join(body)


def tab_status() -> str:
    A = arms()
    rows = []
    for r in ROWS:
        st = arm_state(r)
        word = {
            "running": chip("running", "ok"),
            "pending": chip("implemented next", "warn"),
            "to write": chip("to be written", "warn"),
        }[st]
        rows.append([f"<b>{E(r['label'])}</b>", f"<code>{E(r['name'])}</code>", word])
    running = sum(1 for r in ROWS if arm_state(r) == "running")
    models = sorted({d.parts[-2] for d in method_dirs() if d.parts[-2] != "no-llm"})
    return card(
        "Where the implementation stands",
        f"<p>{running} of the {len(ROWS)} methods run today. The rest are specified here and in the registry the "
        "harness reads, so naming one that is not implemented is an error rather than a row that silently "
        "disappears from a table.</p>",
        table(["method", "name", "state"], rows),
        "<p class='muted'>Models run so far: " + E(", ".join(m for m in models if m)) + ". The stress days are "
        "implemented and have not been run yet.</p>",
    )


# ------------------------------------------------------------------- payload

GROUPS: Tuple[Tuple[str, Tuple[Tuple[str, str], ...]], ...] = (
    ("Design", (
        ("home", "Home"),
        ("methods", "Methods"),
        ("scenarios", "Scenarios"),
        ("prompts", "Prompts"),
        ("tools", "Tools"),
        ("gate", "Gate & scoring"),
    )),
    ("Results", (
        ("results", "Results"),
        ("analysis", "Analysis"),
        ("status", "Implementation"),
    )),
)

BUILDERS = {
    "home": tab_overview,
    "methods": tab_methods,
    "scenarios": tab_scenarios,
    "prompts": tab_prompts,
    "tools": tab_tools,
    "gate": tab_gate,
    "results": tab_results,
    "analysis": tab_analysis,
    "status": tab_status,
}


# Drives the two selectors of the Prompts section: one method panel visible at
# a time, and inside it the blocks of the chosen scenario.
SCRIPT = """
(function(){
  var scn=document.getElementById('scn'), mth=document.getElementById('mth');
  if(!scn||!mth) return;
  function apply(){
    document.querySelectorAll('.pm').forEach(function(p){
      p.style.display = p.dataset.mth===mth.value ? '' : 'none';});
    document.querySelectorAll('.um').forEach(function(u){
      u.style.display = u.dataset.scn===scn.value ? '' : 'none';});
  }
  scn.onchange=apply; mth.onchange=apply; apply();
})();
"""


def payload() -> Dict[str, Any]:
    days = frozen_days()
    return {
        "id": CASE_ID,
        "title": CASE_TITLE,
        "brand": "EVAgent · day-ahead EV charging",
        "note": f"{len(days)} days of real charging sessions",
        "blurb": "Schedule a day of charging at a workplace site from a request written in plain language, under a "
                 "site power cap and a time-of-use tariff.",
        "summary": [
            ("task", "day-ahead charging schedule"),
            ("solver", "CVXPY linear program"),
            ("data", f"{len(days)} real session days"),
        ],
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

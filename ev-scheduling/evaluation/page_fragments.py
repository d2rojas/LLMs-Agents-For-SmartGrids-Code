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
    flow,
    kv,
    note,
    prompt_block,
    table,
    verdict,
)

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
        "operation any optimisation has to beat, and the denominator of the cost reduction.",
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
    from scripts.run_ev_matrix import ARMS

    return ARMS


def gate_module() -> Any:
    from agent.validate import gate

    return gate


def frozen_days() -> List[Dict[str, Any]]:
    path = PROJECT_ROOT / "data" / "benchmark" / "manifest.json"
    if not path.exists():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")).get("days", []))


def run_dirs() -> List[Path]:
    root = PROJECT_ROOT / "results"
    return [d for d in sorted(root.iterdir()) if (d / "run_manifest.json").exists()] if root.is_dir() else []


def read_rows(d: Path) -> List[Dict[str, str]]:
    f = d / "rows.csv"
    if not f.exists():
        return []
    with f.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def sample_request() -> Optional[Dict[str, Any]]:
    for d in run_dirs():
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
            "parameters of an optimisation problem, solve it under the site's power cap and its time-of-use tariff, "
            "and answer what was actually asked, whether that is the schedule itself or a question about it. Today "
            "that somebody is an engineer with a convex solver. This case study asks what happens when it is a "
            "language model.</p>",
            flow([
                ("Request", "free text, one per day and variant"),
                ("Formulate", "four parameters per session"),
                ("Compute", "the LP, or the model writing kW by hand"),
                ("Report", "the schedule, or the answer asked for"),
                ("Verdict", "solved · escalated · wrong"),
            ]),
            "<p class='muted'>Six methods answer the identical requests, on identical days, under an identical "
            "budget, and are scored by identical code. One of them uses no language model at all; the other five "
            "differ from each other by exactly one factor at a time.</p>",
        )
    ]

    body.append(
        card(
            "The problem, formally",
            "<p>The day is discretised into <em>T</em> steps of Δ hours. Session <em>i</em> occupies a charger "
            "from step <em>a<sub>i</sub></em> to step <em>d<sub>i</sub></em>, asks for <em>E<sub>i</sub></em> kWh, "
            "and its charger delivers at most <em>p̄<sub>i</sub></em> kW. The site cannot draw more than "
            "<em>P<sub>max</sub></em>(<em>t</em>) at any step, and energy at step <em>t</em> costs "
            "<em>c</em>(<em>t</em>) per kWh.</p>",
            "<div class='math'>"
            "<span class='lbl'>decision variables</span>"
            "<span class='eq'><em>p<sub>i</sub></em>(<em>t</em>) ≥ 0 &nbsp; power to session <em>i</em> at step "
            "<em>t</em>, in kW &nbsp;&nbsp;·&nbsp;&nbsp; <em>u<sub>i</sub></em> ≥ 0 &nbsp; energy not delivered to "
            "session <em>i</em>, in kWh</span>"
            "<span class='lbl'>objective</span>"
            "<span class='eq'>min &nbsp; Σ<sub><em>t</em></sub> <em>c</em>(<em>t</em>) · "
            "( Σ<sub><em>i</em></sub> <em>p<sub>i</sub></em>(<em>t</em>) ) · Δ &nbsp; + &nbsp; "
            "<em>M</em> · Σ<sub><em>i</em></sub> <em>u<sub>i</sub></em></span>"
            "<span class='lbl'>subject to</span>"
            "<span class='eq'>(1) &nbsp; <em>p<sub>i</sub></em>(<em>t</em>) = 0 &nbsp;&nbsp; for <em>t</em> ∉ "
            "[<em>a<sub>i</sub></em>, <em>d<sub>i</sub></em>) &nbsp;&nbsp;&nbsp; <span class='lbl' "
            "style='display:inline'>the car is not plugged in</span></span>"
            "<span class='eq'>(2) &nbsp; 0 ≤ <em>p<sub>i</sub></em>(<em>t</em>) ≤ <em>p̄<sub>i</sub></em> "
            "&nbsp;&nbsp;&nbsp; <span class='lbl' style='display:inline'>the charger's limit</span></span>"
            "<span class='eq'>(3) &nbsp; Σ<sub><em>i</em></sub> <em>p<sub>i</sub></em>(<em>t</em>) ≤ "
            "<em>P<sub>max</sub></em>(<em>t</em>) &nbsp;&nbsp; for every <em>t</em> &nbsp;&nbsp;&nbsp; "
            "<span class='lbl' style='display:inline'>the site's cap</span></span>"
            "<span class='eq'>(4) &nbsp; Δ · Σ<sub><em>t</em></sub> <em>p<sub>i</sub></em>(<em>t</em>) + "
            "<em>u<sub>i</sub></em> = <em>E<sub>i</sub></em> &nbsp;&nbsp;&nbsp; <span class='lbl' "
            "style='display:inline'>deliver the energy, or account for what is missing</span></span>"
            "</div>",
            "<p>Constraints (1) to (3) are <b>hard</b>: a schedule that breaks one of them cannot be run, and the "
            "site would trip or the car would draw power it cannot take. Constraint (4) is <b>soft</b>, through the "
            "slack <em>u<sub>i</sub></em> priced at <em>M</em> = 10<sup>6</sup> $/kWh. That is a deliberate "
            "modelling choice with a consequence the evaluation has to handle: the problem is <b>always feasible</b>, "
            "because undelivered energy is expensive rather than forbidden. A day the site genuinely cannot serve "
            "does not produce an infeasible solve; it produces an optimal one with a large "
            "Σ<em>u<sub>i</sub></em>, which somebody has to notice and say out loud.</p>",
            "<h3>What is reported from a solution</h3>"
            "<div class='math'>"
            "<span class='eq'>cost &nbsp; = &nbsp; Σ<sub><em>t</em></sub> <em>c</em>(<em>t</em>) · "
            "( Σ<sub><em>i</em></sub> <em>p<sub>i</sub></em>(<em>t</em>) ) · Δ</span>"
            "<span class='eq'>peak &nbsp; = &nbsp; max<sub><em>t</em></sub> Σ<sub><em>i</em></sub> "
            "<em>p<sub>i</sub></em>(<em>t</em>)</span>"
            "<span class='eq'>unmet &nbsp; = &nbsp; Σ<sub><em>i</em></sub> <em>u<sub>i</sub></em></span>"
            "<span class='eq'>gap &nbsp; = &nbsp; ( cost − cost* ) / cost*, &nbsp; with cost* the optimum of the "
            "same day</span>"
            "</div>"
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
            "<p>The set is fixed across the case studies, so the tables can be read side by side. Three methods a "
            "reader might expect are deliberately outside it:</p>"
            "<ul>"
            "<li><b>A human with the solver.</b> The workload everything here is trying to remove. It is measured "
            "by timing, not by running code, and it belongs next to the table rather than inside it.</li>"
            "<li><b>Few-shot and retrieval-augmented prompting.</b> Covered in full in the prompting appendix, "
            "which compares prompting strategies among themselves. The body compares architectures, and two "
            "prompting rows are enough to show what a prompt alone can and cannot do.</li>"
            "<li><b>A single tool call with no iteration.</b> Plan-and-Act already isolates solver access without "
            "feedback: its plan is emitted before any result is seen. A separate row would differ from it by "
            "almost nothing.</li>"
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

    body.append(
        card(
            "The requests",
            "<p>One request per day and variant, generated as free text rather than filled into a template: times "
            "spelled out in words, energies given in Wh or kWh, power in W or kW, and several sentence shapes per "
            "session. Reading the request is half of the task being measured, so the text has to be worth "
            "reading.</p>"
            "<p>The list is generated once, hashed, and the digest is recorded on every result row, so any table "
            "built from those rows can be shown to have asked every method the same thing.</p>",
            table(
                ["variant", "what the answer has to be", "note"],
                [
                    [
                        f"<code>{E(v)}</code>",
                        E(R.ANSWER_KIND_BY_VARIANT.get(v, "")),
                        "<span class='muted'>"
                        + E(
                            "the schedule itself is the answer"
                            if v in R.STATE_VARIANTS
                            else "the answer has to state undelivered energy"
                            if v in R.SHORTFALL_VARIANTS
                            else ""
                        )
                        + "</span>",
                    ]
                    for v in R.VARIANTS
                ],
            ),
            f"<p class='muted'>Site cap {R.SITE_CAP_KW:g} kW. Time-of-use tariff: ${R.PEAK_PRICE:.2f} per kWh "
            f"between {R.PEAK_START_HOUR}:00 and {R.PEAK_END_HOUR}:00, ${R.OFF_PEAK_PRICE:.2f} otherwise.</p>",
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


def tab_prompts() -> str:
    from baseline.strategies import STRATEGIES, build_messages, prompt_sections

    colours = {
        "## Role": "#6d4fc4",
        "## System Data": "#0f8f84",
        "## Task": "#2f5fd0",
        "## Reasoning Instructions": "#c0392b",
        "## Output Requirements": "#c99a06",
    }
    shared = set(prompt_sections(STRATEGIES[0]))
    rows = []
    for s in STRATEGIES:
        cells = " ".join(
            f"<span class='chip' style=\"background:{colours.get(sec, '#eef1f5')};color:#fff\">{E(sec)}</span>"
            if sec not in shared
            else f"<span class='chip'>{E(sec)}</span>"
            for sec in prompt_sections(s)
        )
        rows.append([f"<code>{E(s)}</code>", cells])

    body = [
        card(
            "The prompts, as a run would send them",
            "<p>Rendered by calling the same builders the benchmark calls, on a real request. Nothing below is a "
            "copy of a prompt kept in sync by hand.</p>",
            table(["strategy", "sections, in order"], rows),
            note(
                "The two prompting methods differ by one section and nothing else. That is what makes them a "
                "controlled comparison rather than two prompts that happen to differ, and it is checkable here "
                "rather than asserted in prose.",
                "info",
            ),
        )
    ]

    req = sample_request()
    if req is None:
        return "".join(body)
    try:
        from evaluation.requests import request_from_dict

        obj = request_from_dict(req)
    except Exception:
        return "".join(body)

    body.append(
        card(
            "The request these prompts carry",
            f"<p class='muted'>variant <code>{E(req.get('variant'))}</code> · day {E(req.get('date'))} · "
            f"{E(len(req.get('day', {}).get('sessions', [])))} sessions</p>"
            f"<pre>{E(req.get('text', ''))[:4000]}</pre>",
        )
    )
    for s in STRATEGIES:
        try:
            msgs = build_messages(s, obj)
        except Exception:
            continue
        blocks = []
        for m in msgs:
            content = m["content"]
            if m["role"] == "system":
                blocks.append(
                    prompt_block("system", content, colour="#334155", source="baseline/strategies.py::system_prompt")
                )
                continue
            # split the user message on its own section headings, so each part
            # is shown in the colour the table above gave it
            parts: List[Tuple[str, str]] = []
            current, buf = "(preamble)", []
            for line in content.splitlines():
                if line.strip().startswith("## "):
                    if buf:
                        parts.append((current, "\n".join(buf)))
                    current, buf = line.strip(), []
                else:
                    buf.append(line)
            if buf:
                parts.append((current, "\n".join(buf)))
            for label, text in parts:
                blocks.append(
                    prompt_block(
                        label,
                        text,
                        colour=colours.get(label, "#94a3b8"),
                        source="baseline/strategies.py::build_messages",
                    )
                )
        body.append(card(f"{s}", "".join(blocks)))
    return "".join(body)


def tab_tools() -> str:
    import agent.llm_agent as LA

    tool = LA._SOLVE_TOOL["function"]
    g = gate_module()
    body = [
        card(
            "One tool, identical for every method that has tools",
            f"<p><code>{E(tool['name'])}</code> runs the convex optimiser of the Overview on the problem described "
            "in the conversation. Every method with tools receives this exact schema, the same arguments and the "
            "same round budget, so tool access is never a difference between them. The prompting methods receive "
            "no tool at all, which is the whole content of those rows.</p>"
            f"<p class='muted'>{E(tool['description'])}</p>"
            f"<pre>{E(json.dumps(tool.get('parameters', {}), indent=2))}</pre>",
            "<p><b>What comes back:</b> whether the solve succeeded, the total cost, the peak load, the total "
            "unmet energy and the share of sessions fully served. The kilowatt matrix itself stays with the "
            "harness and is never passed back through the model, so the answer and the artefact that will be run "
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
        "schedule_consistency": "the words and the artefact agree",
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
            "deployable component rather than an evaluation artefact — at a real site there is no ground truth to "
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
            "optimised is not the day it was given.</li>"
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
    dirs = run_dirs()
    if not dirs:
        return card("No runs yet", "<p>No results directory carries a run manifest.</p>")

    latest = dirs[-1]
    man = json.loads((latest / "run_manifest.json").read_text(encoding="utf-8"))
    rows = read_rows(latest)
    by_arm: Dict[str, List[Dict[str, str]]] = {}
    for r in rows:
        by_arm.setdefault(r.get("arm", "?"), []).append(r)

    body: List[str] = []

    # headline: the gated row against its target
    ev = by_arm.get("evagent", [])
    if ev:
        n = len(ev)
        solved = sum(1 for r in ev if r.get("outcome") == "solved")
        esc = sum(1 for r in ev if r.get("outcome") == "escalated")
        bad = sum(1 for r in ev if r.get("outcome") == "wrong_unflagged")
        gate_ok = sum(1 for r in ev if str(r.get("gate_passed")).lower() == "true")
        exact = sum(int(r["n_sessions_exact"] or 0) for r in ev if r.get("n_sessions_exact"))
        truth = sum(int(r["n_sessions_truth"] or 0) for r in ev if r.get("n_sessions_truth"))
        fdays = sum(1 for r in ev if r.get("formulation_status") == "pass")
        share = 100.0 * exact / truth if truth else 0.0
        met = bad == 0 and solved + esc == n
        body.append(
            card(
                "The solver-grounded row against its target",
                f"<p style='font-size:15px'>{verdict('solved')} {solved}/{n} &nbsp; {verdict('escalated')} "
                f"{esc}/{n} &nbsp; {verdict('wrong')} {bad}/{n}</p>",
                f"<p>Target: solved + escalated = {n}, wrong-unflagged = 0. "
                + ("<b>Met.</b>" if met else f"<b>Not met.</b>")
                + f" The gate accepted <b>{gate_ok} of {n}</b> answers, and the formulation was exact on "
                f"<b>{exact} of {truth} sessions ({share:.1f} %)</b> but on <b>{fdays} of {n} days</b>, since a day "
                "counts only when every one of its sessions is right.</p>",
                note(
                    "Those numbers are one finding, not three. The model read the right number of cars every time "
                    "and misread a field on a handful of them; it then optimised the day it had parsed. For that "
                    "day the solution is optimal and every reported number comes from it, so the gate accepted it, "
                    "exactly as the section on what the gate can look at predicts. Measured against the real day, "
                    "the same schedules exceed the true sessions' limits. This is the case study's central "
                    "observation: <b>grounding a number in a solver does not ground the problem the solver was "
                    "given</b>.",
                    "warn",
                ),
            )
        )

    # outcome split per arm
    split = []
    for row in ROWS:
        rs = by_arm.get(row["arm"], []) if row["arm"] else []
        if not rs:
            split.append([f"<b>{E(row['label'])}</b>", "<span class='muted'>not measured yet</span>", "", "", ""])
            continue
        n = len(rs)
        def pct(kind: str) -> str:
            k = sum(1 for r in rs if r.get("outcome") == kind)
            return f"{100.0 * k / n:.0f} % <span class='muted'>({k}/{n})</span>"
        split.append([f"<b>{E(row['label'])}</b>", str(n), pct("solved"), pct("escalated"), pct("wrong_unflagged")])
    for ref in REFERENCES:
        rs = by_arm.get(ref["arm"], [])
        if rs:
            n = len(rs)
            def pct2(kind: str) -> str:
                k = sum(1 for r in rs if r.get("outcome") == kind)
                return f"{100.0 * k / n:.0f} % <span class='muted'>({k}/{n})</span>"
            split.append([
                f"<span class='muted'>{E(ref['label'])} (reference)</span>", str(n),
                pct2("solved"), pct2("escalated"), pct2("wrong_unflagged"),
            ])

    body.append(
        card(
            "Every method, on the same days",
            f"<p class='muted'>Model {E(man.get('model_resolved') or man.get('model_requested'))} · "
            f"{E(man.get('days'))} days · request digest "
            f"<code>{E(str(man.get('requests_digest', ''))[:26])}…</code>, identical for every row.</p>",
            table(["method", "days", verdict("solved"), verdict("escalated"), verdict("wrong")], split),
        )
    )

    # per-day detail
    cols = [
        ("date", "day"), ("variant", "variant"), ("outcome", "outcome"), ("outcome_reason", "why"),
        ("formulation_status", "form."), ("state_status", "state"), ("traceability_status", "trace"),
        ("answer_status", "answer"), ("gap_pct", "gap %"), ("cost_usd", "cost $"),
        ("unmet_kwh", "unmet kWh"), ("peak_kw", "peak kW"), ("total_tokens", "tokens"),
    ]
    det = []
    for arm, rs in by_arm.items():
        body_rows = [
            [verdict(r["outcome"]) if k == "outcome" else E(r.get(k, "")) for k, _ in cols]
            for r in sorted(rs, key=lambda x: str(x.get("date")))
        ]
        det.append(
            f"<details><summary>{E(arm)} — every day</summary>"
            + table([label for _, label in cols], body_rows)
            + "</details>"
        )
    body.append(card("Day by day", *det))
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
    dirs = run_dirs()
    models = sorted({
        json.loads((d / "run_manifest.json").read_text(encoding="utf-8")).get("model_resolved")
        or json.loads((d / "run_manifest.json").read_text(encoding="utf-8")).get("model_requested")
        for d in dirs
    })
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
        ("overview", "The task"),
        ("methods", "Methods"),
        ("scenarios", "Scenarios"),
        ("prompts", "Prompts"),
        ("tools", "Tool"),
        ("gate", "Gate & scoring"),
    )),
    ("Results", (
        ("results", "Results"),
        ("status", "Implementation"),
    )),
)

BUILDERS = {
    "overview": tab_overview,
    "methods": tab_methods,
    "scenarios": tab_scenarios,
    "prompts": tab_prompts,
    "tools": tab_tools,
    "gate": tab_gate,
    "results": tab_results,
    "status": tab_status,
}


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
    }


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "results" / "visuals" / "fragments.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload()), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

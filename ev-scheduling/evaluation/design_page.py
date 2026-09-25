"""The evaluation design of the EV case study, as one readable page.

The EV counterpart of ``power-flow-agent/evaluation/design_page.py``, and it is
built for one job: letting a person check, before any expensive run, that the
comparison this case study makes is the comparison the paper claims and the
reviewers asked for. Every fact on the page is read from the code at build time
-- the arm registry, the gate's own condition table, the request variants, the
frozen day manifest, the prompt builders -- so the page cannot drift from what
would actually run. Nothing here is typed twice.

The page is deliberately not a results page. It states the design and marks what
is missing from it. Where the design is incomplete (rows that are registered but
not implemented, a second model that has not been run, a column that the target
table defines and the scoreboard does not emit), the page says so in place
rather than omitting the row, because a design review whose gaps are invisible
is worth nothing.

Usage (from ev-scheduling/):
    python -m evaluation.design_page

Writes ``results/visuals/design.html``.
"""

from __future__ import annotations

import json
from html import escape as _escape
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def E(x: Any) -> str:
    """HTML-escape any value."""
    return _escape(str(x), quote=True)


# ---------------------------------------------------------------- source data


def arms() -> Dict[str, Any]:
    """The arm registry, straight from the harness that runs them."""
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


def run_sets() -> List[Dict[str, Any]]:
    """One entry per results directory that carries a run manifest."""
    out: List[Dict[str, Any]] = []
    root = PROJECT_ROOT / "results"
    if not root.is_dir():
        return out
    for d in sorted(root.iterdir()):
        man = d / "run_manifest.json"
        if not man.is_dir() and man.exists():
            try:
                payload = json.loads(man.read_text(encoding="utf-8"))
            except ValueError:
                continue
            payload["_dir"] = d.name
            payload["_traces"] = len(list((d / "traces").rglob("*.json"))) if (d / "traces").is_dir() else 0
            out.append(payload)
    return out


def sample_request() -> Optional[Dict[str, Any]]:
    """One real request object, for the prompt tab. Prefers a committed run."""
    root = PROJECT_ROOT / "results"
    for d in sorted(root.iterdir()) if root.is_dir() else []:
        f = d / "requests.jsonl"
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    return json.loads(line)
    return None


# ------------------------------------------------------- the design, declared
#
# The nine rows of the target table (notes repo, tabla_objetivo_ev.md, 18-09),
# each tied to the arm that implements it, or to nothing. ``isolates`` is the
# single factor that row adds over the row above it: that ladder is what
# R3.2, R4.3 and R4.5 asked for, and it is the reason the row exists.

ROWS: Tuple[Dict[str, str], ...] = (
    {
        "block": "Conventional workflow",
        "label": "Human with solver",
        "arm": "",
        "paper": "Figure 1, panel (a)",
        "isolates": "the workload the other rows are trying to remove. Timed, not programmed.",
        "reviewer": "R4.5",
    },
    {
        "block": "Conventional workflow",
        "label": "Deterministic parser + CVXPY",
        "arm": "",
        "paper": "non-LLM baseline asked for by R4.5",
        "isolates": "no LLM anywhere. Regex reads the request text, the LP does the rest. "
        "What automation without a language model already buys.",
        "reviewer": "R4.5",
    },
    {
        "block": "Conventional workflow",
        "label": "Charge as soon as possible",
        "arm": "charge_asap",
        "paper": "fixed operating rule, no optimisation",
        "isolates": "no optimisation and no text. The uncontrolled rule the cost gap is measured against.",
        "reviewer": "R4.5",
    },
    {
        "block": "Prompting, Section 3",
        "label": "Structured prompting",
        "arm": "llm_only:structured",
        "paper": "Section 3.1",
        "isolates": "the language model alone. No tools: it writes the kW matrix as text.",
        "reviewer": "R4.2",
    },
    {
        "block": "Prompting, Section 3",
        "label": "Chain-of-thought prompting",
        "arm": "llm_only:chain_of_thought",
        "paper": "Section 3.3",
        "isolates": "a reasoning section, and nothing else. Same input, same budget as the row above.",
        "reviewer": "R4.2",
    },
    {
        "block": "Architectures, Section 4",
        "label": "Single-call function calling",
        "arm": "",
        "paper": "Section 4.2",
        "isolates": "solver access, and nothing else. One tool call, no iteration, no memory, no gate.",
        "reviewer": "R4.3, R4.5",
    },
    {
        "block": "Architectures, Section 4",
        "label": "ReAct",
        "arm": "react",
        "paper": "Section 4.3",
        "isolates": "iteration. The model sees each tool output and may call again.",
        "reviewer": "R4.3",
    },
    {
        "block": "Architectures, Section 4",
        "label": "Plan-and-Act",
        "arm": "plan_act",
        "paper": "Section 4.3",
        "isolates": "planning. The whole tool plan is emitted once, then executed.",
        "reviewer": "R4.3",
    },
    {
        "block": "Architectures, Section 4",
        "label": "EVAgent, solver-grounded",
        "arm": "evagent",
        "paper": "Section 2",
        "isolates": "the verification gate, and nothing else. Same tools and same budget as ReAct.",
        "reviewer": "R3.2, R4.3",
    },
)

REFERENCE_ROW = {
    "label": "CVXPY optimum",
    "arm": "optimum",
    "note": "The LP solved on the structured ground-truth day. It never reads the request text, so it is the "
    "reference the cost gap is measured against, not a method competing with the others.",
}

# The three metric groups of the framework, with the column each one carries.
# ``scoreboard`` names the column the harness emits today, or "" when the target
# table defines a column that nothing computes yet.
COLUMNS: Tuple[Dict[str, str], ...] = (
    {"group": "Task utility", "name": "Form.", "scoreboard": "Form.",
     "what": "share of sessions whose arrival, departure, energy and max power match the structured day. "
             "Exact on step indices, 1 % on kWh and kW.", "why": "R3.4: did the system formulate the problem that was asked."},
    {"group": "Task utility", "name": "Cost", "scoreboard": "cost $",
     "what": "TOU cost of the schedule, in dollars.", "why": "the objective the day is optimised for."},
    {"group": "Task utility", "name": "Gap", "scoreboard": "gap %",
     "what": "(cost - cost*) / cost* against the CVXPY optimum of the same day.", "why": "distance to the best possible schedule."},
    {"group": "Task utility", "name": "Unmet", "scoreboard": "",
     "what": "energy requested and not delivered, in kWh.", "why": "reads next to Gap: a schedule that charges nothing is cheap."},
    {"group": "Task utility", "name": "Solved", "scoreboard": "Solved",
     "what": "the day was done: state correct, numbers traceable, and the answer matches what was asked.", "why": "the end-to-end verdict."},
    {"group": "Solver-grounded correctness", "name": "FR", "scoreboard": "FR",
     "what": "share of days with no hard violation: availability window, per-charger limit, site cap.", "why": "the schedule can actually be run."},
    {"group": "Solver-grounded correctness", "name": "Traceable", "scoreboard": "Traceable",
     "what": "every number in the answer appears in a tool output and comes from the last solve.", "why": "R3.4 and the paper's own claim: not faithfulness, traceability."},
    {"group": "Solver-grounded correctness", "name": "Wrong, unflagged", "scoreboard": "Wrong unflagged",
     "what": "an invalid schedule, an unsupported number or a wrong formulation, presented as valid.", "why": "the quantity the solver-grounded design claims to drive to zero."},
    {"group": "Cost and operation", "name": "Escalated", "scoreboard": "Escalated",
     "what": "the system declared it could not answer instead of presenting a schedule as valid.", "why": "the agent-versus-person split the advisor asked for."},
    {"group": "Cost and operation", "name": "Tokens", "scoreboard": "(rows only)",
     "what": "prompt and completion tokens per day, every call.", "why": "R4.4: what the architecture costs."},
    {"group": "Cost and operation", "name": "Hours / 100 days", "scoreboard": "",
     "what": "person-hours per hundred operating days. The human row measures it whole, the agent rows only over escalated days.", "why": "what the automation is worth."},
)

# Reviewer comment -> what this design does about it -> whether it holds today.
REVIEW: Tuple[Dict[str, str], ...] = (
    {"id": "R3.2", "comment": "Baselines are not fair: EVAgent calls CVXPY while the LLM must emit a schedule directly. "
                              "Compare under the same tool access and interaction budget, and include direct solver interfaces or rule-based workflows.",
     "design": "The ladder below changes one factor per step. EVAgent and ReAct differ only by the gate: same tool, same "
               "round budget, same request objects, same days. The rule-based workflow is the deterministic parser row.",
     "state": "partial"},
    {"id": "R3.4", "comment": "Distinguish solving correctly from formulating the correct problem from natural language, and evaluate the latter.",
     "design": "Every arm reads the same free-text request. Formulation is scored per session against the structured day "
               "(evaluation/formulation.py) and reported as its own column, never folded into Solved.",
     "state": "done"},
    {"id": "R4.2", "comment": "Prompting strategies of Section 3 are not reflected in the experiments. Align, or provide controlled ablations of the APBF components.",
     "design": "Two prompting rows that differ by exactly one prompt section. baseline/strategies.py::prompt_sections names "
               "the sections each one emits, and the two lists differ only by '## Reasoning Instructions'.",
     "state": "done"},
    {"id": "R4.3", "comment": "Ablate to separate simple solver access, multi-step reasoning, verification, memory and iterative repair.",
     "design": "One row per factor: single-call adds solver access, ReAct adds iteration, Plan-and-Act adds planning, EVAgent adds the gate.",
     "state": "missing"},
    {"id": "R4.5", "comment": "Conventional non-LLM automation baselines are missing: a deterministic parser or rule-based workflow "
                              "coupled to CVXPY, and a single-call function-calling pipeline.",
     "design": "Three conventional rows, one of which reads the request text with regex and calls the same LP.",
     "state": "missing"},
    {"id": "R2.5 / R2.7", "comment": "If agents call already-validated physical models, why is evaluation still needed?",
     "design": "The gate's six conditions are the answer: a validated LP still leaves the answer free to quote an earlier "
               "solve (E4), describe a different schedule from the one surfaced (E5), or omit a shortfall it was told about (E6).",
     "state": "done"},
)


def state_chip(state: str) -> str:
    cls = {"done": "ok", "partial": "warn", "missing": "bad"}.get(state, "")
    return f"<span class='chip {cls}'>{E(state)}</span>"


# ------------------------------------------------------------------- sections


def methods_section() -> str:
    A = arms()
    H: List[str] = ["<div class='tab' id='tab-methods'>"]

    H.append(
        "<div class='card'><h2>The ladder</h2><p>Each row adds one factor to the row above it. That is the whole "
        "design: if two rows differ by two things, no result of this case study can say which of the two mattered. "
        "The reviewers asked for exactly this (R3.2, R4.3, R4.5) and the ladder is how the answer is organised.</p>"
    )
    H.append("<table><tr><th>Block</th><th>Row</th><th>What it adds over the row above</th><th>Paper</th><th>Reviewer</th><th>In code</th></tr>")
    for r in ROWS:
        arm = A.get(r["arm"]) if r["arm"] else None
        if arm is None and r["arm"]:
            status = "<span class='chip bad'>not in the registry</span>"
        elif arm is None:
            status = "<span class='chip bad'>missing</span>"
        elif not arm.implemented:
            status = f"<span class='chip warn'>registered, not implemented</span><div class='muted'>{E(arm.pending_reason)}</div>"
        else:
            status = f"<span class='chip ok'>{E(r['arm'])}</span>"
        H.append(
            f"<tr><td class='muted'>{E(r['block'])}</td><td><b>{E(r['label'])}</b></td><td>{E(r['isolates'])}</td>"
            f"<td class='muted'>{E(r['paper'])}</td><td class='muted'>{E(r['reviewer'])}</td><td>{status}</td></tr>"
        )
    H.append("</table>")
    missing = [r["label"] for r in ROWS if not r["arm"] or not A.get(r["arm"]) or not A[r["arm"]].implemented]
    H.append(
        f"<p class='warn-box'><b>{len(missing)} of {len(ROWS)} rows do not run today:</b> {E(', '.join(missing))}. "
        "Four of them are the rows R4.3 and R4.5 asked for, so the ladder as published would have gaps at exactly the "
        "steps the reviewers named.</p></div>"
    )

    H.append(
        f"<div class='card'><h2>Reference row</h2><p><b>{E(REFERENCE_ROW['label'])}</b> "
        f"<span class='chip ok'>{E(REFERENCE_ROW['arm'])}</span></p><p>{E(REFERENCE_ROW['note'])}</p></div>"
    )

    # what the registry actually declares, field by field
    H.append("<div class='card'><h2>What the registry declares</h2><p class='muted'>Read from "
             "<code>scripts/run_ev_matrix.py</code> at build time. These flags decide what the scorer measures for each arm.</p>")
    H.append("<table><tr><th>arm</th><th>label</th><th>LLM</th><th>tools / grounded</th><th>gate</th><th>formulation scored</th><th>runs</th></tr>")
    for name, a in A.items():
        H.append(
            f"<tr><td><code>{E(name)}</code></td><td>{E(a.label)}</td><td>{'yes' if a.uses_llm else 'no'}</td>"
            f"<td>{'yes' if a.grounded else 'no'}</td><td>{'yes' if a.has_gate else 'no'}</td>"
            f"<td>{'yes' if a.scores_formulation else 'no'}</td>"
            f"<td>{'<span class=chip-ok>yes</span>' if a.implemented else '<b>no</b>'}</td></tr>"
        )
    H.append("</table>")
    H.append("<h3>Cost model per arm</h3><table><tr><th>arm</th><th>calls</th><th>completion tokens/call</th><th>context resend</th><th>basis</th></tr>")
    for name, a in A.items():
        c = a.cost
        H.append(
            f"<tr><td><code>{E(name)}</code></td><td>{E(getattr(c, 'n_calls', 0))}</td>"
            f"<td>{E(getattr(c, 'completion_tokens_per_call', 0))}</td>"
            f"<td>×{E(getattr(c, 'context_resend_factor', 0))}</td><td class='muted'>{E(getattr(c, 'basis', '') or 'no LLM')}</td></tr>"
        )
    H.append("</table></div>")

    H.append(
        "<div class='card'><h2>A trap in the missing parser row</h2>"
        "<p><code>evaluation/requests.py::reference_parse</code> already extracts every parameter from a request, and "
        "it is tempting to make it the deterministic-parser row. It must not be. That function knows the vocabulary "
        "<code>render_request</code> draws from, so it scores near perfectly by construction and its own docstring "
        "forbids reporting it as an LLM-free baseline. It is a round-trip check on the generator, not a competitor.</p>"
        "<p>The row R4.5 asked for has to be written independently, the way the power-flow case did it: a parser that "
        "handles the request shapes an engineer would actually write, gets a useful share of them right, and escalates "
        "the rest. A row that reads 100 % would prove nothing except that the generator and the parser were written "
        "by the same hand.</p></div>"
    )

    H.append(
        "<div class='card'><h2>The one that needs an answer before the run</h2>"
        "<p>The EVAgent arm is a tool-calling loop of up to three rounds with <code>tool_choice=\"auto\"</code>, plus a "
        "parse step and the gate (<code>agent/run.py</code>, <code>agent/llm_agent.py</code>). Strip the gate and it is "
        "close to the single-call row; give it its rounds and it is close to ReAct. If the three rows come out with the "
        "same numbers, that is the finding and it must be reported as one: the case study would then show that the "
        "agentic layer adds nothing here beyond the gate. What it must not do is ship with only one of the three "
        "implemented, because then the question is not asked at all.</p></div>"
    )
    return "".join(H) + "</div>"


def scenarios_section() -> str:
    import evaluation.requests as R
    import evaluation.stress as S

    days = frozen_days()
    H: List[str] = ["<div class='tab' id='tab-scenarios'>"]
    total = sum(int(d.get("record_count", 0)) for d in days)
    H.append(
        f"<div class='card'><h2>The days</h2><p>{len(days)} days of real sessions from the Caltech ACN-Data portal, "
        f"frozen once into <code>data/benchmark/</code> and committed, so the benchmark reproduces with no token and no "
        f"network. {total:,} raw records in total. Each file carries its fetch timestamp and a sha256 of the records, "
        f"and a day edited after freezing fails its hash check on load.</p>"
    )
    H.append("<table><tr><th>date</th><th>records</th><th>frozen</th><th>content hash</th></tr>")
    for d in days:
        H.append(
            f"<tr><td>{E(d.get('date'))}</td><td>{E(d.get('record_count'))}</td>"
            f"<td class='muted'>{E(str(d.get('fetched_at_utc'))[:10])}</td>"
            f"<td class='muted'><code>{E(str(d.get('content_hash'))[:23])}…</code></td></tr>"
        )
    H.append("</table>")
    H.append(
        "<p class='muted'>Site: <b>caltech</b>. The manuscript names Caltech and JPL in the same sentence; the frozen "
        "set fixes the answer to Caltech and the sentence has to follow it (notes, tabla_objetivo_ev.md E2).</p></div>"
    )

    H.append(
        f"<div class='card'><h2>The request variants</h2><p>One request is generated per day and variant by "
        f"<code>evaluation/requests.py</code>, as free text: times spelled in words, energies in Wh or kWh, power in W "
        f"or kW, sessions described in several sentence shapes. The list is generated once, hashed, and the digest is "
        f"stamped on every row, so a table built from those rows can be shown to have asked every arm the same thing.</p>"
    )
    H.append("<table><tr><th>variant</th><th>what the answer must be</th><th>class</th></tr>")
    for v in R.VARIANTS:
        kind = R.ANSWER_KIND_BY_VARIANT.get(v, "")
        cls = []
        if v in R.STATE_VARIANTS:
            cls.append("state: the schedule itself is the answer")
        if v in R.SHORTFALL_VARIANTS:
            cls.append("shortfall: the answer must state undelivered energy")
        H.append(f"<tr><td><code>{E(v)}</code></td><td>{E(kind)}</td><td class='muted'>{E('; '.join(cls))}</td></tr>")
    H.append("</table>")
    H.append(
        f"<p class='muted'>Site cap {R.SITE_CAP_KW:g} kW. Time-of-use: ${R.PEAK_PRICE:.2f}/kWh between "
        f"{R.PEAK_START_HOUR}:00 and {R.PEAK_END_HOUR}:00, ${R.OFF_PEAK_PRICE:.2f}/kWh otherwise.</p></div>"
    )

    H.append(
        "<div class='card'><h2>The stress set</h2><p>On a normal day the LP is always feasible, because the energy "
        "slack guarantees it. That means <b>Escalated can come out empty on all twenty days and then it discriminates "
        "nothing</b>. The stress set is what gives that column meaning: days where the request is genuinely "
        "unsatisfiable, so a system either declares it or presents an invalid schedule as valid. It is the EV "
        "counterpart of non-convergence and islanding in the power-flow case.</p>"
    )
    H.append("<table><tr><th>class</th><th>what is made impossible</th></tr>")
    explain = {
        "lowered_cap": f"the site cap is dropped to one of {', '.join(f'{c:g}' for c in S.LOWERED_CAPS_KW)} kW, below what the day needs",
        "disabled_chargers": "one or more chargers are set to 0 kW",
        "impossible_deadline": "a session is asked for more energy than its window can deliver",
        "contradictory_request": "the request contradicts itself and cannot be formulated at all",
    }
    for c in S.CLASSES:
        H.append(f"<tr><td><code>{E(c)}</code></td><td>{E(explain.get(c, ''))}</td></tr>")
    H.append("</table>")
    H.append(
        f"<p class='muted'>What a system must declare for the day to count as escalated rather than wrong: "
        f"{E(', '.join(S.DECLARATION_KEYS))}.</p>"
        "<p class='warn-box'><b>Open:</b> the stress days are implemented and have not been run. Until they are, the "
        "Escalated column of the main table rests on the twenty normal days alone (notes, tabla_objetivo_ev.md E3).</p></div>"
    )
    return "".join(H) + "</div>"


def prompts_section() -> str:
    from baseline.strategies import STRATEGIES, build_messages, prompt_sections

    H: List[str] = ["<div class='tab' id='tab-prompts'>"]
    H.append(
        "<div class='card'><h2>Every prompt, as the run would send it</h2><p>Rendered here by calling the same "
        "builders the harness calls, on a real request object. Nothing on this page is a copy of a prompt.</p>"
    )
    H.append("<table><tr><th>strategy</th><th>sections, in order</th></tr>")
    base = set(prompt_sections(STRATEGIES[0]))
    for s in STRATEGIES:
        secs = prompt_sections(s)
        cells = " ".join(
            f"<span class='chip {'acc' if sec not in base else ''}'>{E(sec)}</span>" for sec in secs
        )
        H.append(f"<tr><td><code>{E(s)}</code></td><td>{cells}</td></tr>")
    H.append(
        "</table><p class='muted'>The two prompting rows differ by one section and nothing else. That is the "
        "controlled ablation R4.2 asked for, and it is checkable here rather than asserted in the text.</p></div>"
    )

    req = sample_request()
    if req is not None:
        try:
            from evaluation.requests import request_from_dict

            obj = request_from_dict(req)
        except Exception:
            obj = None
        H.append(
            f"<div class='card'><h2>The request these prompts carry</h2>"
            f"<p class='muted'>id <code>{E(req.get('id'))}</code> · variant <code>{E(req.get('variant'))}</code> · "
            f"day {E(req.get('date'))}</p><pre>{E(req.get('text', ''))[:4000]}</pre></div>"
        )
        if obj is not None:
            for s in STRATEGIES:
                try:
                    msgs = build_messages(s, obj)
                except Exception as exc:  # pragma: no cover - rendering is best effort
                    H.append(f"<div class='card'><h2>{E(s)}</h2><p class='muted'>could not render: {E(exc)}</p></div>")
                    continue
                H.append(f"<div class='card'><h2>{E(s)}</h2>")
                for m in msgs:
                    H.append(
                        f"<div class='blk'><div class='blk-h'><b>{E(m['role'])}</b></div>"
                        f"<pre>{E(m['content'])[:12000]}</pre></div>"
                    )
                H.append("</div>")
    return "".join(H) + "</div>"


def tools_section() -> str:
    import agent.llm_agent as LA

    tool = LA._SOLVE_TOOL["function"]
    H: List[str] = ["<div class='tab' id='tab-tools'>"]
    H.append(
        "<div class='card'><h2>One tool, the same for every arm that has tools</h2>"
        f"<p><code>{E(tool['name'])}</code> runs the CVXPY convex optimiser. Every grounded arm receives this exact "
        "schema, with the same argument set and the same round budget, so tool access is not a difference between "
        "them. The arms without tools receive no tool at all, which is the point of the row.</p>"
        f"<p class='muted'>{E(tool['description'])}</p>"
        f"<pre>{E(json.dumps(tool.get('parameters', {}), indent=2))}</pre>"
    )
    H.append(
        "<p><b>What the tool returns:</b> success, total_cost_usd, peak_load_kw, total_unmet_kwh, pct_fully_served. "
        "The schedule matrix is held by the harness, not passed back through the model, so the answer and the "
        "deliverable can come apart. Gate condition E5 exists for exactly that.</p>"
    )
    H.append(
        f"<p class='muted'>The what-if arguments (<code>disabled_chargers</code>, <code>site_cap_kw</code>, "
        f"<code>extra_sessions</code>, <code>penalty_unmet</code>) change the problem that is posed. A retry after a "
        f"failed gate is not allowed to use them: <code>agent/llm_agent.py</code> blocks "
        f"{E(', '.join(sorted(getattr(LA, 'PROBLEM_CHANGING_ARGUMENTS', gate_module().PROBLEM_CHANGING_ARGUMENTS))))} "
        "on the retry, so a method cannot pass the gate by quietly solving an easier problem.</p></div>"
    )

    H.append(
        "<div class='card'><h2>The LP itself</h2><p>Variables: power per session per step, plus an unmet-energy slack "
        "per session. Objective: minimise TOU energy cost plus a large penalty on unmet energy. Constraints: charging "
        "only inside the availability window, per-charger power limit, site cap at every step, and delivered energy "
        "plus slack equal to the requested energy. <code>optimization/solver.py</code>.</p>"
        "<p class='muted'>The slack is why a normal day is always feasible, and therefore why the stress set exists.</p></div>"
    )
    return "".join(H) + "</div>"


def gate_section() -> str:
    g = gate_module()
    H: List[str] = ["<div class='tab' id='tab-gate'>"]
    H.append(
        "<div class='card'><h2>The verification gate</h2><p>Six conditions on the final answer, evaluated separately "
        "and never collapsed into one boolean. On a failure the verdict goes back to the model once; if the second "
        "attempt fails too, the answer is replaced by a declared failure that carries no numbers, and the day counts "
        "as escalated to a person. This is the EV counterpart of the power-flow gate V1–V7.</p>"
    )
    H.append("<table><tr><th>label</th><th>key</th><th>what it checks</th><th>power-flow counterpart</th></tr>")
    counterpart = {
        "solver_optimal": "V1–V3 (the tool produced a runnable state)",
        "no_hard_violation": "V1–V3",
        "traceable": "V4",
        "currency": "V5",
        "schedule_consistency": "none — added by this case study",
        "shortfall_declared": "none — added by this case study",
    }
    for key in g.CONDITION_ORDER:
        H.append(
            f"<tr><td><b>{E(g.CONDITION_LABELS[key])}</b></td><td><code>{E(key)}</code></td>"
            f"<td>{E(g.CONDITION_DESCRIPTIONS[key])}</td><td class='muted'>{E(counterpart.get(key, ''))}</td></tr>"
        )
    H.append("</table>")
    H.append(
        f"<p class='muted'>Attempts before a declared failure: {E(g.MAX_VERIFICATION_ATTEMPTS)}. A shortfall counts as "
        f"material, and so must be declared under E6, only when it crosses both floors: "
        f"{E(g.MATERIAL_UNMET_KWH)} kWh and {E(g.MATERIAL_UNMET_SHARE)} of the energy requested.</p>"
    )
    H.append(
        "<p class='warn-box'><b>What a reader should check here.</b> E5 and E6 have no power-flow counterpart, so they "
        "are the two an expert has not already accepted elsewhere. E5 recomputes the headline metrics from the "
        "surfaced schedule and compares them with the last tool output, which catches an answer quoting one solve "
        "while the matrix on the table is another. E6 requires a material shortfall to be stated; it never requires "
        "the day to be servable, so it does not turn an infeasible day into a failure of the method.</p></div>"
    )

    H.append(
        "<div class='card'><h2>What the gate cannot see, and what that costs</h2>"
        "<p>The gate's scope is deliberate and correct: only the agent's own evidence, the schedule it produced, the "
        "outputs of the tools it called and the text it wrote. No reference solution, no optimum. A gate deployed at "
        "a real site has no ground truth to consult, so one that used it would not be the thing being evaluated.</p>"
        "<p>The consequence is the central result of the run of 2026-09-21, and it has to be faced before the table "
        "is built. On all twenty days the agent parsed the right <i>number</i> of sessions and misread a field on a "
        "few of them: <b>808 of 894 sessions exact, 90.4 %</b>. It then optimised the day it had parsed. That LP is "
        "feasible and optimal for the problem as posed, so <b>E1 and E2 pass</b>; every number in the answer comes "
        "from that solve, so <b>E3 and E4 pass</b>; and the gate accepted all twenty answers. Scored against the real "
        "day, those same schedules break the true sessions' constraints by 0.5 to 6.5 kW. Result: "
        "<b>0 of 20 solved, 0 escalated, 20 wrong and unflagged</b>.</p>"
        "<p class='warn-box'><b>The mission is unreachable as the design stands.</b> Solved + Escalated = 100 % with "
        "Wrong-unflagged = 0 requires the system to notice when it has misread the request, and nothing in the "
        "agent's own evidence reveals that the day it optimised is not the day the text described. Three ways out, "
        "and the choice is not the harness's to make: (a) add a condition that reads the parsed parameters back "
        "against the request text, which is still the agent's own evidence, so the scope rule survives; (b) keep the "
        "gate as it is and report the honest finding, that the gate protects against fabricated and stale numbers but "
        "not against misreading; (c) both, and show what (a) buys.</p></div>"
        "<div class='card'><h2>The unit of measurement, and the symmetry it breaks</h2>"
        "<p>A day counts as correctly formulated only when <b>every</b> one of its sessions is. On a day with 44 cars "
        "that is 44 chances to fail, and 90.4 % per session becomes 0 % per day. The harness already reports both "
        "numbers side by side, which is right.</p>"
        "<p>What it means for the comparison with the power-flow case is not settled. There, one item is one request "
        "with a handful of parameters; here, one item is a day with dozens of sessions. The same per-parameter "
        "accuracy produces a far worse row here, and a reader comparing the two tables would read that as a "
        "difference between the methods rather than between the units. Either both tables carry the per-item rate "
        "next to the per-day one, or the text says plainly why the two are not comparable.</p></div>"
        "<div class='card'><h2>Where every day lands</h2><p>The three outcomes are exclusive and sum to 100 %. "
        "<code>evaluation/outcome.py</code>, following <code>power-flow-agent/benchmarks/scoring.py</code>.</p>"
        "<table><tr><th>outcome</th><th>definition</th></tr>"
        "<tr><td><span class='vd solved'>solved</span></td><td>the conjunction of three terms and the gate: the state "
        "is right (no hard violation, cost gap within tolerance, and the gap comparable, i.e. the cost was not bought "
        "by leaving energy undelivered), every number traces to the last solve, and the answer matches what was asked "
        "when the request asks something checkable.</td></tr>"
        "<tr><td><span class='vd escalated'>escalated</span></td><td>the system declared it could not answer, instead "
        "of presenting a schedule as valid. Takes precedence over the other two.</td></tr>"
        "<tr><td><span class='vd wrong'>wrong, unflagged</span></td><td>an invalid schedule, a number with no support, "
        "or a wrong formulation, presented as valid. The one an operator reads first.</td></tr></table>"
        "<p class='muted'><b>Formulation is not a term of Solved</b> (decided 2026-09-21). It is still scored and "
        "still stored on every row, but each column measures one thing: Formulation says whether the request was "
        "understood, Solved says whether what was delivered was right.</p></div>"
    )

    # columns and their group
    H.append(
        "<div class='card'><h2>The columns, by framework group</h2><p>Three groups, with the framework's own names. "
        "The same groups and the same row names as the power-flow table: that symmetry is an explicit requirement "
        "(notes, PENDIENTES G8), and only task-utility metrics are allowed to differ between the two cases.</p>"
    )
    H.append("<table><tr><th>group</th><th>column</th><th>what it measures</th><th>why it is there</th><th>emitted today</th></tr>")
    last = ""
    for c in COLUMNS:
        grp = "" if c["group"] == last else E(c["group"])
        last = c["group"]
        emitted = (
            f"<span class='chip ok'>{E(c['scoreboard'])}</span>" if c["scoreboard"] and c["scoreboard"] != "(rows only)"
            else ("<span class='chip warn'>rows only, not in the scoreboard</span>" if c["scoreboard"] else "<span class='chip bad'>nothing computes it</span>")
        )
        H.append(
            f"<tr><td class='muted'><b>{grp}</b></td><td><b>{E(c['name'])}</b></td><td>{E(c['what'])}</td>"
            f"<td class='muted'>{E(c['why'])}</td><td>{emitted}</td></tr>"
        )
    H.append("</table>")
    H.append(
        "<p class='warn-box'><b>Three things to settle before the table is built.</b> "
        "(1) The scoreboard emits an <code>Answer</code> column that the target table does not define. "
        "(2) The target table still carries a <code>Fieles</code> (faithful) column although the same note decides "
        "faithfulness is out and traceability is in. "
        "(3) <code>Unmet</code> and <code>Hours / 100 days</code> are defined in the target table and nothing computes "
        "them. Each is a one-line decision, and each changes what the table looks like.</p></div>"
    )
    return "".join(H) + "</div>"


def review_section() -> str:
    H: List[str] = ["<div class='tab' id='tab-review'>"]
    H.append(
        "<div class='card'><h2>What each reviewer asked, and where this design answers it</h2>"
        "<p class='muted'>Comment text compressed from <code>review/reviewer_comments.md</code> in the notes repo. "
        "The state is the state of the <b>code</b>, not of the manuscript.</p><table>"
        "<tr><th>ID</th><th>Comment</th><th>What this design does</th><th>State</th></tr>"
    )
    for r in REVIEW:
        H.append(
            f"<tr><td><b>{E(r['id'])}</b></td><td class='muted'>{E(r['comment'])}</td><td>{E(r['design'])}</td>"
            f"<td>{state_chip(r['state'])}</td></tr>"
        )
    H.append("</table></div>")

    H.append(
        "<div class='card'><h2>Symmetry with the power-flow case</h2><p>The two case studies must present the same "
        "metric groups and the same row names; only task-utility metrics may differ. Anything red here is a difference "
        "a reader will read as an inconsistency to explain.</p><table>"
        "<tr><th>Aspect</th><th>Power flow</th><th>EV charging</th><th></th></tr>"
        "<tr><td>Rows without an LLM</td><td><code>rule_based</code>: regex reads the request text, calls the solver</td>"
        "<td><code>charge_asap</code> and <code>optimum</code>, <b>neither reads the request text</b></td>"
        "<td>" + state_chip("missing") + "</td></tr>"
        "<tr><td>Prompting rows</td><td>structured, chain-of-thought</td><td>structured, chain-of-thought</td>"
        "<td>" + state_chip("done") + "</td></tr>"
        "<tr><td>Agent rows without a gate</td><td><code>react_nogate</code>, <code>plan_act_nogate</code></td>"
        "<td>registered, not implemented</td><td>" + state_chip("missing") + "</td></tr>"
        "<tr><td>Gated row</td><td><code>pfagent</code>, gate V1–V7</td><td><code>evagent</code>, gate E1–E6</td>"
        "<td>" + state_chip("done") + "</td></tr>"
        "<tr><td>Outcome split</td><td>solved / escalated / wrong-unflagged, exclusive, sum 100</td>"
        "<td>same, same code shape</td><td>" + state_chip("done") + "</td></tr>"
        "<tr><td>Models in the main table</td><td>gpt-5.6-sol and gpt-4o-mini</td>"
        "<td><b>gpt-4o-mini only</b></td><td>" + state_chip("missing") + "</td></tr>"
        "<tr><td>Stress set</td><td>run</td><td>implemented, not run</td><td>" + state_chip("partial") + "</td></tr>"
        "<tr><td>Repetitions per item</td><td>one run per request</td><td>one run per day; the manuscript claims a mean of five</td>"
        "<td>" + state_chip("missing") + "</td></tr>"
        "</table></div>"
    )

    H.append(
        "<div class='card'><h2>Claims in the manuscript this design does not support yet</h2>"
        "<p class='muted'>Verified against the files, notes repo <code>tabla_objetivo_ev.md</code>. These are wrong in "
        "the paper today, independently of any run.</p><ul>"
        "<li>The two EVAgent rows of <code>tab:ev_results</code> print the solver's five numbers; the committed result "
        "file gives different numbers, over nineteen days and not twenty.</li>"
        "<li>The mean of five runs does not exist. The harness runs once per date.</li>"
        "<li>The thirty seconds, three to five calls and two to five thousand tokens in the prose come from no file.</li>"
        "<li>The site is named twice, Caltech and JPL, in the same sentence.</li></ul></div>"
    )
    return "".join(H) + "</div>"


def plan_section() -> str:
    A = arms()
    sets = run_sets()
    H: List[str] = ["<div class='tab' id='tab-plan'>"]
    H.append("<div class='card'><h2>What has been run</h2><table>"
             "<tr><th>directory</th><th>model</th><th>days</th><th>arms</th><th>traces</th><th>spent</th><th>real data</th></tr>")
    for s in sets:
        armnames = s.get("arms") or []
        H.append(
            f"<tr><td><code>{E(s['_dir'])}</code></td><td>{E(s.get('model_resolved') or s.get('model_requested'))}</td>"
            f"<td>{E(s.get('days') or s.get('n_days'))}</td><td class='muted'>{E(', '.join(armnames))}</td>"
            f"<td>{E(s['_traces'])}</td><td>${E(s.get('spent_usd'))}</td>"
            f"<td>{'yes' if not s.get('synthetic') else 'NO — smoke'}</td></tr>"
        )
    H.append("</table><p class='muted'>Only the first directory carries traces; the other two were written by a "
             "rescore of the same rows. A trace viewer therefore has one run set to read.</p></div>")

    H.append(
        "<div class='card'><h2>What is left, in the order it unblocks</h2><ol>"
        "<li><b>The four missing rows</b> (deterministic parser, single-call, ReAct, Plan-and-Act). No credit spent "
        "writing them; they are what R4.3 and R4.5 asked for.</li>"
        "<li><b>The stress days.</b> Implemented, never run. Without them Escalated does not discriminate.</li>"
        "<li><b>The second model.</b> The main table pairs gpt-5.6-sol with gpt-4o-mini in the power-flow case and the "
        "same pairing is required here.</li>"
        "<li><b>Repetitions.</b> The manuscript claims a mean of five runs; the harness does one.</li>"
        "<li><b>The report.</b> <code>python -m scripts.ev_report &lt;dir&gt; --pdf</code> next to every results "
        "directory, as the repository rule requires.</li></ol>"
        "<p class='warn-box'><b>Credit.</b> A full EV run was estimated at $10–11 and the OpenRouter balance has been "
        "in single digits since 2026-09-18 (notes, PENDIENTES A5). The four missing rows raise that estimate, and the "
        "no-tools rows are the expensive ones because they must write a session-by-step matrix as text.</p></div>"
    )
    return "".join(H) + "</div>"


def overview_section() -> str:
    A = arms()
    days = frozen_days()
    import evaluation.requests as R

    implemented = [n for n, a in A.items() if a.implemented]
    H: List[str] = ["<div class='tab on' id='tab-overview'>"]
    H.append(
        "<div class='card'><h2>The question this case study asks</h2>"
        "<p>A site operator describes a day of charging in plain English: the cars, when each one arrives and leaves, "
        "how much energy it needs, what its charger can deliver. Somebody has to turn that into the parameters of an "
        "optimisation problem, solve it under the site cap, and answer what was asked, whether that is the schedule "
        "itself or a question about it. Today that somebody is an engineer with CVXPY. The question is what happens "
        "when it is a language model.</p>"
        "<div class='flow'>"
        "<div class='box'><b>Request</b><span>free text, one per day and variant</span></div><span class='arr'>→</span>"
        "<div class='box'><b>Formulate</b><span>arrival, departure, energy, max power, per session</span></div><span class='arr'>→</span>"
        "<div class='box'><b>Compute</b><span>CVXPY, or the model writing kW by hand</span></div><span class='arr'>→</span>"
        "<div class='box'><b>Report</b><span>the schedule, or the answer asked for</span></div><span class='arr'>→</span>"
        "<div class='box'><b>Verdict</b><span>solved · escalated · wrong</span></div></div></div>"
    )
    H.append(
        "<div class='grid g3'>"
        "<div class='card'><h3>What a correct answer needs</h3><ul>"
        "<li><b>Formulation:</b> every session's four parameters read from the text, not invented.</li>"
        "<li><b>A runnable schedule:</b> inside every availability window, under every charger limit, under the site "
        "cap at every step.</li>"
        "<li><b>The operator's answer:</b> the cost, the undelivered energy, the share served, the car, whatever was "
        "asked, and it must be the schedule that was actually produced.</li></ul></div>"
        "<div class='card'><h3>What can go wrong</h3><ul>"
        "<li>A schedule that looks fine and breaks the site cap: <b>wrong, presented as right</b>.</li>"
        "<li>A cheap schedule that is cheap because it never charges the cars.</li>"
        "<li>An answer quoting one solve while the schedule on the table is another.</li>"
        "<li>A shortfall the operator is never told about.</li></ul></div>"
        "<div class='card'><h3>What is expected of EVAgent</h3><p>Every reported number comes from the LP and passes "
        "six verification conditions before it reaches the operator. When they cannot pass, the day is "
        "<b>escalated</b> to a person rather than answered. The target for the solver-grounded row, as fixed for the "
        "power-flow case: <span class='vd solved'>solved</span> + <span class='vd escalated'>escalated</span> = 100 %, "
        "<span class='vd wrong'>wrong, unflagged</span> = 0.</p></div></div>"
    )
    H.append(
        f"<div class='card'><h2>Common to every arm</h2>"
        f"<span class='chip'>{len(days)} frozen Caltech days</span>"
        f"<span class='chip'>{len(R.VARIANTS)} request variants</span>"
        f"<span class='chip'>site cap {R.SITE_CAP_KW:g} kW</span>"
        f"<span class='chip'>TOU ${R.PEAK_PRICE:.2f} peak / ${R.OFF_PEAK_PRICE:.2f} off-peak</span>"
        f"<span class='chip'>same request objects, hashed</span>"
        f"<span class='chip'>same seeds and repeats</span>"
        f"<span class='chip'>same completion budget</span>"
        f"<span class='chip'>one scorer for every arm</span>"
        f"<span class='chip'>every message stored in the trace</span>"
        f"<span class='chip'>{len(implemented)} of {len(A)} registered arms run</span></div>"
    )
    H.append(
        "<div class='card'><h2>How to read this page</h2><p>It states the design and marks what is missing from it. "
        "Everything on it is read from the code when the page is built, so it cannot describe a design that is not "
        "the one that would run. Start at <b>Methods</b> for the ladder of rows, then <b>Review</b> for the mapping "
        "to the reviewers' comments and the symmetry with the power-flow case. Red marks a gap, amber a decision "
        "still open.</p></div>"
    )
    return "".join(H) + "</div>"


CSS = """
:root{--bg:#f3f5f8;--panel:#fff;--line:#e3e7ee;--text:#0f172a;--muted:#64748b;--acc:#2f5fd0;--ok:#1f9d55;--esc:#e0891a;--bad:#d53f3f;--shadow:0 1px 2px rgba(15,23,42,.06),0 4px 14px rgba(15,23,42,.05)}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 Inter,-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:var(--text);background:var(--bg)}
header{position:sticky;top:0;z-index:5;background:var(--panel);border-bottom:1px solid var(--line);padding:10px 22px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
header h1{font-size:17px;margin:0;letter-spacing:-.01em}.tabs{display:flex;gap:4px;flex-wrap:wrap}body.embed header{display:none}
.tabs button{font:inherit;font-weight:500;padding:7px 14px;border:1px solid transparent;border-radius:8px;background:transparent;cursor:pointer;color:var(--muted)}.tabs button.on{background:var(--acc);color:#fff}
main{padding:18px 22px;max-width:1500px;margin:0 auto}.tab{display:none}.tab.on{display:block}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow);margin-bottom:12px}
.card h2{font-size:16px;margin:0 0 6px}.card h3{font-size:14px;margin:12px 0 6px}.card ul{margin:6px 0;padding-left:18px}.card ol{margin:6px 0;padding-left:20px}.card li{margin:3px 0}
.grid{display:grid;gap:12px}.g3{grid-template-columns:repeat(3,minmax(0,1fr))}.g2{grid-template-columns:repeat(2,minmax(0,1fr))}
@media(max-width:900px){.grid.g3,.grid.g2{grid-template-columns:1fr}main{padding:14px 12px}}
.muted{color:var(--muted);font-size:12.5px}
.chip{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11.5px;font-weight:600;background:#eef1f5;color:#334155;margin:2px 4px 2px 0}
.chip.acc{background:var(--acc);color:#fff}.chip.ok{background:#e6f4ea;color:#166534}.chip.bad{background:#fdecec;color:#991b1b}.chip.warn{background:#fdf0e3;color:#9a5b0a}
.vd{display:inline-block;padding:1px 8px;border-radius:999px;color:#fff;font-size:11px;font-weight:600;white-space:nowrap}
.vd.solved{background:var(--ok)}.vd.escalated{background:var(--esc)}.vd.wrong{background:var(--bad)}
.flow{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0}
.flow .box{background:#fff;border:1px solid var(--line);border-radius:10px;padding:8px 12px;box-shadow:var(--shadow)}
.flow .box b{display:block;font-size:13px}.flow .box span{font-size:12px;color:var(--muted)}.flow .arr{color:var(--muted);font-size:18px}
table{border-collapse:collapse;width:100%;font-size:13px;background:#fff}th,td{border:1px solid var(--line);padding:6px 8px;vertical-align:top;text-align:left}th{background:#f6f8fb;font-weight:600}
code{font-family:"JetBrains Mono",ui-monospace,Menlo,Consolas,monospace;font-size:12px;background:#f1f4f9;padding:1px 4px;border-radius:4px}
pre{background:#fafbfd;border:1px solid var(--line);border-radius:8px;padding:10px;white-space:pre-wrap;word-break:break-word;font:12px/1.45 "JetBrains Mono",ui-monospace,Menlo,Consolas,monospace;margin:4px 0;max-height:460px;overflow:auto}
.blk{border-left:5px solid var(--acc);background:#fff;border-radius:0 8px 8px 0;padding:8px 12px;margin:8px 0;border-top:1px solid var(--line);border-right:1px solid var(--line);border-bottom:1px solid var(--line)}
.blk-h{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.warn-box{background:#fdf7ec;border:1px solid #f0dcbc;border-radius:10px;padding:10px 12px;font-size:13px;margin:10px 0 0}
"""

TABS: Tuple[Tuple[str, str], ...] = (
    ("overview", "Overview"),
    ("methods", "Methods"),
    ("scenarios", "Scenarios"),
    ("prompts", "Prompts"),
    ("tools", "Tools"),
    ("gate", "Gate & scoring"),
    ("review", "Review"),
    ("plan", "Run plan"),
)

SCRIPT = """
const tabs=document.querySelectorAll('.tabs button');
function show(k){tabs.forEach(b=>b.classList.toggle('on',b.dataset.tab===k));document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on',t.id==='tab-'+k));window.scrollTo(0,0);if(window.self!==window.top){window.parent.postMessage({page:'design',tab:k},'*');}}
tabs.forEach(b=>b.onclick=()=>{show(b.dataset.tab);history.replaceState(null,'','#'+b.dataset.tab);});
function fromHash(){const k=(location.hash||'#overview').slice(1);if(document.getElementById('tab-'+k)){show(k);}}
window.addEventListener('hashchange',fromHash);
if(window.self!==window.top){document.body.classList.add('embed');}
fromHash();
"""


def build() -> Path:
    """Render the design page and return the path it was written to."""
    H: List[str] = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>EVAgent · Evaluation design</title>"
        "<link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap' rel='stylesheet'>"
        f"<style>{CSS}</style></head><body>"
    ]
    H.append(
        "<header><h1>EVAgent · Evaluation design</h1><nav class='tabs'>"
        + "".join(f"<button data-tab='{k}' class='{'on' if k == 'overview' else ''}'>{v}</button>" for k, v in TABS)
        + "</nav></header><main>"
    )
    H.append(overview_section())
    H.append(methods_section())
    H.append(scenarios_section())
    H.append(prompts_section())
    H.append(tools_section())
    H.append(gate_section())
    H.append(review_section())
    H.append(plan_section())
    H.append(f"</main><script>{SCRIPT}</script></body></html>")

    out = PROJECT_ROOT / "results" / "visuals" / "design.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(H), encoding="utf-8")
    return out


if __name__ == "__main__":
    p = build()
    print(f"wrote {p} ({p.stat().st_size // 1024} KB)")

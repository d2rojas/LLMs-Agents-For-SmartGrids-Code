# Power Flow Agent (PFAgent)

A conversational agent that delegates AC power flow to **PandaPower's Newton-Raphson
solver**, while the LLM parses natural-language requests, sequences tools, tracks network
state, and writes operator-readable answers. For the paper (§6.3), every method is evaluated
on the same requests and metrics: LLM-only prompting, single-call tool use, a rule-based
parser with no LLM, multi-step agents, and PFAgent, which adds a task-level verification gate
so that only numbers traceable to a solver output are reported.

> Architecture notes and the module inventory: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Layout

```
run.py            the front door: run a method on a case, then render the results
methods/          everything that answers a request. One folder per method with its method.json and prompt
                  .txt files (rule_based, llm_only_structured, llm_only_cot, plan_act_nogate, react_nogate, pfagent;
                  _shared/ texts, _archive/ variants), plus the code that runs them:
                    methods/agent/          engine.py (ReAct loop, Plan-and-Act, verification gate), tools.py (the 12
                                            solver tools and the dispatcher), prompts.py
                    methods/prompting/      llm_only.py (case tables in the prompt, the LLM-only runner),
                                            prompt_variants.py (prompt assembly), prompts_baseline.py
                    methods/deterministic/  rule_based.py, the parser: request text to solver calls, no LLM
solver/           PandaPower: case_loader, power_flow, contingency (N-1), remedial, validators, schemas
evaluation/       requests.py (the 40 scenarios per system), runner.py (runs one method), scoring.py,
                  metrics.py, common_eval.py (one evaluator for every method), rescore.py, postprocess.py,
                  trace_figures.py, compare_runs.py, design_page.py (results/visuals/design.html)
results/          every run: <system>/<date>/<model>/<method>/ with traces, summary, REPORT   (results/README.md)
data/             MATPOWER case files                                                          (data/README.md)
ui/  viz/         the Streamlit UI (streamlit run ui/app.py) and the Plotly figures
scripts/          fetch_matpower_cases.py
tests/            pytest suite, no API keys needed
```

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=...          # or OPENROUTER_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY, or a .env file

python run.py list-methods
python run.py show-prompt --method pfagent
python run.py run --method pfagent --model openrouter:openai/gpt-4o-mini --case ieee14 --n 40 --dry-run
python run.py run --method pfagent --method react_nogate --model openrouter:openai/gpt-4o-mini --case ieee14 --n 40
open results/INDEX.md              # then the run folder's REPORT.md and traces/
python run.py serve                # results/visuals/: design.html, results.html, viewer.html
```

Six methods make up the evaluation design: the deterministic parser, structured prompting,
chain-of-thought prompting, Plan-and-Act, ReAct and PFAgent. They share one rules block, one
operations catalogue, one answer object and one evaluator (`evaluation/common_eval.py`);
`results/visuals/design.html` documents all of it, prompts included. Other variants are kept
under `methods/_archive/` for their old runs. The design runs on five IEEE systems, 14, 30, 57, 118
and 300 buses, with the same 40-request shape on each (`--case ieee14 | ieee30 | ieee57 | ieee118 | ieee300`);
`run.py run` has no default case.

`run` calls `evaluation/runner.py` with the flags the paper runs used, rescores the
report offline, and renders one folder per (method, model, case): a per-run transcript
(every message, tool call and tool output), a per-run narrative (steps, tokens, formulation
check, verification, outcome), `summary.csv`, and `REPORT.md` with the counts per metric.
Models are `provider:model` strings; the runs behind the current paper tables used
`openrouter:openai/gpt-4o-mini`, `openrouter:openai/gpt-5.6-sol` and `openrouter:openai/gpt-5.4`.

Interactive UI: `streamlit run ui/app.py`.

## Data and protocol

MATPOWER IEEE 14/30/57/118-bus cases (bundled in [`data/`](data/) and [`solver/cases/`](solver/cases/)).
Loads and generator setpoints are perturbed around the base case (`--k 1`) to mitigate
memorization; requests are generated deterministically from (case, N, seed) by
`evaluation/requests.py`, N = 40 per case. Ground truth is the PandaPower solution of the
intended tool calls on the same perturbed case.

## Metrics

Three groups, as in the paper. Definitions and code: `evaluation/scoring.py`, `evaluation/metrics.py`.

- **Task utility**: formulation exactness (did the executed tool calls match the request), voltage
  MAE (`V_MAE`, p.u.) and branch-flow MAE against the reference, both over all runs and over
  formulation-exact runs, KCL residual (`B_mean`, MW).
- **Solver-grounded correctness**: where every request ended, as three exclusive outcomes that
  sum to 100%: solved autonomously, escalated to a person, wrong and unflagged; V-pass (all
  verification conditions, checked offline for every method); traceable answers (every number in
  the answer appears in a tool output from the solve after the last network change); safe failure
  on the stress set.
- **Cost and time**: LLM and tool calls, prompt and completion tokens, cost from `pricing.json`,
  wall time.

## Verification gate (PFAgent)

Conditions V1 to V7 in `methods/agent/engine.py:verify_final_answer`: converged, power balance, no isolated
buses, faithfulness of reported numbers, currency (numbers come from the solve after the last
mutation), argument grounding (every mutating-tool argument traces to the request or a prior tool
output), and claims consistent with the agent's own last solved state. A rejected answer is
retried once with the failed conditions spelled out; an answer that still fails is escalated.

## Paper tables

`evaluation/build_paper_tables.py` renders `evaluation/tab_pf_*.tex` from the runs it names in
`SOURCES`, `STRESS_SOURCES` and `SPLIT_TOOL_SOURCES`. The same runs are mirrored, readable, under
`results/` (see `results/README.md`, "Provenance"), where every raw report and trace is tracked in git.

## Tests

```bash
pip install pytest && pytest        # solver, tools, scoring, prompts, post-processing; no API keys
pytest tests/test_methods_prompts.py    # the prompt texts still hash to the values stamped on the paper runs
```

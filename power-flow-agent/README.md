# Power Flow Agent (PFAgent)

A conversational agent that delegates AC power flow to **PandaPower's Newton-Raphson
solver**, while the LLM parses natural-language requests, sequences tools, tracks network
state, and writes operator-readable answers. For the paper (§6.3), six methods answer the same
requests and are scored by the same evaluator: a deterministic parser with no LLM, structured
and chain-of-thought prompting with no tools, Plan-and-Act, ReAct, and PFAgent, which adds a
verification gate so that only numbers traceable to a solver output are reported.

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
data/fetch_matpower_cases.py   refresh the MATPOWER case files
tests/            pytest suite, no API keys needed
```

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=...          # or OPENROUTER_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY, or a .env file

python run.py list-methods
python run.py show-prompt --method pfagent
python run.py run --method pfagent --model openrouter:openai/gpt-4o-mini --case ieee14 --n 20 --dry-run
python run.py run --method pfagent --method react_nogate --model openrouter:openai/gpt-4o-mini --case ieee14 --n 20
open results/INDEX.md              # then the run folder's REPORT.md and traces/
python run.py serve                # results/visuals/: design.html, results.html, viewer.html
```

Six methods make up the evaluation design: the deterministic parser, structured prompting,
chain-of-thought prompting, Plan-and-Act, ReAct and PFAgent. They share one rules block, one
operations catalogue, one answer object and one evaluator (`evaluation/common_eval.py`);
`results/visuals/design.html` documents all of it, prompts included. Other variants are kept
under `methods/_archive/` for their old runs. The design runs on five IEEE systems, 14, 30, 57, 118
and 300 buses, with the same 20-request shape on each (5 per difficulty) (`--case ieee14 | ieee30 | ieee57 | ieee118 | ieee300`);
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
`evaluation/requests.py`, N = 20 per case (5 per difficulty; the runs before 2026-09-25 used N = 40 on the 14-bus system). Ground truth is the PandaPower solution of the
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

## Where things are

One request in plain English, six ways to answer it, one evaluator. This section says where each
piece lives. The evaluation design itself (methods, prompts, answer object, scoring, run plan) is
`results/visuals/design.html`, built by `evaluation/design_page.py`; open it with `run.py serve`.

### The six methods and their code

| method | `methods/` folder (prompts) | code that runs it |
|---|---|---|
| Deterministic parser | `rule_based` | `methods/deterministic/rule_based.py` (`_parse_clause`, `run`, `contract_answer`) |
| Structured prompting | `llm_only_structured` | `methods/prompting/prompt_variants.py` (`build_messages`), `methods/prompting/llm_only.py` (case tables), `evaluation/runner.py` (`evaluate_item`, kind `llm_only`) |
| Chain-of-thought prompting | `llm_only_cot` | same as structured, with the reasoning section from `methods/_shared/` |
| Plan-and-Act | `plan_act_nogate` | `methods/agent/engine.py` (`LLMEngine._run_plan_act`, planner prompt from `methods/plan_act_nogate/`) |
| ReAct | `react_nogate` | `methods/agent/engine.py` (`LLMEngine._run_react`) |
| PFAgent | `pfagent` | `methods/agent/engine.py` (`LLMEngine._run_react` + `verify_final_answer`, the gate V1 to V7) |

Every method with tools calls the same twelve tools through `methods/agent/tools.py` (`ToolDispatcher`,
`build_default_dispatcher`); the tool schemas and the text catalogue the no-tools methods read come
from the same table there (`TOOLS_LOAD_SPLIT`, `tools_catalog_text`). Every method returns the same
answer object (`methods/_shared/output_contract.txt`) and is scored by `evaluation/common_eval.py`
(`score_common`).

### Packages

- `methods/agent/`: `engine.py` (the loop, the gate, the plan parser), `tools.py` (tools, dispatcher, rounding of
  outputs), `prompts.py` (agent system prompt loader).
- `methods/prompting/`: `llm_only.py` (case tables, `BaselineParsed`, `evaluate_against_truth_extended`),
  `prompt_variants.py` (assembles system and user messages for every prompting strategy),
  `prompts_baseline.py` (loads the prompting texts).
- `methods/deterministic/`: the regex parser.
- `solver/`: `case_loader.py`, `power_flow.py`, `contingency.py`, `remedial.py`, `net_ops.py`, `validators.py`,
  `schemas.py` (Pydantic: `PowerFlowResult`, `N1Report`, `SessionState`), `llm_only_schema.py` and `llm_pf.py`
  (the archived hand-Newton-Raphson method).
- `evaluation/`: `requests.py` (seeded scenarios with reference calls and reference solution), `runner.py`
  (one method, one model, one system: writes `raw/report.json` and traces), `scoring.py` and `metrics.py`
  (formulation comparator R0 to R10, V6 argument grounding, traceable numbers), `common_eval.py` (the
  verdict), `rescore.py` (offline re-scoring of a report), `postprocess.py` (transcripts, narratives,
  figures, REPORT.md), `trace_figures.py`, `compare_runs.py`, `design_page.py`.
- `methods/`: only text. `methods/__init__.py` is the registry (`list_methods`, `system_prompt_for`);
  `methods/_archive/` keeps the variants outside the design.
- `results/`: one folder per run, everything tracked. `results/visuals/`: the pages.
- `ui/` and `viz/`: the Streamlit app and its figures; `viz/network_plot.py` is also used by the
  `generate_plot` tool.

### Data flow of one run

`run.py run` builds the command for `evaluation/runner.py`, which generates the requests
(`evaluation/requests.py`), loads the perturbed system (`perturbed_case`), runs the method through the
engine or the prompting path, scores each item (`score_common`), and writes `raw/`. `run.py` then calls
`evaluation/rescore.py` (recomputes verdicts offline) and `evaluation/postprocess.py` (renders the
folder). `results/INDEX.md` is rebuilt at the end.

### Bus ids

MATPOWER numbers everywhere: `solver/power_flow._bus_display_id` (the `name` column when numeric,
else row index + 1). The tools, the reference calls, and the prompting tables all use it; the
300-bus system keeps MATPOWER's numbering with gaps.

# PFAgent: where things are

One request in plain English, six ways to answer it, one evaluator. This file says where each
piece lives. The evaluation design itself (methods, prompts, answer object, scoring, run plan) is
`results/visuals/design.html`, built by `evaluation/design_page.py`; open it with `run.py serve`.

## The six methods and their code

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

## Packages

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

## Data flow of one run

`run.py run` builds the command for `evaluation/runner.py`, which generates the requests
(`evaluation/requests.py`), loads the perturbed system (`perturbed_case`), runs the method through the
engine or the prompting path, scores each item (`score_common`), and writes `raw/`. `run.py` then calls
`evaluation/rescore.py` (recomputes verdicts offline) and `evaluation/postprocess.py` (renders the
folder). `results/INDEX.md` is rebuilt at the end.

## Bus ids

MATPOWER numbers everywhere: `solver/power_flow._bus_display_id` (the `name` column when numeric,
else row index + 1). The tools, the reference calls, and the prompting tables all use it; the
300-bus system keeps MATPOWER's numbering with gaps.

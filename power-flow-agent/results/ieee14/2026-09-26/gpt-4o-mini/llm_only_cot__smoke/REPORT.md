# llm_only:cot on IEEE 14-bus with gpt-4o-mini

Generated 2026-09-26 21:23 by evaluation/postprocess.py from `report.rescored.json`. Runs: 3. Scored by the unified evaluator (v2): every verdict below is read from the answer JSON, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-26 |
| model | openrouter:openai/gpt-4o-mini |
| method | llm_only:cot |
| case | case14 |
| condition | normal |
| n | 3 |
| seed | 0 |
| k | 1 |
| max_rounds | 8 |
| tool_variant | load_split |
| plan_variant | text |
| temperature | 0.0 |
| system_prompt_hash | be09b0a3b7d2 |
| description | LLM answers from the case tables in the prompt. No tools. Structured prompt plus a reasoning section asking for step-by-step reasoning before the final JSON. |
| prompt files | _shared/llm_only_system_prompt.txt, _shared/llm_only_user_template.txt, _shared/llm_only_bus_id_note.txt, _shared/cot_system_suffix.txt, llm_only_cot/reasoning_section.txt |

![overview of the runs](overview.png)

One row per request, one cell per step (blue LLM call, teal tool call, purple planner, gold verification; green or red edge is the gate verdict), then formulation and where the request ended. Each run also has its own figure next to its traces: `traces/NN_<request>.png`.

## Where every request ended

The three outcomes are exclusive and sum to the run count. Escalation takes precedence: a run the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 0 | 0.0% |
| Escalated to a person | 0 | 0.0% |
| Wrong, unflagged | 3 | 100.0% |
| **Total** | **3** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Formulation exact | 3/3 (100.0%) |
| Task utility | Voltage MAE, all runs | 0.03 p.u. |
| Task utility | Voltage MAE, formulation-exact runs | 0.03 p.u. |
| Task utility | Flow MAE, all runs | 19.42 MW |
| Task utility | Flow MAE, formulation-exact runs | 19.42 MW |
| Task utility | KCL mismatch, mean | 16.1248 MW |
| Solver-grounded correctness | Solved (computation right, any path) | 0/3 (0.0%) |
| Solver-grounded correctness | V-pass (all conditions, offline) | 0/3 (0.0%) |
| Reporting | Traceable answers | 0/3 (0.0%) |
| Reporting | Traceable numbers, mean share | 0.152 |
| Reporting | Stale state quoted | 0/3 |
| Cost and time | LLM calls / tool calls, mean | 1 / 0 |
| Cost and time | Prompt / completion tokens, mean | 3256 / 1487 |
| Cost and time | Cost, total | $0.0041 |
| Cost and time | Wall time, mean | 14.7 s |

### Cross-check against the runner's own scoreboard

Values the runner aggregated for the same rows (report.json scoreboard). They should agree with the table above; a disagreement means the rows were filtered differently.

| metric | runner scoreboard | this report |
|---|---:|---:|
| common_solved_count | 0 | 0 |
| common_escalated_count | 0 | 0 |
| common_wrong_count | 3 | 3 |
| common_formulation_count | 3 | 3 |
| common_traceable_count | 0 | 0 |
| common_n | 3 | 3 |

## By request difficulty

| difficulty | n | solved | escalated | wrong unflagged | formulation exact |
|---|---:|---:|---:|---:|---:|
| ambiguous | 1 | 0 | 0 | 1 | 1 |
| multistep | 1 | 0 | 0 | 1 | 1 |
| parameterized | 1 | 0 | 0 | 1 | 1 |

## Wrong and unflagged (3)

- `case14-ambiguous-002-s0` formulation exact; declared:  ([narrative](traces/01_case14-ambiguous-002-s0.narrative.txt), [transcript](traces/01_case14-ambiguous-002-s0.transcript.txt))
- `case14-multistep-001-s0` formulation exact; declared:  ([narrative](traces/02_case14-multistep-001-s0.narrative.txt), [transcript](traces/02_case14-multistep-001-s0.transcript.txt))
- `case14-parameterized-000-s0` formulation exact; declared:  ([narrative](traces/03_case14-parameterized-000-s0.narrative.txt), [transcript](traces/03_case14-parameterized-000-s0.transcript.txt))

## Untraceable numbers in the answer (3)

- `case14-ambiguous-002-s0` 64 of 64 numbers; values ['36.68 MW', '191.57 MW', '0.0 MW', '1.06', '0.0', '1.045', '-0.0', '1.01', '-0.0', '-0.0', '-0.0', '1.07', '-0.0', '-0.0', '1.09', '-0.0', '-0.0', '-0.0', '-0.0', '-0.0']  ([narrative](traces/01_case14-ambiguous-002-s0.narrative.txt), [transcript](traces/01_case14-ambiguous-002-s0.transcript.txt))
- `case14-multistep-001-s0` 67 of 67 numbers; values ['0.9345 p.u.', '1.06', '0.0', '1.045', '-4.0', '1.01', '-6.0', '-8.0', '-10.0', '1.07', '-2.0', '-1.0', '1.09', '-3.0', '-5.0', '-7.0', '-9.0', '0.9345', '-11.0', '-12.0']  ([narrative](traces/02_case14-multistep-001-s0.narrative.txt), [transcript](traces/02_case14-multistep-001-s0.transcript.txt))
- `case14-parameterized-000-s0` 61 of 61 numbers; values ['1.06', '0.0', '1.045', '-2.0', '1.01', '-5.0', '1.0', '-10.0', '1.0', '-15.0', '1.07', '-20.0', '1.0', '-25.0', '1.09', '-30.0', '1.0', '-35.0', '1.0', '-40.0']  ([narrative](traces/03_case14-parameterized-000-s0.narrative.txt), [transcript](traces/03_case14-parameterized-000-s0.transcript.txt))

## Files

- `summary.csv`: one line per run, the fields above plus tokens and time.
- `traces/NN_<request>.narrative.txt`: what happened in each run, step by step, with the verdicts.
- `traces/NN_<request>.transcript.txt`: the raw exchange, every message, tool call and tool output.
- `traces/NN_<request>.png`: the run as a picture: steps, gate verdicts, formulation, verification, outcome, with a two-line narrative.
- `overview.png`: all runs of this folder on one page.
- `traces/NN_<request>.json`: the raw trace the runner wrote.
- `raw/`: the runner's own outputs (report.json, rescored report, logs).
- `requests.jsonl`: the request set, with the intended tool calls that define formulation exactness.

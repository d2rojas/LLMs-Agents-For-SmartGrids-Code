# plan_act_nogate on IEEE 14-bus with gpt-5.6-sol

Generated 2026-09-28 10:15 by evaluation/postprocess.py from `report.rescored.json`. Runs: 20. Scored by the unified evaluator (v2): every verdict below is read from the answer JSON, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-28 |
| model | openrouter:openai/gpt-5.6-sol |
| method | plan_act_nogate |
| case | case14 |
| condition | normal |
| n | 20 |
| seed | 0 |
| k | 1 |
| max_rounds | 8 |
| tool_variant | load_split |
| plan_variant | text |
| temperature | 0.0 |
| system_prompt_hash | 43ef7eaadb12 |
| description | Plan-and-Act with no gate. |
| prompt files | _shared/agent_system_prompt.txt, _shared/final_answer_instruction.txt, plan_act_nogate/plan_system_prompt_prefix.txt, plan_act_nogate/plan_system_prompt_structured.txt |

![overview of the runs](overview.png)

One row per request, one cell per step (blue LLM call, teal tool call, purple planner, gold verification; green or red edge is the gate verdict), then formulation and where the request ended. Each run also has its own figure next to its traces: `traces/NN_<request>.png`.

## Where every request ended

The three outcomes are exclusive and sum to the run count. Escalation takes precedence: a run the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 18 | 90.0% |
| Escalated to a person | 0 | 0.0% |
| Wrong, unflagged | 2 | 10.0% |
| **Total** | **20** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Formulation exact | 18/20 (90.0%) |
| Task utility | Formulation error types | declared_differs_from_executed: 2 |
| Task utility | Voltage MAE, all runs | 1.61e-07 p.u. |
| Task utility | Voltage MAE, formulation-exact runs | 1.60e-07 p.u. |
| Task utility | Flow MAE, all runs | 2.39e-04 MW |
| Task utility | Flow MAE, formulation-exact runs | 2.40e-04 MW |
| Task utility | KCL mismatch, mean | 2.15e-04 MW |
| Solver-grounded correctness | Solved (computation right, any path) | 18/20 (90.0%) |
| Solver-grounded correctness | V-pass (all conditions, offline) | 20/20 (100.0%) |
| Reporting | Traceable answers | 20/20 (100.0%) |
| Reporting | Traceable numbers, mean share | 1 |
| Reporting | Stale state quoted | 0/20 |
| Cost and time | LLM calls / tool calls, mean | 2 / 3.2 |
| Cost and time | Prompt / completion tokens, mean | 5755 / 1657 |
| Cost and time | Cost, total | $0.5617 |
| Cost and time | Wall time, mean | 16.7 s |

### Cross-check against the runner's own scoreboard

Values the runner aggregated for the same rows (report.json scoreboard). They should agree with the table above; a disagreement means the rows were filtered differently.

| metric | runner scoreboard | this report |
|---|---:|---:|
| common_solved_count | 18 | 18 |
| common_escalated_count | 0 | 0 |
| common_wrong_count | 2 | 2 |
| common_formulation_count | 18 | 18 |
| common_traceable_count | 20 | 20 |
| common_n | 20 | 20 |

## By request difficulty

| difficulty | n | solved | escalated | wrong unflagged | formulation exact |
|---|---:|---:|---:|---:|---:|
| ambiguous | 5 | 5 | 0 | 0 | 5 |
| multistep | 5 | 5 | 0 | 0 | 5 |
| parameterized | 5 | 5 | 0 | 0 | 5 |
| plain | 5 | 3 | 0 | 2 | 3 |

## Wrong and unflagged (2)

- `case14-plain-004-s0` formulation declared_differs_from_executed; the answer declares operations that differ from the ones the trace shows: run_n1_contingency: top_k intended 1 != executed 5  ([narrative](traces/17_case14-plain-004-s0.narrative.txt), [transcript](traces/17_case14-plain-004-s0.transcript.txt))
- `case14-plain-016-s0` formulation declared_differs_from_executed; the answer declares operations that differ from the ones the trace shows: run_n1_contingency: top_k intended 1 != executed 5  ([narrative](traces/20_case14-plain-016-s0.narrative.txt), [transcript](traces/20_case14-plain-016-s0.transcript.txt))

## Formulation not exact (2)

- `case14-plain-004-s0` declared_differs_from_executed: the answer declares operations that differ from the ones the trace shows: run_n1_contingency: top_k intended 1 != executed 5  ([narrative](traces/17_case14-plain-004-s0.narrative.txt), [transcript](traces/17_case14-plain-004-s0.transcript.txt))
- `case14-plain-016-s0` declared_differs_from_executed: the answer declares operations that differ from the ones the trace shows: run_n1_contingency: top_k intended 1 != executed 5  ([narrative](traces/20_case14-plain-016-s0.narrative.txt), [transcript](traces/20_case14-plain-016-s0.transcript.txt))

## Files

- `summary.csv`: one line per run, the fields above plus tokens and time.
- `traces/NN_<request>.narrative.txt`: what happened in each run, step by step, with the verdicts.
- `traces/NN_<request>.transcript.txt`: the raw exchange, every message, tool call and tool output.
- `traces/NN_<request>.png`: the run as a picture: steps, gate verdicts, formulation, verification, outcome, with a two-line narrative.
- `overview.png`: all runs of this folder on one page.
- `traces/NN_<request>.json`: the raw trace the runner wrote.
- `raw/`: the runner's own outputs (report.json, rescored report, logs).
- `requests.jsonl`: the request set, with the intended tool calls that define formulation exactness.

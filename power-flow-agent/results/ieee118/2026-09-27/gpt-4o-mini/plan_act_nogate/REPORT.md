# plan_act_nogate on IEEE 118-bus with gpt-4o-mini

Generated 2026-09-28 10:15 by evaluation/postprocess.py from `report.rescored.json`. Runs: 20. Scored by the unified evaluator (v2): every verdict below is read from the answer JSON, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-27 |
| model | openrouter:openai/gpt-4o-mini |
| method | plan_act_nogate |
| case | case118 |
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
| Solved autonomously | 10 | 50.0% |
| Escalated to a person | 0 | 0.0% |
| Wrong, unflagged | 10 | 50.0% |
| **Total** | **20** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Formulation exact | 20/20 (100.0%) |
| Task utility | Voltage MAE, all runs | 0.0075 p.u. |
| Task utility | Voltage MAE, formulation-exact runs | 0.0075 p.u. |
| Task utility | Flow MAE, all runs | 1.3556 MW |
| Task utility | Flow MAE, formulation-exact runs | 1.3556 MW |
| Task utility | KCL mismatch, mean | 0.028 MW |
| Solver-grounded correctness | Solved (computation right, any path) | 10/20 (50.0%) |
| Solver-grounded correctness | V-pass (all conditions, offline) | 16/20 (80.0%) |
| Reporting | Traceable answers | 16/20 (80.0%) |
| Reporting | Traceable numbers, mean share | 0.859 |
| Reporting | Stale state quoted | 0/20 |
| Cost and time | LLM calls / tool calls, mean | 2 / 3.15 |
| Cost and time | Prompt / completion tokens, mean | 14357 / 6168 |
| Cost and time | Cost, total | $0.1171 |
| Cost and time | Wall time, mean | 51.8 s |

### Cross-check against the runner's own scoreboard

Values the runner aggregated for the same rows (report.json scoreboard). They should agree with the table above; a disagreement means the rows were filtered differently.

| metric | runner scoreboard | this report |
|---|---:|---:|
| common_solved_count | 10 | 10 |
| common_escalated_count | 0 | 0 |
| common_wrong_count | 10 | 10 |
| common_formulation_count | 20 | 20 |
| common_traceable_count | 16 | 16 |
| common_n | 20 | 20 |

## By request difficulty

| difficulty | n | solved | escalated | wrong unflagged | formulation exact |
|---|---:|---:|---:|---:|---:|
| ambiguous | 5 | 4 | 0 | 1 | 5 |
| multistep | 5 | 2 | 0 | 3 | 5 |
| parameterized | 5 | 3 | 0 | 2 | 5 |
| plain | 5 | 1 | 0 | 4 | 5 |

## Wrong and unflagged (10)

- `case118-ambiguous-011-s0` formulation exact; declared:  ([narrative](traces/03_case118-ambiguous-011-s0.narrative.txt), [transcript](traces/03_case118-ambiguous-011-s0.transcript.txt))
- `case118-multistep-006-s0` formulation exact; declared:  ([narrative](traces/07_case118-multistep-006-s0.narrative.txt), [transcript](traces/07_case118-multistep-006-s0.transcript.txt))
- `case118-multistep-010-s0` formulation exact; declared:  ([narrative](traces/08_case118-multistep-010-s0.narrative.txt), [transcript](traces/08_case118-multistep-010-s0.transcript.txt))
- `case118-multistep-018-s0` formulation exact; declared:  ([narrative](traces/10_case118-multistep-018-s0.narrative.txt), [transcript](traces/10_case118-multistep-018-s0.transcript.txt))
- `case118-parameterized-009-s0` formulation exact; declared:  ([narrative](traces/13_case118-parameterized-009-s0.narrative.txt), [transcript](traces/13_case118-parameterized-009-s0.transcript.txt))
- `case118-parameterized-017-s0` formulation exact; declared:  ([narrative](traces/15_case118-parameterized-017-s0.narrative.txt), [transcript](traces/15_case118-parameterized-017-s0.transcript.txt))
- `case118-plain-004-s0` formulation exact; declared:  ([narrative](traces/17_case118-plain-004-s0.narrative.txt), [transcript](traces/17_case118-plain-004-s0.transcript.txt))
- `case118-plain-008-s0` formulation exact; declared:  ([narrative](traces/18_case118-plain-008-s0.narrative.txt), [transcript](traces/18_case118-plain-008-s0.transcript.txt))
- `case118-plain-012-s0` formulation exact; declared:  ([narrative](traces/19_case118-plain-012-s0.narrative.txt), [transcript](traces/19_case118-plain-012-s0.transcript.txt))
- `case118-plain-016-s0` formulation exact; declared:  ([narrative](traces/20_case118-plain-016-s0.narrative.txt), [transcript](traces/20_case118-plain-016-s0.transcript.txt))

## Untraceable numbers in the answer (4)

- `case118-parameterized-009-s0` 3 of 3 numbers; values ['0.0', '0.0', '0.0']  ([narrative](traces/13_case118-parameterized-009-s0.narrative.txt), [transcript](traces/13_case118-parameterized-009-s0.transcript.txt))
- `case118-plain-004-s0` 3 of 3 numbers; values ['0.0', '0.0', '0.0']  ([narrative](traces/17_case118-plain-004-s0.narrative.txt), [transcript](traces/17_case118-plain-004-s0.transcript.txt))
- `case118-plain-008-s0` 2 of 9 numbers; values ['1.06', '1.06']  ([narrative](traces/18_case118-plain-008-s0.narrative.txt), [transcript](traces/18_case118-plain-008-s0.transcript.txt))
- `case118-plain-012-s0` 3 of 5 numbers; values ['0.0', '0.0', '0.0']  ([narrative](traces/19_case118-plain-012-s0.narrative.txt), [transcript](traces/19_case118-plain-012-s0.transcript.txt))

## Files

- `summary.csv`: one line per run, the fields above plus tokens and time.
- `traces/NN_<request>.narrative.txt`: what happened in each run, step by step, with the verdicts.
- `traces/NN_<request>.transcript.txt`: the raw exchange, every message, tool call and tool output.
- `traces/NN_<request>.png`: the run as a picture: steps, gate verdicts, formulation, verification, outcome, with a two-line narrative.
- `overview.png`: all runs of this folder on one page.
- `traces/NN_<request>.json`: the raw trace the runner wrote.
- `raw/`: the runner's own outputs (report.json, rescored report, logs).
- `requests.jsonl`: the request set, with the intended tool calls that define formulation exactness.

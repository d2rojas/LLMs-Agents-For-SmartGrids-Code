# plan_act_nogate on IEEE 300-bus with gpt-4o-mini

Generated 2026-09-28 13:11 by evaluation/postprocess.py from `report.rescored.json`. Runs: 20. Scored by the unified evaluator (v2): every verdict below is read from the answer JSON, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-28 |
| model | openrouter:openai/gpt-4o-mini |
| method | plan_act_nogate |
| case | case300 |
| condition | normal |
| n | 20 |
| seed | 0 |
| k | 1 |
| max_rounds | 8 |
| tool_variant | load_split |
| plan_variant | text |
| temperature | 0.0 |
| system_prompt_hash | 43ef7eaadb12 |
| description | Plan-and-Act with no gate. Replans on failure: when a planned step errors or a solve does not converge, one reasoning call revises the remaining plan and execution resumes, at most twice (EngineConfig.max_replans, main.tex Sec. 4). |
| prompt files | _shared/agent_system_prompt.txt, _shared/final_answer_instruction.txt, plan_act_nogate/plan_system_prompt_prefix.txt, plan_act_nogate/plan_system_prompt_structured.txt, plan_act_nogate/replan_instruction.txt |

![overview of the runs](overview.png)

One row per request, one cell per step (blue LLM call, teal tool call, purple planner, gold verification; green or red edge is the gate verdict), then formulation and where the request ended. Each run also has its own figure next to its traces: `traces/NN_<request>.png`.

## Where every request ended

The three outcomes are exclusive and cover every request the method answered. Escalation takes precedence: a run the method handed to a person is not an autonomous answer, right or wrong. A request whose API call failed never reached an answer, so it is listed apart and excluded from the rates.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 0 | 0.0% |
| Escalated to a person | 5 | 25.0% |
| Wrong, unflagged | 15 | 75.0% |
| **Total** | **20** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Formulation exact | 20/20 (100.0%) |
| Task utility | Voltage MAE, all runs | 0.0033 p.u. |
| Task utility | Voltage MAE, formulation-exact runs | 0.0033 p.u. |
| Task utility | Flow MAE, all runs | 2.46e-04 MW |
| Task utility | Flow MAE, formulation-exact runs | 2.46e-04 MW |
| Task utility | KCL mismatch, mean | 2.62e-06 MW |
| Solver-grounded correctness | Solved (computation right, any path) | 0/20 (0.0%) |
| Solver-grounded correctness | V-pass (all conditions, offline) | 19/20 (95.0%) |
| Reporting | Traceable answers | 19/20 (95.0%) |
| Reporting | Traceable numbers, mean share | 0.97 |
| Reporting | Stale state quoted | 0/20 |
| Cost and time | LLM calls / tool calls, mean | 2 / 3.15 |
| Cost and time | Prompt / completion tokens, mean | 28017 / 5124 |
| Cost and time | Cost, total | $0.1455 |
| Cost and time | Wall time, mean | 59.6 s |

### Cross-check against the runner's own scoreboard

Values the runner aggregated for the same rows (report.json scoreboard). They should agree with the table above; a disagreement means the rows were filtered differently.

| metric | runner scoreboard | this report |
|---|---:|---:|
| common_solved_count | 0 | 0 |
| common_escalated_count | 5 | 5 |
| common_wrong_count | 15 | 15 |
| common_formulation_count | 20 | 20 |
| common_traceable_count | 19 | 19 |
| common_n | 20 | 20 |

## By request difficulty

| difficulty | n | solved | escalated | wrong unflagged | formulation exact |
|---|---:|---:|---:|---:|---:|
| ambiguous | 5 | 0 | 0 | 5 | 5 |
| multistep | 5 | 0 | 0 | 5 | 5 |
| parameterized | 5 | 0 | 3 | 2 | 5 |
| plain | 5 | 0 | 2 | 3 | 5 |

## Wrong and unflagged (15)

- `case300-ambiguous-003-s0` formulation exact; declared:  ([narrative](traces/01_case300-ambiguous-003-s0.narrative.txt), [transcript](traces/01_case300-ambiguous-003-s0.transcript.txt))
- `case300-ambiguous-007-s0` formulation exact; declared:  ([narrative](traces/02_case300-ambiguous-007-s0.narrative.txt), [transcript](traces/02_case300-ambiguous-007-s0.transcript.txt))
- `case300-ambiguous-011-s0` formulation exact; declared:  ([narrative](traces/03_case300-ambiguous-011-s0.narrative.txt), [transcript](traces/03_case300-ambiguous-011-s0.transcript.txt))
- `case300-ambiguous-015-s0` formulation exact; declared:  ([narrative](traces/04_case300-ambiguous-015-s0.narrative.txt), [transcript](traces/04_case300-ambiguous-015-s0.transcript.txt))
- `case300-ambiguous-019-s0` formulation exact; declared:  ([narrative](traces/05_case300-ambiguous-019-s0.narrative.txt), [transcript](traces/05_case300-ambiguous-019-s0.transcript.txt))
- `case300-multistep-002-s0` formulation exact; declared:  ([narrative](traces/06_case300-multistep-002-s0.narrative.txt), [transcript](traces/06_case300-multistep-002-s0.transcript.txt))
- `case300-multistep-006-s0` formulation exact; declared:  ([narrative](traces/07_case300-multistep-006-s0.narrative.txt), [transcript](traces/07_case300-multistep-006-s0.transcript.txt))
- `case300-multistep-010-s0` formulation exact; declared:  ([narrative](traces/08_case300-multistep-010-s0.narrative.txt), [transcript](traces/08_case300-multistep-010-s0.transcript.txt))
- `case300-multistep-014-s0` formulation exact; declared:  ([narrative](traces/09_case300-multistep-014-s0.narrative.txt), [transcript](traces/09_case300-multistep-014-s0.transcript.txt))
- `case300-multistep-018-s0` formulation exact; declared:  ([narrative](traces/10_case300-multistep-018-s0.narrative.txt), [transcript](traces/10_case300-multistep-018-s0.transcript.txt))
- `case300-parameterized-005-s0` formulation exact; declared:  ([narrative](traces/12_case300-parameterized-005-s0.narrative.txt), [transcript](traces/12_case300-parameterized-005-s0.transcript.txt))
- `case300-parameterized-013-s0` formulation exact; declared:  ([narrative](traces/14_case300-parameterized-013-s0.narrative.txt), [transcript](traces/14_case300-parameterized-013-s0.transcript.txt))
- `case300-plain-000-s0` formulation exact; declared:  ([narrative](traces/16_case300-plain-000-s0.narrative.txt), [transcript](traces/16_case300-plain-000-s0.transcript.txt))
- `case300-plain-008-s0` formulation exact; declared:  ([narrative](traces/18_case300-plain-008-s0.narrative.txt), [transcript](traces/18_case300-plain-008-s0.transcript.txt))
- `case300-plain-012-s0` formulation exact; declared:  ([narrative](traces/19_case300-plain-012-s0.narrative.txt), [transcript](traces/19_case300-plain-012-s0.transcript.txt))

## Escalated (5)

- `case300-parameterized-001-s0` detected via cannot_answer, abstention_json; formulation exact; declared:  ([narrative](traces/11_case300-parameterized-001-s0.narrative.txt), [transcript](traces/11_case300-parameterized-001-s0.transcript.txt))
- `case300-parameterized-009-s0` detected via abstention_json; formulation exact; declared:  ([narrative](traces/13_case300-parameterized-009-s0.narrative.txt), [transcript](traces/13_case300-parameterized-009-s0.transcript.txt))
- `case300-parameterized-017-s0` detected via cannot_answer, abstention_json; formulation exact; declared:  ([narrative](traces/15_case300-parameterized-017-s0.narrative.txt), [transcript](traces/15_case300-parameterized-017-s0.transcript.txt))
- `case300-plain-004-s0` detected via cannot_answer, abstention_json; formulation exact; declared:  ([narrative](traces/17_case300-plain-004-s0.narrative.txt), [transcript](traces/17_case300-plain-004-s0.transcript.txt))
- `case300-plain-016-s0` detected via cannot_answer, abstention_json; formulation exact; declared:  ([narrative](traces/20_case300-plain-016-s0.narrative.txt), [transcript](traces/20_case300-plain-016-s0.transcript.txt))

## Untraceable numbers in the answer (1)

- `case300-plain-012-s0` 3 of 5 numbers; values ['0.0', '0.0', '0.0']  ([narrative](traces/19_case300-plain-012-s0.narrative.txt), [transcript](traces/19_case300-plain-012-s0.transcript.txt))

## Files

- `summary.csv`: one line per run, the fields above plus tokens and time.
- `traces/NN_<request>.narrative.txt`: what happened in each run, step by step, with the verdicts.
- `traces/NN_<request>.transcript.txt`: the raw exchange, every message, tool call and tool output.
- `traces/NN_<request>.png`: the run as a picture: steps, gate verdicts, formulation, verification, outcome, with a two-line narrative.
- `overview.png`: all runs of this folder on one page.
- `traces/NN_<request>.json`: the raw trace the runner wrote.
- `raw/`: the runner's own outputs (report.json, rescored report, logs).
- `requests.jsonl`: the request set, with the intended tool calls that define formulation exactness.

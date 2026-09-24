# react_nogate on IEEE 14-bus with gpt-5.6-sol

Generated 2026-09-24 04:57 by benchmarks/postprocess.py from `report.rescored.json`. Runs: 40.

## Run

| field | value |
|---|---|
| date | 2026-09-21 |
| model | openrouter:openai/gpt-5.6-sol |
| method | react_nogate |
| case | case14 |
| condition | normal |
| n | 40 |
| seed | 0 |
| k | 1 |
| max_rounds | 8 |
| tool_variant | v1 |
| plan_variant | text |
| temperature | 0.0 |
| system_prompt_hash | 7da5e2a37ec4 |
| source | results_validation_sol_n40_clean/react_nogate/case14 |
| source_commit | f8fb5ef 2026-09-21 Re-rescore after the round-limit escalation fix; composite unaffected |
| role_in_paper | split-tool appendix, before side (original modify_load tool) |
| notes | Copied from benchmarks/results_* by scripts/migrate_paper_results.py; the date is the write time of the source report.json. |
| description | ReAct loop with no gate at all. The plain multi-step agent baseline. |
| prompt files | _shared/agent_system_prompt.txt, _shared/final_answer_instruction.txt |

![overview of the runs](overview.png)

One row per request, one cell per step (blue LLM call, teal tool call, purple planner, gold verification; green or red edge is the gate verdict), then formulation and where the request ended. Each run also has its own figure next to its traces: `traces/NN_<request>.png`.

## Where every request ended

The three outcomes are exclusive and sum to the run count. Escalation takes precedence: a run the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 25 | 62.5% |
| Escalated to a person | 0 | 0.0% |
| Wrong, unflagged | 15 | 37.5% |
| **Total** | **40** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Formulation exact | 25/40 (62.5%) |
| Task utility | Formulation error types | extra_arg_changes_result: 14, extra_step: 1 |
| Task utility | Voltage MAE, all runs | 1.65e-05 p.u. |
| Task utility | Voltage MAE, formulation-exact runs | 0 p.u. |
| Task utility | Flow MAE, all runs | 0.0012 MW |
| Task utility | Flow MAE, formulation-exact runs | 0 MW |
| Task utility | KCL mismatch, mean | 0 MW |
| Solver-grounded correctness | Solved (computation right, any path) | 25/40 (62.5%) |
| Solver-grounded correctness | V-pass (all conditions, offline) | 36/40 (90.0%) |
| Reporting | Traceable answers | 36/40 (90.0%) |
| Reporting | Traceable numbers, mean share | 0.988 |
| Reporting | Stale state quoted | 1/40 |
| Cost and time | LLM calls / tool calls, mean | 4.1 / 3.12 |
| Cost and time | Prompt / completion tokens, mean | 12934 / 532 |
| Cost and time | Cost, total | $1.2474 |
| Cost and time | Wall time, mean | 34.9 s |

### Cross-check against the runner's own scoreboard

Values the runner aggregated for the same rows (report.json scoreboard). They should agree with the table above; a disagreement means the rows were filtered differently.

| metric | runner scoreboard | this report |
|---|---:|---:|
| solved_autonomously_count | 25 | 25 |
| escalated_count | 0 | 0 |
| wrong_silently_count | 15 | 15 |
| formulation_exact_count | 25 | 25 |
| v_pass_count | 36 | 36 |
| faithful_answers_count | 36 | 36 |
| n_items | 40 | 40 |

## By request difficulty

| difficulty | n | solved | escalated | wrong unflagged | formulation exact |
|---|---:|---:|---:|---:|---:|
| ambiguous | 10 | 4 | 0 | 6 | 4 |
| multistep | 10 | 4 | 0 | 6 | 4 |
| parameterized | 10 | 9 | 0 | 1 | 9 |
| plain | 10 | 8 | 0 | 2 | 8 |

## Wrong and unflagged (15)

- `case14-ambiguous-011-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=7.5 changes the solver outcome (request did not ask for it)  ([narrative](traces/03_case14-ambiguous-011-s0.narrative.txt), [transcript](traces/03_case14-ambiguous-011-s0.transcript.txt))
- `case14-ambiguous-015-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=1.6 changes the solver outcome (request did not ask for it)  ([narrative](traces/04_case14-ambiguous-015-s0.narrative.txt), [transcript](traces/04_case14-ambiguous-015-s0.transcript.txt))
- `case14-ambiguous-023-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=1.6 changes the solver outcome (request did not ask for it)  ([narrative](traces/06_case14-ambiguous-023-s0.narrative.txt), [transcript](traces/06_case14-ambiguous-023-s0.transcript.txt))
- `case14-ambiguous-027-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=1.8 changes the solver outcome (request did not ask for it)  ([narrative](traces/07_case14-ambiguous-027-s0.narrative.txt), [transcript](traces/07_case14-ambiguous-027-s0.transcript.txt))
- `case14-ambiguous-035-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=1.6 changes the solver outcome (request did not ask for it)  ([narrative](traces/09_case14-ambiguous-035-s0.narrative.txt), [transcript](traces/09_case14-ambiguous-035-s0.transcript.txt))
- `case14-ambiguous-039-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=12.7 changes the solver outcome (request did not ask for it)  ([narrative](traces/10_case14-ambiguous-039-s0.narrative.txt), [transcript](traces/10_case14-ambiguous-039-s0.transcript.txt))
- `case14-multistep-006-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=-3.9 changes the solver outcome (request did not ask for it)  ([narrative](traces/12_case14-multistep-006-s0.narrative.txt), [transcript](traces/12_case14-multistep-006-s0.transcript.txt))
- `case14-multistep-014-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=5.8 changes the solver outcome (request did not ask for it)  ([narrative](traces/14_case14-multistep-014-s0.narrative.txt), [transcript](traces/14_case14-multistep-014-s0.transcript.txt))
- `case14-multistep-022-s0` formulation extra_step; unintended tools: ['modify_load']  ([narrative](traces/16_case14-multistep-022-s0.narrative.txt), [transcript](traces/16_case14-multistep-022-s0.transcript.txt))
- `case14-multistep-030-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=5.0 changes the solver outcome (request did not ask for it)  ([narrative](traces/18_case14-multistep-030-s0.narrative.txt), [transcript](traces/18_case14-multistep-030-s0.transcript.txt))
- `case14-multistep-034-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=16.6 changes the solver outcome (request did not ask for it)  ([narrative](traces/19_case14-multistep-034-s0.narrative.txt), [transcript](traces/19_case14-multistep-034-s0.transcript.txt))
- `case14-multistep-038-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=7.5 changes the solver outcome (request did not ask for it)  ([narrative](traces/20_case14-multistep-038-s0.narrative.txt), [transcript](traces/20_case14-multistep-038-s0.transcript.txt))
- `case14-parameterized-033-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=5.0 changes the solver outcome (request did not ask for it)  ([narrative](traces/29_case14-parameterized-033-s0.narrative.txt), [transcript](traces/29_case14-parameterized-033-s0.transcript.txt))
- `case14-plain-008-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=12.7 changes the solver outcome (request did not ask for it)  ([narrative](traces/33_case14-plain-008-s0.narrative.txt), [transcript](traces/33_case14-plain-008-s0.transcript.txt))
- `case14-plain-036-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=12.7 changes the solver outcome (request did not ask for it)  ([narrative](traces/40_case14-plain-036-s0.narrative.txt), [transcript](traces/40_case14-plain-036-s0.transcript.txt))

## Formulation not exact (15)

- `case14-ambiguous-011-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=7.5 changes the solver outcome (request did not ask for it)  ([narrative](traces/03_case14-ambiguous-011-s0.narrative.txt), [transcript](traces/03_case14-ambiguous-011-s0.transcript.txt))
- `case14-ambiguous-015-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=1.6 changes the solver outcome (request did not ask for it)  ([narrative](traces/04_case14-ambiguous-015-s0.narrative.txt), [transcript](traces/04_case14-ambiguous-015-s0.transcript.txt))
- `case14-ambiguous-023-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=1.6 changes the solver outcome (request did not ask for it)  ([narrative](traces/06_case14-ambiguous-023-s0.narrative.txt), [transcript](traces/06_case14-ambiguous-023-s0.transcript.txt))
- `case14-ambiguous-027-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=1.8 changes the solver outcome (request did not ask for it)  ([narrative](traces/07_case14-ambiguous-027-s0.narrative.txt), [transcript](traces/07_case14-ambiguous-027-s0.transcript.txt))
- `case14-ambiguous-035-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=1.6 changes the solver outcome (request did not ask for it)  ([narrative](traces/09_case14-ambiguous-035-s0.narrative.txt), [transcript](traces/09_case14-ambiguous-035-s0.transcript.txt))
- `case14-ambiguous-039-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=12.7 changes the solver outcome (request did not ask for it)  ([narrative](traces/10_case14-ambiguous-039-s0.narrative.txt), [transcript](traces/10_case14-ambiguous-039-s0.transcript.txt))
- `case14-multistep-006-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=-3.9 changes the solver outcome (request did not ask for it)  ([narrative](traces/12_case14-multistep-006-s0.narrative.txt), [transcript](traces/12_case14-multistep-006-s0.transcript.txt))
- `case14-multistep-014-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=5.8 changes the solver outcome (request did not ask for it)  ([narrative](traces/14_case14-multistep-014-s0.narrative.txt), [transcript](traces/14_case14-multistep-014-s0.transcript.txt))
- `case14-multistep-022-s0` extra_step: unintended tools: ['modify_load']  ([narrative](traces/16_case14-multistep-022-s0.narrative.txt), [transcript](traces/16_case14-multistep-022-s0.transcript.txt))
- `case14-multistep-030-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=5.0 changes the solver outcome (request did not ask for it)  ([narrative](traces/18_case14-multistep-030-s0.narrative.txt), [transcript](traces/18_case14-multistep-030-s0.transcript.txt))
- `case14-multistep-034-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=16.6 changes the solver outcome (request did not ask for it)  ([narrative](traces/19_case14-multistep-034-s0.narrative.txt), [transcript](traces/19_case14-multistep-034-s0.transcript.txt))
- `case14-multistep-038-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=7.5 changes the solver outcome (request did not ask for it)  ([narrative](traces/20_case14-multistep-038-s0.narrative.txt), [transcript](traces/20_case14-multistep-038-s0.transcript.txt))
- `case14-parameterized-033-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=5.0 changes the solver outcome (request did not ask for it)  ([narrative](traces/29_case14-parameterized-033-s0.narrative.txt), [transcript](traces/29_case14-parameterized-033-s0.transcript.txt))
- `case14-plain-008-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=12.7 changes the solver outcome (request did not ask for it)  ([narrative](traces/33_case14-plain-008-s0.narrative.txt), [transcript](traces/33_case14-plain-008-s0.transcript.txt))
- `case14-plain-036-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=12.7 changes the solver outcome (request did not ask for it)  ([narrative](traces/40_case14-plain-036-s0.narrative.txt), [transcript](traces/40_case14-plain-036-s0.transcript.txt))

## Untraceable numbers in the answer (4)

- `case14-ambiguous-011-s0` 1 of 7 numbers; values ['7.5 MVAr']  ([narrative](traces/03_case14-ambiguous-011-s0.narrative.txt), [transcript](traces/03_case14-ambiguous-011-s0.transcript.txt))
- `case14-ambiguous-035-s0` 1 of 7 numbers; values ['1.6 MVAr']  ([narrative](traces/09_case14-ambiguous-035-s0.narrative.txt), [transcript](traces/09_case14-ambiguous-035-s0.transcript.txt))
- `case14-multistep-030-s0` 0 of 15 numbers; values []  ([narrative](traces/18_case14-multistep-030-s0.narrative.txt), [transcript](traces/18_case14-multistep-030-s0.transcript.txt))
- `case14-plain-036-s0` 1 of 6 numbers; values ['12.7 MVAr']  ([narrative](traces/40_case14-plain-036-s0.narrative.txt), [transcript](traces/40_case14-plain-036-s0.transcript.txt))

## Files

- `summary.csv`: one line per run, the fields above plus tokens and time.
- `traces/NN_<request>.narrative.txt`: what happened in each run, step by step, with the verdicts.
- `traces/NN_<request>.transcript.txt`: the raw exchange, every message, tool call and tool output.
- `traces/NN_<request>.png`: the run as a picture: steps, gate verdicts, formulation, verification, outcome, with a two-line narrative.
- `overview.png`: all runs of this folder on one page.
- `traces/NN_<request>.json`: the raw trace the runner wrote.
- `raw/`: the runner's own outputs (report.json, rescored report, logs).
- `requests.jsonl`: the request set, with the intended tool calls that define formulation exactness.

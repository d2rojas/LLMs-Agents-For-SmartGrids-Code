# pfagent on IEEE 14-bus with gpt-5.4

Generated 2026-09-23 11:18 by benchmarks/postprocess.py from `report.rescored.json`. Runs: 40.

## Run

| field | value |
|---|---|
| date | 2026-09-16 |
| model | openrouter:openai/gpt-5.4 |
| method | pfagent |
| case | case14 |
| condition | normal |
| n | 40 |
| seed | 0 |
| k | 1 |
| max_rounds | 8 |
| temperature | 0.0 |
| system_prompt_hash | None |
| source | results_validation_n40/gpt-5.4/pfagent |
| source_commit | 46e27b8 2026-09-22 Backfill GPT-5.4's missing B_mean-solved from its own frozen data |
| role_in_paper | main protocol table (Table 5 / S8); split-tool appendix, before side (original modify_load tool) |
| notes | Copied from benchmarks/results_* by scripts/migrate_paper_results.py; the date is the write time of the source report.json. |
| description | PFAgent: ReAct loop with no in-loop gate plus the task-level verification gate V1-V7 on the final answer (llm/engine.py verify_final_answer). The solver-grounded row. |
| prompt files | _shared/agent_system_prompt.txt, _shared/final_answer_instruction.txt |

## Where every request ended

The three outcomes are exclusive and sum to the run count. Escalation takes precedence: a run the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 24 | 60.0% |
| Escalated to a person | 1 | 2.5% |
| Wrong, unflagged | 15 | 37.5% |
| **Total** | **40** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Formulation exact | 25/40 (62.5%) |
| Task utility | Formulation error types | extra_arg_changes_result: 13, missed_step: 1, wrong_id: 1 |
| Task utility | Voltage MAE, all runs | 3.17e-04 p.u. |
| Task utility | Voltage MAE, formulation-exact runs | 0 p.u. |
| Task utility | Flow MAE, all runs | 0.0568 MW |
| Task utility | Flow MAE, formulation-exact runs | 0 MW |
| Task utility | KCL mismatch, mean | 0.0083 MW |
| Solver-grounded correctness | Solved (computation right, any path) | 24/40 (60.0%) |
| Solver-grounded correctness | V-pass (all conditions, offline) | 40/40 (100.0%) |
| Reporting | Traceable answers | 40/40 (100.0%) |
| Reporting | Traceable numbers, mean share | 1 |
| Reporting | Stale state quoted | 0/40 |
| Cost and time | LLM calls / tool calls, mean | 3.9 / 2.83 |
| Cost and time | Prompt / completion tokens, mean | 13809 / 386 |
| Cost and time | Cost, total | $1.6125 |
| Cost and time | Wall time, mean | 7.4 s |

### Cross-check against the runner's own scoreboard

Values the runner aggregated for the same rows (report.json scoreboard). They should agree with the table above; a disagreement means the rows were filtered differently.

| metric | runner scoreboard | this report |
|---|---:|---:|
| solved_autonomously_count | 24 | 24 |
| escalated_count | 1 | 1 |
| wrong_silently_count | 15 | 15 |
| formulation_exact_count | 25 | 25 |
| v_pass_count | 40 | 40 |
| faithful_answers_count | 40 | 40 |
| n_items | 40 | 40 |

## By request difficulty

| difficulty | n | solved | escalated | wrong unflagged | formulation exact |
|---|---:|---:|---:|---:|---:|
| ambiguous | 10 | 4 | 0 | 6 | 4 |
| multistep | 10 | 3 | 1 | 6 | 4 |
| parameterized | 10 | 9 | 0 | 1 | 9 |
| plain | 10 | 8 | 0 | 2 | 8 |

## Wrong and unflagged (15)

- `case14-ambiguous-011-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=11.2 changes the solver outcome (request did not ask for it)  ([narrative](traces/03_case14-ambiguous-011-s0.narrative.txt), [transcript](traces/03_case14-ambiguous-011-s0.transcript.txt))
- `case14-ambiguous-015-s0` formulation missed_step; missing tools: ['modify_load']  ([narrative](traces/04_case14-ambiguous-015-s0.narrative.txt), [transcript](traces/04_case14-ambiguous-015-s0.transcript.txt))
- `case14-ambiguous-023-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=1.6 changes the solver outcome (request did not ask for it)  ([narrative](traces/06_case14-ambiguous-023-s0.narrative.txt), [transcript](traces/06_case14-ambiguous-023-s0.transcript.txt))
- `case14-ambiguous-027-s0` formulation wrong_id; modify_load: bus_id intended 11 != executed 10; modify_load: extra argument q_mvar=0.0 changes the solver outcome (request did not ask for it)  ([narrative](traces/07_case14-ambiguous-027-s0.narrative.txt), [transcript](traces/07_case14-ambiguous-027-s0.transcript.txt))
- `case14-ambiguous-035-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=0.0 changes the solver outcome (request did not ask for it)  ([narrative](traces/09_case14-ambiguous-035-s0.narrative.txt), [transcript](traces/09_case14-ambiguous-035-s0.transcript.txt))
- `case14-ambiguous-039-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=12.7 changes the solver outcome (request did not ask for it)  ([narrative](traces/10_case14-ambiguous-039-s0.narrative.txt), [transcript](traces/10_case14-ambiguous-039-s0.transcript.txt))
- `case14-multistep-006-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=-3.9 changes the solver outcome (request did not ask for it)  ([narrative](traces/12_case14-multistep-006-s0.narrative.txt), [transcript](traces/12_case14-multistep-006-s0.transcript.txt))
- `case14-multistep-010-s0` formulation exact  ([narrative](traces/13_case14-multistep-010-s0.narrative.txt), [transcript](traces/13_case14-multistep-010-s0.transcript.txt))
- `case14-multistep-014-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=13.5 changes the solver outcome (request did not ask for it)  ([narrative](traces/14_case14-multistep-014-s0.narrative.txt), [transcript](traces/14_case14-multistep-014-s0.transcript.txt))
- `case14-multistep-022-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=0.0 changes the solver outcome (request did not ask for it)  ([narrative](traces/16_case14-multistep-022-s0.narrative.txt), [transcript](traces/16_case14-multistep-022-s0.transcript.txt))
- `case14-multistep-034-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=0.0 changes the solver outcome (request did not ask for it)  ([narrative](traces/19_case14-multistep-034-s0.narrative.txt), [transcript](traces/19_case14-multistep-034-s0.transcript.txt))
- `case14-multistep-038-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=11.2 changes the solver outcome (request did not ask for it)  ([narrative](traces/20_case14-multistep-038-s0.narrative.txt), [transcript](traces/20_case14-multistep-038-s0.transcript.txt))
- `case14-parameterized-033-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=5.0 changes the solver outcome (request did not ask for it)  ([narrative](traces/29_case14-parameterized-033-s0.narrative.txt), [transcript](traces/29_case14-parameterized-033-s0.transcript.txt))
- `case14-plain-008-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=12.7 changes the solver outcome (request did not ask for it)  ([narrative](traces/33_case14-plain-008-s0.narrative.txt), [transcript](traces/33_case14-plain-008-s0.transcript.txt))
- `case14-plain-036-s0` formulation extra_arg_changes_result; modify_load: extra argument q_mvar=12.7 changes the solver outcome (request did not ask for it)  ([narrative](traces/40_case14-plain-036-s0.narrative.txt), [transcript](traces/40_case14-plain-036-s0.transcript.txt))

## Escalated (1)

- `case14-multistep-030-s0` detected via text; formulation extra_arg_changes_result; modify_load: extra argument q_mvar=0.0 changes the solver outcome (request did not ask for it)  ([narrative](traces/18_case14-multistep-030-s0.narrative.txt), [transcript](traces/18_case14-multistep-030-s0.transcript.txt))

## Formulation not exact (15)

- `case14-ambiguous-011-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=11.2 changes the solver outcome (request did not ask for it)  ([narrative](traces/03_case14-ambiguous-011-s0.narrative.txt), [transcript](traces/03_case14-ambiguous-011-s0.transcript.txt))
- `case14-ambiguous-015-s0` missed_step: missing tools: ['modify_load']  ([narrative](traces/04_case14-ambiguous-015-s0.narrative.txt), [transcript](traces/04_case14-ambiguous-015-s0.transcript.txt))
- `case14-ambiguous-023-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=1.6 changes the solver outcome (request did not ask for it)  ([narrative](traces/06_case14-ambiguous-023-s0.narrative.txt), [transcript](traces/06_case14-ambiguous-023-s0.transcript.txt))
- `case14-ambiguous-027-s0` wrong_id: modify_load: bus_id intended 11 != executed 10; modify_load: extra argument q_mvar=0.0 changes the solver outcome (request did not ask for it)  ([narrative](traces/07_case14-ambiguous-027-s0.narrative.txt), [transcript](traces/07_case14-ambiguous-027-s0.transcript.txt))
- `case14-ambiguous-035-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=0.0 changes the solver outcome (request did not ask for it)  ([narrative](traces/09_case14-ambiguous-035-s0.narrative.txt), [transcript](traces/09_case14-ambiguous-035-s0.transcript.txt))
- `case14-ambiguous-039-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=12.7 changes the solver outcome (request did not ask for it)  ([narrative](traces/10_case14-ambiguous-039-s0.narrative.txt), [transcript](traces/10_case14-ambiguous-039-s0.transcript.txt))
- `case14-multistep-006-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=-3.9 changes the solver outcome (request did not ask for it)  ([narrative](traces/12_case14-multistep-006-s0.narrative.txt), [transcript](traces/12_case14-multistep-006-s0.transcript.txt))
- `case14-multistep-014-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=13.5 changes the solver outcome (request did not ask for it)  ([narrative](traces/14_case14-multistep-014-s0.narrative.txt), [transcript](traces/14_case14-multistep-014-s0.transcript.txt))
- `case14-multistep-022-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=0.0 changes the solver outcome (request did not ask for it)  ([narrative](traces/16_case14-multistep-022-s0.narrative.txt), [transcript](traces/16_case14-multistep-022-s0.transcript.txt))
- `case14-multistep-030-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=0.0 changes the solver outcome (request did not ask for it)  ([narrative](traces/18_case14-multistep-030-s0.narrative.txt), [transcript](traces/18_case14-multistep-030-s0.transcript.txt))
- `case14-multistep-034-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=0.0 changes the solver outcome (request did not ask for it)  ([narrative](traces/19_case14-multistep-034-s0.narrative.txt), [transcript](traces/19_case14-multistep-034-s0.transcript.txt))
- `case14-multistep-038-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=11.2 changes the solver outcome (request did not ask for it)  ([narrative](traces/20_case14-multistep-038-s0.narrative.txt), [transcript](traces/20_case14-multistep-038-s0.transcript.txt))
- `case14-parameterized-033-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=5.0 changes the solver outcome (request did not ask for it)  ([narrative](traces/29_case14-parameterized-033-s0.narrative.txt), [transcript](traces/29_case14-parameterized-033-s0.transcript.txt))
- `case14-plain-008-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=12.7 changes the solver outcome (request did not ask for it)  ([narrative](traces/33_case14-plain-008-s0.narrative.txt), [transcript](traces/33_case14-plain-008-s0.transcript.txt))
- `case14-plain-036-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=12.7 changes the solver outcome (request did not ask for it)  ([narrative](traces/40_case14-plain-036-s0.narrative.txt), [transcript](traces/40_case14-plain-036-s0.transcript.txt))

## Files

- `summary.csv`: one line per run, the fields above plus tokens and time.
- `traces/NN_<request>.narrative.txt`: what happened in each run, step by step, with the verdicts.
- `traces/NN_<request>.transcript.txt`: the raw exchange, every message, tool call and tool output.
- `traces/NN_<request>.json`: the raw trace the runner wrote.
- `raw/`: the runner's own outputs (report.json, rescored report, logs).
- `requests.jsonl`: the request set, with the intended tool calls that define formulation exactness.

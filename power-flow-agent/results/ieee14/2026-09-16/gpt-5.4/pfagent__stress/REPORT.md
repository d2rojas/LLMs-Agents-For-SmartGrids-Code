# pfagent on IEEE 14-bus with gpt-5.4

Generated 2026-09-23 11:18 by benchmarks/postprocess.py from `report.rescored.json`. Runs: 10.

## Run

| field | value |
|---|---|
| date | 2026-09-16 |
| model | openrouter:openai/gpt-5.4 |
| method | pfagent |
| case | case14 |
| condition | stress |
| n | 10 |
| seed | 0 |
| k | 1 |
| max_rounds | 8 |
| temperature | 0.0 |
| system_prompt_hash | None |
| source | results_validation_gpt-5.4_stress |
| source_commit | 46e27b8 2026-09-22 Backfill GPT-5.4's missing B_mean-solved from its own frozen data |
| role_in_paper | stress table (S6) |
| notes | Copied from benchmarks/results_* by scripts/migrate_paper_results.py; the date is the write time of the source report.json. |
| description | PFAgent: ReAct loop with no in-loop gate plus the task-level verification gate V1-V7 on the final answer (llm/engine.py verify_final_answer). The solver-grounded row. |
| prompt files | _shared/agent_system_prompt.txt, _shared/final_answer_instruction.txt |

## Where every request ended

The three outcomes are exclusive and sum to the run count. Escalation takes precedence: a run the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 0 | 0.0% |
| Escalated to a person | 10 | 100.0% |
| Wrong, unflagged | 0 | 0.0% |
| **Total** | **10** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Formulation exact | 5/10 (50.0%) |
| Task utility | Formulation error types | extra_arg_changes_result: 5 |
| Task utility | Voltage MAE, all runs | nan p.u. |
| Task utility | Voltage MAE, formulation-exact runs | nan p.u. |
| Task utility | Flow MAE, all runs | 0.0067 MW |
| Task utility | Flow MAE, formulation-exact runs | 0 MW |
| Task utility | KCL mismatch, mean | 0 MW |
| Solver-grounded correctness | Solved (computation right, any path) | 5/10 (50.0%) |
| Solver-grounded correctness | V-pass (all conditions, offline) | 0/10 (0.0%) |
| Solver-grounded correctness | Safe failure on real failures | 10/10 (100.0%) |
| Reporting | Traceable answers | 10/10 (100.0%) |
| Reporting | Traceable numbers, mean share | n/a |
| Reporting | Stale state quoted | 0/10 |
| Cost and time | LLM calls / tool calls, mean | 5.7 / 3.9 |
| Cost and time | Prompt / completion tokens, mean | 23794 / 628 |
| Cost and time | Cost, total | $0.6890 |
| Cost and time | Wall time, mean | 12.7 s |

## Escalated (10)

- `case14-stress-000-s0` detected via text; formulation exact  ([narrative](traces/01_case14-stress-000-s0.narrative.txt), [transcript](traces/01_case14-stress-000-s0.transcript.txt))
- `case14-stress-000-s1` detected via text; formulation exact  ([narrative](traces/02_case14-stress-000-s1.narrative.txt), [transcript](traces/02_case14-stress-000-s1.transcript.txt))
- `case14-stress-001-s0` detected via text; formulation exact  ([narrative](traces/03_case14-stress-001-s0.narrative.txt), [transcript](traces/03_case14-stress-001-s0.transcript.txt))
- `case14-stress-001-s1` detected via text; formulation extra_arg_changes_result; modify_load: extra argument q_mvar=-3.9 changes the solver outcome (request did not ask for it)  ([narrative](traces/04_case14-stress-001-s1.narrative.txt), [transcript](traces/04_case14-stress-001-s1.transcript.txt))
- `case14-stress-002-s0` detected via text; formulation extra_arg_changes_result; modify_load: extra argument q_mvar=16.6 changes the solver outcome (request did not ask for it)  ([narrative](traces/05_case14-stress-002-s0.narrative.txt), [transcript](traces/05_case14-stress-002-s0.transcript.txt))
- `case14-stress-002-s1` detected via text; formulation extra_arg_changes_result; modify_load: extra argument q_mvar=-3.9 changes the solver outcome (request did not ask for it)  ([narrative](traces/06_case14-stress-002-s1.narrative.txt), [transcript](traces/06_case14-stress-002-s1.transcript.txt))
- `case14-stress-003-s0` detected via text; formulation exact  ([narrative](traces/07_case14-stress-003-s0.narrative.txt), [transcript](traces/07_case14-stress-003-s0.transcript.txt))
- `case14-stress-003-s1` detected via text; formulation exact  ([narrative](traces/08_case14-stress-003-s1.narrative.txt), [transcript](traces/08_case14-stress-003-s1.transcript.txt))
- `case14-stress-004-s0` detected via text; formulation extra_arg_changes_result; modify_load: extra argument q_mvar=-3.9 changes the solver outcome (request did not ask for it)  ([narrative](traces/09_case14-stress-004-s0.narrative.txt), [transcript](traces/09_case14-stress-004-s0.transcript.txt))
- `case14-stress-004-s1` detected via text; formulation extra_arg_changes_result; modify_load: extra argument q_mvar=-3.9 changes the solver outcome (request did not ask for it)  ([narrative](traces/10_case14-stress-004-s1.narrative.txt), [transcript](traces/10_case14-stress-004-s1.transcript.txt))

## Formulation not exact (5)

- `case14-stress-001-s1` extra_arg_changes_result: modify_load: extra argument q_mvar=-3.9 changes the solver outcome (request did not ask for it)  ([narrative](traces/04_case14-stress-001-s1.narrative.txt), [transcript](traces/04_case14-stress-001-s1.transcript.txt))
- `case14-stress-002-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=16.6 changes the solver outcome (request did not ask for it)  ([narrative](traces/05_case14-stress-002-s0.narrative.txt), [transcript](traces/05_case14-stress-002-s0.transcript.txt))
- `case14-stress-002-s1` extra_arg_changes_result: modify_load: extra argument q_mvar=-3.9 changes the solver outcome (request did not ask for it)  ([narrative](traces/06_case14-stress-002-s1.narrative.txt), [transcript](traces/06_case14-stress-002-s1.transcript.txt))
- `case14-stress-004-s0` extra_arg_changes_result: modify_load: extra argument q_mvar=-3.9 changes the solver outcome (request did not ask for it)  ([narrative](traces/09_case14-stress-004-s0.narrative.txt), [transcript](traces/09_case14-stress-004-s0.transcript.txt))
- `case14-stress-004-s1` extra_arg_changes_result: modify_load: extra argument q_mvar=-3.9 changes the solver outcome (request did not ask for it)  ([narrative](traces/10_case14-stress-004-s1.narrative.txt), [transcript](traces/10_case14-stress-004-s1.transcript.txt))

## Files

- `summary.csv`: one line per run, the fields above plus tokens and time.
- `traces/NN_<request>.narrative.txt`: what happened in each run, step by step, with the verdicts.
- `traces/NN_<request>.transcript.txt`: the raw exchange, every message, tool call and tool output.
- `traces/NN_<request>.json`: the raw trace the runner wrote.
- `raw/`: the runner's own outputs (report.json, rescored report, logs).
- `requests.jsonl`: the request set, with the intended tool calls that define formulation exactness.

# llm_only:cot on IEEE 30-bus with gpt-4o-mini

Generated 2026-09-29 14:54 by evaluation/postprocess.py from `report.rescored.json`. Runs: 20. Scored by the unified evaluator (v2): every verdict below is read from the answer JSON, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-29 |
| model | openrouter:openai/gpt-4o-mini |
| method | llm_only:cot |
| case | case30 |
| condition | normal |
| n | 20 |
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

The three outcomes are exclusive and cover every request the method answered. Escalation takes precedence: a run the method handed to a person is not an autonomous answer, right or wrong. A request whose API call failed never reached an answer, so it is listed apart and excluded from the rates.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 0 | 0.0% |
| Escalated to a person | 0 | 0.0% |
| Wrong, unflagged | 20 | 100.0% |
| **Total** | **20** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Formulation exact | 15/20 (75.0%) |
| Task utility | Formulation error types | missed_step: 4, wrong_id: 1 |
| Task utility | Voltage MAE, all runs | 0.0376 p.u. |
| Task utility | Voltage MAE, formulation-exact runs | 0.0423 p.u. |
| Task utility | Flow MAE, all runs | 7.5627 MW |
| Task utility | Flow MAE, formulation-exact runs | 7.2206 MW |
| Task utility | KCL mismatch, mean | 9.0607 MW |
| Solver-grounded correctness | Solved (computation right, any path) | 0/20 (0.0%) |
| Solver-grounded correctness | V-pass (all conditions, offline) | 0/20 (0.0%) |
| Reporting | Traceable answers | 0/20 (0.0%) |
| Reporting | Traceable numbers, mean share | 0.148 |
| Reporting | Stale state quoted | 0/20 |
| Cost and time | LLM calls / tool calls, mean | 1 / 0 |
| Cost and time | Prompt / completion tokens, mean | 4283 / 2577 |
| Cost and time | Cost, total | $0.0438 |
| Cost and time | Wall time, mean | 32.7 s |

### Cross-check against the runner's own scoreboard

Values the runner aggregated for the same rows (report.json scoreboard). They should agree with the table above; a disagreement means the rows were filtered differently.

| metric | runner scoreboard | this report |
|---|---:|---:|
| common_solved_count | 0 | 0 |
| common_escalated_count | 0 | 0 |
| common_wrong_count | 20 | 20 |
| common_formulation_count | 15 | 15 |
| common_traceable_count | 0 | 0 |
| common_n | 20 | 20 |

## By request difficulty

| difficulty | n | solved | escalated | wrong unflagged | formulation exact |
|---|---:|---:|---:|---:|---:|
| ambiguous | 5 | 0 | 0 | 5 | 2 |
| multistep | 5 | 0 | 0 | 5 | 4 |
| parameterized | 5 | 0 | 0 | 5 | 5 |
| plain | 5 | 0 | 0 | 5 | 4 |

## Wrong and unflagged (20)

- `case30-ambiguous-003-s0` formulation exact; declared:  ([narrative](traces/01_case30-ambiguous-003-s0.narrative.txt), [transcript](traces/01_case30-ambiguous-003-s0.transcript.txt))
- `case30-ambiguous-007-s0` formulation exact; declared:  ([narrative](traces/02_case30-ambiguous-007-s0.narrative.txt), [transcript](traces/02_case30-ambiguous-007-s0.transcript.txt))
- `case30-ambiguous-011-s0` formulation missed_step; the formulation declared in the answer omits load_case, which the request needs  ([narrative](traces/03_case30-ambiguous-011-s0.narrative.txt), [transcript](traces/03_case30-ambiguous-011-s0.transcript.txt))
- `case30-ambiguous-015-s0` formulation missed_step; the formulation declared in the answer omits load_case, which the request needs  ([narrative](traces/04_case30-ambiguous-015-s0.narrative.txt), [transcript](traces/04_case30-ambiguous-015-s0.transcript.txt))
- `case30-ambiguous-019-s0` formulation wrong_id; declared: disconnect_line: from_bus intended 8 != executed 7; disconnect_line: to_bus intended 28 != executed 27  ([narrative](traces/05_case30-ambiguous-019-s0.narrative.txt), [transcript](traces/05_case30-ambiguous-019-s0.transcript.txt))
- `case30-multistep-002-s0` formulation exact; declared:  ([narrative](traces/06_case30-multistep-002-s0.narrative.txt), [transcript](traces/06_case30-multistep-002-s0.transcript.txt))
- `case30-multistep-006-s0` formulation exact; declared:  ([narrative](traces/07_case30-multistep-006-s0.narrative.txt), [transcript](traces/07_case30-multistep-006-s0.transcript.txt))
- `case30-multistep-010-s0` formulation exact; declared:  ([narrative](traces/08_case30-multistep-010-s0.narrative.txt), [transcript](traces/08_case30-multistep-010-s0.transcript.txt))
- `case30-multistep-014-s0` formulation missed_step; the formulation declared in the answer omits load_case, which the request needs  ([narrative](traces/09_case30-multistep-014-s0.narrative.txt), [transcript](traces/09_case30-multistep-014-s0.transcript.txt))
- `case30-multistep-018-s0` formulation exact; declared:  ([narrative](traces/10_case30-multistep-018-s0.narrative.txt), [transcript](traces/10_case30-multistep-018-s0.transcript.txt))
- `case30-parameterized-001-s0` formulation exact; declared:  ([narrative](traces/11_case30-parameterized-001-s0.narrative.txt), [transcript](traces/11_case30-parameterized-001-s0.transcript.txt))
- `case30-parameterized-005-s0` formulation exact; declared:  ([narrative](traces/12_case30-parameterized-005-s0.narrative.txt), [transcript](traces/12_case30-parameterized-005-s0.transcript.txt))
- `case30-parameterized-009-s0` formulation exact; declared:  ([narrative](traces/13_case30-parameterized-009-s0.narrative.txt), [transcript](traces/13_case30-parameterized-009-s0.transcript.txt))
- `case30-parameterized-013-s0` formulation exact; declared:  ([narrative](traces/14_case30-parameterized-013-s0.narrative.txt), [transcript](traces/14_case30-parameterized-013-s0.transcript.txt))
- `case30-parameterized-017-s0` formulation exact; declared:  ([narrative](traces/15_case30-parameterized-017-s0.narrative.txt), [transcript](traces/15_case30-parameterized-017-s0.transcript.txt))
- `case30-plain-000-s0` formulation exact; declared:  ([narrative](traces/16_case30-plain-000-s0.narrative.txt), [transcript](traces/16_case30-plain-000-s0.transcript.txt))
- `case30-plain-004-s0` formulation exact; declared:  ([narrative](traces/17_case30-plain-004-s0.narrative.txt), [transcript](traces/17_case30-plain-004-s0.transcript.txt))
- `case30-plain-008-s0` formulation missed_step; the formulation declared in the answer omits load_case, which the request needs  ([narrative](traces/18_case30-plain-008-s0.narrative.txt), [transcript](traces/18_case30-plain-008-s0.transcript.txt))
- `case30-plain-012-s0` formulation exact; declared:  ([narrative](traces/19_case30-plain-012-s0.narrative.txt), [transcript](traces/19_case30-plain-012-s0.transcript.txt))
- `case30-plain-016-s0` formulation exact; declared:  ([narrative](traces/20_case30-plain-016-s0.narrative.txt), [transcript](traces/20_case30-plain-016-s0.transcript.txt))

## Formulation not exact (5)

- `case30-ambiguous-011-s0` missed_step: the formulation declared in the answer omits load_case, which the request needs  ([narrative](traces/03_case30-ambiguous-011-s0.narrative.txt), [transcript](traces/03_case30-ambiguous-011-s0.transcript.txt))
- `case30-ambiguous-015-s0` missed_step: the formulation declared in the answer omits load_case, which the request needs  ([narrative](traces/04_case30-ambiguous-015-s0.narrative.txt), [transcript](traces/04_case30-ambiguous-015-s0.transcript.txt))
- `case30-ambiguous-019-s0` wrong_id: declared: disconnect_line: from_bus intended 8 != executed 7; disconnect_line: to_bus intended 28 != executed 27  ([narrative](traces/05_case30-ambiguous-019-s0.narrative.txt), [transcript](traces/05_case30-ambiguous-019-s0.transcript.txt))
- `case30-multistep-014-s0` missed_step: the formulation declared in the answer omits load_case, which the request needs  ([narrative](traces/09_case30-multistep-014-s0.narrative.txt), [transcript](traces/09_case30-multistep-014-s0.transcript.txt))
- `case30-plain-008-s0` missed_step: the formulation declared in the answer omits load_case, which the request needs  ([narrative](traces/18_case30-plain-008-s0.narrative.txt), [transcript](traces/18_case30-plain-008-s0.transcript.txt))

## Untraceable numbers in the answer (20)

- `case30-ambiguous-003-s0` 148 of 148 numbers; values ['174.0 MW', '174.0 MW', '0.0 MW', '1.0', '0.0', '1.01', '-1.5', '0.98', '-2.0', '0.97', '-3.0', '1.02', '-1.0', '1.03', '0.5', '1.01', '-1.5', '1.00', '0.0', '1.01']  ([narrative](traces/01_case30-ambiguous-003-s0.narrative.txt), [transcript](traces/01_case30-ambiguous-003-s0.transcript.txt))
- `case30-ambiguous-007-s0` 143 of 143 numbers; values ['0.0', '1.01', '-1.5', '1.02', '-2.0', '1.03', '-3.0', '1.01', '-1.0', '1.02', '-2.5', '1.01', '-1.5', '0.98', '-4.0', '-2.0', '1.01', '-1.5', '-2.0', '1.02']  ([narrative](traces/02_case30-ambiguous-007-s0.narrative.txt), [transcript](traces/02_case30-ambiguous-007-s0.transcript.txt))
- `case30-ambiguous-011-s0` 150 of 150 numbers; values ['10.7 MW', '8.69 MW', '10.7 MW', '10.7', '10.7 MW', '1.0', '0.0', '1.01', '-2.0', '1.02', '-3.0', '1.03', '-4.0', '1.01', '-1.5', '1.00', '-1.0', '1.02', '-2.5', '1.01']  ([narrative](traces/03_case30-ambiguous-011-s0.narrative.txt), [transcript](traces/03_case30-ambiguous-011-s0.transcript.txt))
- `case30-ambiguous-015-s0` 151 of 151 numbers; values ['6.762852 MW', '1.0', '0.0', '1.01', '-2.0', '1.02', '-3.0', '1.03', '-4.0', '1.01', '-1.0', '1.02', '-2.0', '1.01', '-1.0', '1.00', '0.0', '1.01', '-1.0', '1.02']  ([narrative](traces/04_case30-ambiguous-015-s0.narrative.txt), [transcript](traces/04_case30-ambiguous-015-s0.transcript.txt))
- `case30-ambiguous-019-s0` 148 of 148 numbers; values ['139.2 MW', '139.2 MW', '1.0', '1.01', '-1.5', '1.02', '-2.0', '1.03', '-1.0', '1.01', '-1.5', '1.02', '-2.0', '1.01', '-1.5', '1.02', '-2.0', '1.01', '-1.5', '1.02']  ([narrative](traces/05_case30-ambiguous-019-s0.narrative.txt), [transcript](traces/05_case30-ambiguous-019-s0.transcript.txt))
- `case30-multistep-002-s0` 35 of 35 numbers; values ['0.9345 p.u.', '1.025', '1.02', '1.015', '1.01', '0.9345', '0.0', '0.0', '0.0', '0.9345']  ([narrative](traces/06_case30-multistep-002-s0.narrative.txt), [transcript](traces/06_case30-multistep-002-s0.transcript.txt))
- `case30-multistep-006-s0` 173 of 173 numbers; values ['22.73 MW', '2.20 MW', '7.44 MW', '24.75 MW', '32.50 MW', '5.65 MW', '11.24 MW', '6.53 MW', '8.52 MW', '3.35 MW', '9.02 MW', '3.27 MW', '10.29 MW', '2.17 MW', '16.80 MW', '3.38 MW', '9.37 MW', '3.37 MW', '2.31 MW', '9.71 MW']  ([narrative](traces/07_case30-multistep-006-s0.narrative.txt), [transcript](traces/07_case30-multistep-006-s0.transcript.txt))
- `case30-multistep-010-s0` 152 of 152 numbers; values ['105.3%', '102.1%', '101.5%', '0.0', '1.01', '-2.5', '0.98', '-5.0', '0.97', '-7.0', '0.96', '-8.0', '0.95', '-9.0', '0.99', '-3.0', '1.02', '-1.0', '1.01', '-2.0']  ([narrative](traces/08_case30-multistep-010-s0.narrative.txt), [transcript](traces/08_case30-multistep-010-s0.transcript.txt))
- `case30-multistep-014-s0` 70 of 70 numbers; values ['0.9345 p.u.', '1.0', '0.0', '1.0', '0.0', '1.0', '0.0', '1.0', '0.0', '1.0', '0.0', '1.0', '0.0', '1.0', '0.0', '1.0', '0.0', '1.0', '0.0', '0.9750']  ([narrative](traces/09_case30-multistep-014-s0.narrative.txt), [transcript](traces/09_case30-multistep-014-s0.transcript.txt))
- `case30-multistep-018-s0` 80 of 80 numbers; values ['92.5%', '95.3%', '91.2%', '1.0', '0.0', '1.01', '5.0', '1.02', '10.0', '1.03', '15.0', '1.04', '20.0', '1.05', '25.0', '1.06', '1.07', '35.0', '1.08', '40.0']  ([narrative](traces/10_case30-multistep-018-s0.narrative.txt), [transcript](traces/10_case30-multistep-018-s0.transcript.txt))
- `case30-parameterized-001-s0` 70 of 70 numbers; values ['0.95', '1.05 p.u.', '0.9345 p.u.', '0.9382 p.u.', '0.9410 p.u.', '0.0', '1.02', '0.0', '1.01', '0.0', '0.95', '0.0', '1.03', '0.0', '0.94', '0.0', '1.01', '0.0', '1.02', '0.0']  ([narrative](traces/11_case30-parameterized-001-s0.narrative.txt), [transcript](traces/11_case30-parameterized-001-s0.transcript.txt))
- `case30-parameterized-005-s0` 148 of 148 numbers; values ['174.0 MW', '174.0 MW', '0.0 MW', '1.0', '0.0', '1.01', '-1.5', '1.02', '-2.0', '1.03', '-3.0', '1.01', '-1.0', '1.02', '-2.5', '1.01', '-1.5', '1.02', '-2.0', '1.01']  ([narrative](traces/12_case30-parameterized-005-s0.narrative.txt), [transcript](traces/12_case30-parameterized-005-s0.transcript.txt))
- `case30-parameterized-009-s0` 148 of 148 numbers; values ['0.0', '1.02', '-2.0', '1.01', '-3.0', '0.98', '-5.0', '1.01', '-1.0', '0.97', '-4.0', '0.95', '-6.0', '1.03', '-2.0', '1.01', '-3.0', '1.02', '-1.0', '0.0']  ([narrative](traces/13_case30-parameterized-009-s0.narrative.txt), [transcript](traces/13_case30-parameterized-009-s0.transcript.txt))
- `case30-parameterized-013-s0` 143 of 143 numbers; values ['1.0', '0.0', '1.01', '-2.0', '1.02', '-3.0', '1.03', '-4.0', '1.01', '-1.0', '1.00', '-5.0', '1.02', '-2.5', '1.01', '-1.5', '0.99', '-6.0', '1.00', '-5.5']  ([narrative](traces/14_case30-parameterized-013-s0.narrative.txt), [transcript](traces/14_case30-parameterized-013-s0.transcript.txt))
- `case30-parameterized-017-s0` 145 of 145 numbers; values ['0.0', '1.02', '5.0', '1.01', '3.0', '0.98', '-2.0', '0.0', '1.01', '4.0', '1.03', '6.0', '1.04', '7.0', '0.0', '1.01', '3.0', '0.0', '0.97', '-3.0']  ([narrative](traces/15_case30-parameterized-017-s0.narrative.txt), [transcript](traces/15_case30-parameterized-017-s0.transcript.txt))
- `case30-plain-000-s0` 65 of 65 numbers; values ['0.9487 p.u.', '1.06', '0.0', '1.045', '-4.98', '1.01', '-12.72', '1.0', '-15.0', '1.0', '-15.0', '1.0', '-15.0', '1.0', '-15.0', '0.9487', '-15.0', '1.0', '-15.0', '1.0']  ([narrative](traces/16_case30-plain-000-s0.narrative.txt), [transcript](traces/16_case30-plain-000-s0.transcript.txt))
- `case30-plain-004-s0` 147 of 147 numbers; values ['120.5%', '0.0', '0.98', '-5.0', '0.97', '-10.0', '0.96', '-15.0', '0.95', '-20.0', '0.94', '-25.0', '0.93', '-30.0', '0.92', '-35.0', '0.91', '-40.0', '0.90', '-45.0']  ([narrative](traces/17_case30-plain-004-s0.narrative.txt), [transcript](traces/17_case30-plain-004-s0.transcript.txt))
- `case30-plain-008-s0` 82 of 82 numbers; values ['20.917473 MW', '173.5 MW', '173.5 MW', '0.0 MW', '1.0', '0.0', '1.01', '-2.0', '1.02', '-3.0', '1.03', '-4.0', '1.01', '-5.0', '1.00', '-6.0', '1.02', '-7.0', '1.01', '-8.0']  ([narrative](traces/18_case30-plain-008-s0.narrative.txt), [transcript](traces/18_case30-plain-008-s0.transcript.txt))
- `case30-plain-012-s0` 148 of 148 numbers; values ['155.2 MW', '155.2 MW', '0.0 MW', '1.06', '0.0', '1.045', '-4.98', '1.01', '-12.72', '1.0', '-15.0', '1.0', '-15.0', '1.0', '-15.0', '1.0', '-15.0', '1.0', '-15.0', '1.0']  ([narrative](traces/19_case30-plain-012-s0.narrative.txt), [transcript](traces/19_case30-plain-012-s0.transcript.txt))
- `case30-plain-016-s0` 147 of 147 numbers; values ['120.5%', '0.0', '1.02', '-5.0', '1.01', '-3.0', '1.01', '-2.0', '1.01', '-1.0', '0.98', '-4.0', '0.97', '-6.0', '1.03', '-2.0', '1.02', '-1.0', '1.01', '-3.0']  ([narrative](traces/20_case30-plain-016-s0.narrative.txt), [transcript](traces/20_case30-plain-016-s0.transcript.txt))

## Files

- `summary.csv`: one line per run, the fields above plus tokens and time.
- `traces/NN_<request>.narrative.txt`: what happened in each run, step by step, with the verdicts.
- `traces/NN_<request>.transcript.txt`: the raw exchange, every message, tool call and tool output.
- `traces/NN_<request>.png`: the run as a picture: steps, gate verdicts, formulation, verification, outcome, with a two-line narrative.
- `overview.png`: all runs of this folder on one page.
- `traces/NN_<request>.json`: the raw trace the runner wrote.
- `raw/`: the runner's own outputs (report.json, rescored report, logs).
- `requests.jsonl`: the request set, with the intended tool calls that define formulation exactness.

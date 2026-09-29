# llm_only:structured on IEEE 118-bus with gpt-4o-mini

Generated 2026-09-29 14:54 by evaluation/postprocess.py from `report.rescored.json`. Runs: 20. Scored by the unified evaluator (v2): every verdict below is read from the answer JSON, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-29 |
| model | openrouter:openai/gpt-4o-mini |
| method | llm_only:structured |
| case | case118 |
| condition | normal |
| n | 20 |
| seed | 0 |
| k | 1 |
| max_rounds | 8 |
| tool_variant | load_split |
| plan_variant | text |
| temperature | 0.0 |
| system_prompt_hash | 183abd966fbd |
| description | LLM answers from the case tables in the prompt. No tools. Structured prompt: role, full case tables as system data, task, JSON output schema. |
| prompt files | _shared/llm_only_system_prompt.txt, _shared/llm_only_user_template.txt, _shared/llm_only_bus_id_note.txt |

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
| Task utility | Formulation exact | 20/20 (100.0%) |
| Task utility | Voltage MAE, all runs | 0.0891 p.u. |
| Task utility | Voltage MAE, formulation-exact runs | 0.0891 p.u. |
| Task utility | Flow MAE, all runs | 149.4892 MW |
| Task utility | Flow MAE, formulation-exact runs | 149.4892 MW |
| Task utility | KCL mismatch, mean | 107.8411 MW |
| Solver-grounded correctness | Solved (computation right, any path) | 0/20 (0.0%) |
| Solver-grounded correctness | V-pass (all conditions, offline) | 0/20 (0.0%) |
| Reporting | Traceable answers | 0/20 (0.0%) |
| Reporting | Traceable numbers, mean share | 0.071 |
| Reporting | Stale state quoted | 0/20 |
| Cost and time | LLM calls / tool calls, mean | 1 / 0 |
| Cost and time | Prompt / completion tokens, mean | 14061 / 6739 |
| Cost and time | Cost, total | $0.1231 |
| Cost and time | Wall time, mean | 218.4 s |

### Cross-check against the runner's own scoreboard

Values the runner aggregated for the same rows (report.json scoreboard). They should agree with the table above; a disagreement means the rows were filtered differently.

| metric | runner scoreboard | this report |
|---|---:|---:|
| common_solved_count | 0 | 0 |
| common_escalated_count | 0 | 0 |
| common_wrong_count | 20 | 20 |
| common_formulation_count | 20 | 20 |
| common_traceable_count | 0 | 0 |
| common_n | 20 | 20 |

## By request difficulty

| difficulty | n | solved | escalated | wrong unflagged | formulation exact |
|---|---:|---:|---:|---:|---:|
| ambiguous | 5 | 0 | 0 | 5 | 5 |
| multistep | 5 | 0 | 0 | 5 | 5 |
| parameterized | 5 | 0 | 0 | 5 | 5 |
| plain | 5 | 0 | 0 | 5 | 5 |

## Wrong and unflagged (20)

- `case118-ambiguous-003-s0` formulation exact; declared:  ([narrative](traces/01_case118-ambiguous-003-s0.narrative.txt), [transcript](traces/01_case118-ambiguous-003-s0.transcript.txt))
- `case118-ambiguous-007-s0` formulation exact; declared:  ([narrative](traces/02_case118-ambiguous-007-s0.narrative.txt), [transcript](traces/02_case118-ambiguous-007-s0.transcript.txt))
- `case118-ambiguous-011-s0` formulation exact; declared:  ([narrative](traces/03_case118-ambiguous-011-s0.narrative.txt), [transcript](traces/03_case118-ambiguous-011-s0.transcript.txt))
- `case118-ambiguous-015-s0` formulation exact; declared:  ([narrative](traces/04_case118-ambiguous-015-s0.narrative.txt), [transcript](traces/04_case118-ambiguous-015-s0.transcript.txt))
- `case118-ambiguous-019-s0` formulation exact; declared:  ([narrative](traces/05_case118-ambiguous-019-s0.narrative.txt), [transcript](traces/05_case118-ambiguous-019-s0.transcript.txt))
- `case118-multistep-002-s0` formulation exact; declared:  ([narrative](traces/06_case118-multistep-002-s0.narrative.txt), [transcript](traces/06_case118-multistep-002-s0.transcript.txt))
- `case118-multistep-006-s0` formulation exact; declared:  ([narrative](traces/07_case118-multistep-006-s0.narrative.txt), [transcript](traces/07_case118-multistep-006-s0.transcript.txt))
- `case118-multistep-010-s0` formulation exact; declared:  ([narrative](traces/08_case118-multistep-010-s0.narrative.txt), [transcript](traces/08_case118-multistep-010-s0.transcript.txt))
- `case118-multistep-014-s0` formulation exact; declared:  ([narrative](traces/09_case118-multistep-014-s0.narrative.txt), [transcript](traces/09_case118-multistep-014-s0.transcript.txt))
- `case118-multistep-018-s0` formulation exact; declared:  ([narrative](traces/10_case118-multistep-018-s0.narrative.txt), [transcript](traces/10_case118-multistep-018-s0.transcript.txt))
- `case118-parameterized-001-s0` formulation exact; declared:  ([narrative](traces/11_case118-parameterized-001-s0.narrative.txt), [transcript](traces/11_case118-parameterized-001-s0.transcript.txt))
- `case118-parameterized-005-s0` formulation exact; declared:  ([narrative](traces/12_case118-parameterized-005-s0.narrative.txt), [transcript](traces/12_case118-parameterized-005-s0.transcript.txt))
- `case118-parameterized-009-s0` formulation exact; declared:  ([narrative](traces/13_case118-parameterized-009-s0.narrative.txt), [transcript](traces/13_case118-parameterized-009-s0.transcript.txt))
- `case118-parameterized-013-s0` formulation exact; declared:  ([narrative](traces/14_case118-parameterized-013-s0.narrative.txt), [transcript](traces/14_case118-parameterized-013-s0.transcript.txt))
- `case118-parameterized-017-s0` formulation exact; declared:  ([narrative](traces/15_case118-parameterized-017-s0.narrative.txt), [transcript](traces/15_case118-parameterized-017-s0.transcript.txt))
- `case118-plain-000-s0` formulation exact; declared:  ([narrative](traces/16_case118-plain-000-s0.narrative.txt), [transcript](traces/16_case118-plain-000-s0.transcript.txt))
- `case118-plain-004-s0` formulation exact; declared:  ([narrative](traces/17_case118-plain-004-s0.narrative.txt), [transcript](traces/17_case118-plain-004-s0.transcript.txt))
- `case118-plain-008-s0` formulation exact; declared:  ([narrative](traces/18_case118-plain-008-s0.narrative.txt), [transcript](traces/18_case118-plain-008-s0.transcript.txt))
- `case118-plain-012-s0` formulation exact; declared:  ([narrative](traces/19_case118-plain-012-s0.narrative.txt), [transcript](traces/19_case118-plain-012-s0.transcript.txt))
- `case118-plain-016-s0` formulation exact; declared:  ([narrative](traces/20_case118-plain-016-s0.narrative.txt), [transcript](traces/20_case118-plain-016-s0.transcript.txt))

## Untraceable numbers in the answer (20)

- `case118-ambiguous-003-s0` 434 of 434 numbers; values ['1,200.0 MW', '1,150.0 MW', '50.0 MW', '1.02', '0.0', '1.01', '-2.0', '1.00', '-4.0', '1.00', '-6.0', '1.00', '-8.0', '1.00', '-10.0', '1.00', '-12.0', '1.00', '-14.0', '1.00']  ([narrative](traces/01_case118-ambiguous-003-s0.narrative.txt), [transcript](traces/01_case118-ambiguous-003-s0.transcript.txt))
- `case118-ambiguous-007-s0` 239 of 239 numbers; values ['1.02', '0.0', '1.01', '-5.0', '-10.0', '1.03', '-15.0', '1.02', '-20.0', '1.01', '-25.0', '-30.0', '1.01', '-35.0', '1.02', '-40.0', '1.03', '-45.0', '1.01', '-50.0']  ([narrative](traces/02_case118-ambiguous-007-s0.narrative.txt), [transcript](traces/02_case118-ambiguous-007-s0.transcript.txt))
- `case118-ambiguous-011-s0` 243 of 243 numbers; values ['1,200.0 MW', '1,200.0 MW', '1.020', '1.015', '-2.0', '1.010', '-4.0', '1.005', '-6.0', '1.000', '-8.0', '1.025', '-10.0', '1.030', '-12.0', '1.035', '-14.0', '1.040', '-16.0', '1.045']  ([narrative](traces/03_case118-ambiguous-011-s0.narrative.txt), [transcript](traces/03_case118-ambiguous-011-s0.transcript.txt))
- `case118-ambiguous-015-s0` 244 of 244 numbers; values ['2,000.0 MW', '1,800.0 MW', '200.0 MW', '1.02', '0.0', '1.01', '-2.0', '1.00', '-4.0', '1.00', '-6.0', '1.00', '-8.0', '1.00', '-10.0', '1.00', '-12.0', '1.00', '-14.0', '1.00']  ([narrative](traces/04_case118-ambiguous-015-s0.narrative.txt), [transcript](traces/04_case118-ambiguous-015-s0.transcript.txt))
- `case118-ambiguous-019-s0` 590 of 590 numbers; values ['2,000.0 MW', '1,800.0 MW', '200.0 MW', '1.02', '0.0', '1.01', '-5.0', '-10.0', '1.03', '-3.0', '1.02', '-2.0', '1.01', '-1.0', '0.0', '1.01', '-4.0', '-6.0', '1.02', '-5.0']  ([narrative](traces/05_case118-ambiguous-019-s0.narrative.txt), [transcript](traces/05_case118-ambiguous-019-s0.transcript.txt))
- `case118-multistep-002-s0` 123 of 123 numbers; values ['0.934 p.u.', '1.045', '1.034', '1.025', '1.020', '1.018', '1.015', '1.012', '1.010', '0.990', '0.989', '0.988', '0.987', '0.986', '0.985', '0.984', '0.983', '0.982', '0.981', '0.980']  ([narrative](traces/06_case118-multistep-002-s0.narrative.txt), [transcript](traces/06_case118-multistep-002-s0.transcript.txt))
- `case118-multistep-006-s0` 475 of 475 numbers; values ['102.5%', '101.2%', '1.020', '1.015', '1.018', '1.022', '1.025', '1.020', '1.018', '1.015', '1.017', '1.019', '1.021', '1.020', '1.018', '1.016', '1.014', '1.013', '1.012', '1.011']  ([narrative](traces/07_case118-multistep-006-s0.narrative.txt), [transcript](traces/07_case118-multistep-006-s0.transcript.txt))
- `case118-multistep-010-s0` 595 of 595 numbers; values ['105.3%', '102.1%', '101.5%', '1.020', '0.0', '1.015', '-2.5', '1.010', '-5.0', '1.025', '-1.0', '1.030', '-3.0', '1.005', '-4.0', '1.000', '-6.0', '1.015', '-2.0', '1.020']  ([narrative](traces/08_case118-multistep-010-s0.narrative.txt), [transcript](traces/08_case118-multistep-010-s0.transcript.txt))
- `case118-multistep-014-s0` 126 of 126 numbers; values ['0.9482 p.u.', '1.035', '1.025', '1.020', '1.018', '1.015', '1.010', '1.005', '1.000', '1.000', '1.000', '1.000', '1.000', '1.000', '1.000', '1.000', '1.000', '1.000', '1.000', '1.000']  ([narrative](traces/09_case118-multistep-014-s0.narrative.txt), [transcript](traces/09_case118-multistep-014-s0.transcript.txt))
- `case118-multistep-018-s0` 594 of 594 numbers; values ['101.2%', '1.005', '0.0', '1.002', '-1.5', '1.003', '-2.0', '1.004', '-1.0', '1.006', '0.5', '1.007', '1.0', '1.008', '1.5', '1.009', '2.0', '1.010', '2.5', '1.011']  ([narrative](traces/10_case118-multistep-018-s0.narrative.txt), [transcript](traces/10_case118-multistep-018-s0.transcript.txt))
- `case118-parameterized-001-s0` 477 of 477 numbers; values ['0.9345 p.u.', '0.9350 p.u.', '0.9400 p.u.', '1.035', '1.025', '1.020', '1.015', '0.940', '1.010', '1.020', '1.030', '1.015', '0.935', '1.010', '1.020', '1.025', '1.030', '1.035', '1.040', '1.045']  ([narrative](traces/11_case118-parameterized-001-s0.narrative.txt), [transcript](traces/11_case118-parameterized-001-s0.transcript.txt))
- `case118-parameterized-005-s0` 239 of 239 numbers; values ['1.020', '0.0', '1.015', '-2.0', '1.010', '-4.0', '1.025', '-1.0', '1.030', '1.0', '1.018', '-3.0', '1.022', '-2.0', '1.028', '0.0', '1.024', '-1.0', '1.019', '-2.0']  ([narrative](traces/12_case118-parameterized-005-s0.narrative.txt), [transcript](traces/12_case118-parameterized-005-s0.transcript.txt))
- `case118-parameterized-009-s0` 604 of 604 numbers; values ['1.02', '0.0', '1.01', '5.0', '10.0', '0.99', '15.0', '0.98', '20.0', '25.0', '1.01', '30.0', '1.02', '35.0', '1.03', '40.0', '1.04', '45.0', '1.05', '50.0']  ([narrative](traces/13_case118-parameterized-009-s0.narrative.txt), [transcript](traces/13_case118-parameterized-009-s0.transcript.txt))
- `case118-parameterized-013-s0` 592 of 592 numbers; values ['2,000.0 MW', '1,800.0 MW', '200.0 MW', '1.02', '0.0', '1.01', '-5.0', '1.00', '-10.0', '1.03', '-2.0', '1.01', '-3.0', '1.00', '-4.0', '1.00', '-5.0', '1.00', '-6.0', '1.00']  ([narrative](traces/14_case118-parameterized-013-s0.narrative.txt), [transcript](traces/14_case118-parameterized-013-s0.transcript.txt))
- `case118-parameterized-017-s0` 259 of 259 numbers; values ['1.02', '0.0', '0.98', '-5.0', '1.01', '10.0', '15.0', '20.0', '0.97', '25.0', '1.03', '30.0', '1.04', '35.0', '1.02', '40.0', '1.01', '45.0', '50.0', '0.99']  ([narrative](traces/15_case118-parameterized-017-s0.narrative.txt), [transcript](traces/15_case118-parameterized-017-s0.transcript.txt))
- `case118-plain-000-s0` 240 of 240 numbers; values ['0.8834 p.u.', '0.9551', '0.0', '0.9642', '-1.5', '0.9735', '-2.3', '0.9821', '-3.1', '0.9900', '-4.0', '0.9965', '-5.0', '0.9980', '-6.0', '1.0000', '-7.0', '1.0020', '-8.0', '1.0040']  ([narrative](traces/16_case118-plain-000-s0.narrative.txt), [transcript](traces/16_case118-plain-000-s0.transcript.txt))
- `case118-plain-004-s0` 591 of 591 numbers; values ['120.5%', '1.02', '0.0', '1.01', '-5.0', '-10.0', '-15.0', '-20.0', '-25.0', '-30.0', '-35.0', '-40.0', '-45.0', '-50.0', '-55.0', '-60.0', '-65.0', '-70.0', '-75.0', '-80.0']  ([narrative](traces/17_case118-plain-004-s0.narrative.txt), [transcript](traces/17_case118-plain-004-s0.transcript.txt))
- `case118-plain-008-s0` 244 of 244 numbers; values ['0.0 MW', '0.0 MW', '0.0 MW', '1.06', '0.0', '1.05', '-2.0', '1.04', '-4.0', '1.03', '-6.0', '1.02', '-8.0', '1.01', '-10.0', '-12.0', '0.99', '-14.0', '0.98', '-16.0']  ([narrative](traces/18_case118-plain-008-s0.narrative.txt), [transcript](traces/18_case118-plain-008-s0.transcript.txt))
- `case118-plain-012-s0` 260 of 260 numbers; values ['3,200.0 MW', '2,800.0 MW', '400.0 MW', '1.02', '0.0', '1.01', '-5.0', '1.00', '-10.0', '1.00', '-15.0', '1.00', '-20.0', '1.00', '-25.0', '1.00', '-30.0', '1.00', '-35.0', '1.00']  ([narrative](traces/19_case118-plain-012-s0.narrative.txt), [transcript](traces/19_case118-plain-012-s0.transcript.txt))
- `case118-plain-016-s0` 473 of 473 numbers; values ['120.5%', '1.025', '1.020', '1.018', '1.015', '1.012', '1.010', '0.990', '0.988', '0.985', '0.983', '0.980', '0.978', '0.975', '0.973', '0.970', '0.968', '0.965', '0.963', '0.960']  ([narrative](traces/20_case118-plain-016-s0.narrative.txt), [transcript](traces/20_case118-plain-016-s0.transcript.txt))

## Files

- `summary.csv`: one line per run, the fields above plus tokens and time.
- `traces/NN_<request>.narrative.txt`: what happened in each run, step by step, with the verdicts.
- `traces/NN_<request>.transcript.txt`: the raw exchange, every message, tool call and tool output.
- `traces/NN_<request>.png`: the run as a picture: steps, gate verdicts, formulation, verification, outcome, with a two-line narrative.
- `overview.png`: all runs of this folder on one page.
- `traces/NN_<request>.json`: the raw trace the runner wrote.
- `raw/`: the runner's own outputs (report.json, rescored report, logs).
- `requests.jsonl`: the request set, with the intended tool calls that define formulation exactness.

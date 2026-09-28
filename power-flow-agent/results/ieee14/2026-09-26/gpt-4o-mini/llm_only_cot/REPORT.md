# llm_only:cot on IEEE 14-bus with gpt-4o-mini

Generated 2026-09-28 11:27 by evaluation/postprocess.py from `report.rescored.json`. Runs: 20. Scored by the unified evaluator (v2): every verdict below is read from the answer JSON, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-26 |
| model | openrouter:openai/gpt-4o-mini |
| method | llm_only:cot |
| case | case14 |
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
| Task utility | Formulation exact | 19/20 (95.0%) |
| Task utility | Formulation error types | wrong_id: 1 |
| Task utility | Voltage MAE, all runs | 0.0274 p.u. |
| Task utility | Voltage MAE, formulation-exact runs | 0.0274 p.u. |
| Task utility | Flow MAE, all runs | 19.6695 MW |
| Task utility | Flow MAE, formulation-exact runs | 19.6695 MW |
| Task utility | KCL mismatch, mean | 11.8723 MW |
| Solver-grounded correctness | Solved (computation right, any path) | 0/20 (0.0%) |
| Solver-grounded correctness | V-pass (all conditions, offline) | 0/20 (0.0%) |
| Reporting | Traceable answers | 0/20 (0.0%) |
| Reporting | Traceable numbers, mean share | 0.092 |
| Reporting | Stale state quoted | 0/20 |
| Cost and time | LLM calls / tool calls, mean | 1 / 0 |
| Cost and time | Prompt / completion tokens, mean | 3277 / 1506 |
| Cost and time | Cost, total | $0.0279 |
| Cost and time | Wall time, mean | 10.4 s |

### Cross-check against the runner's own scoreboard

Values the runner aggregated for the same rows (report.json scoreboard). They should agree with the table above; a disagreement means the rows were filtered differently.

| metric | runner scoreboard | this report |
|---|---:|---:|
| common_solved_count | 0 | 0 |
| common_escalated_count | 0 | 0 |
| common_wrong_count | 20 | 20 |
| common_formulation_count | 19 | 19 |
| common_traceable_count | 0 | 0 |
| common_n | 20 | 20 |

## By request difficulty

| difficulty | n | solved | escalated | wrong unflagged | formulation exact |
|---|---:|---:|---:|---:|---:|
| ambiguous | 5 | 0 | 0 | 5 | 5 |
| multistep | 5 | 0 | 0 | 5 | 4 |
| parameterized | 5 | 0 | 0 | 5 | 5 |
| plain | 5 | 0 | 0 | 5 | 5 |

## Wrong and unflagged (20)

- `case14-ambiguous-003-s0` formulation exact; declared:  ([narrative](traces/01_case14-ambiguous-003-s0.narrative.txt), [transcript](traces/01_case14-ambiguous-003-s0.transcript.txt))
- `case14-ambiguous-007-s0` formulation exact; declared:  ([narrative](traces/02_case14-ambiguous-007-s0.narrative.txt), [transcript](traces/02_case14-ambiguous-007-s0.transcript.txt))
- `case14-ambiguous-011-s0` formulation exact; declared:  ([narrative](traces/03_case14-ambiguous-011-s0.narrative.txt), [transcript](traces/03_case14-ambiguous-011-s0.transcript.txt))
- `case14-ambiguous-015-s0` formulation exact; declared:  ([narrative](traces/04_case14-ambiguous-015-s0.narrative.txt), [transcript](traces/04_case14-ambiguous-015-s0.transcript.txt))
- `case14-ambiguous-019-s0` formulation exact; declared:  ([narrative](traces/05_case14-ambiguous-019-s0.narrative.txt), [transcript](traces/05_case14-ambiguous-019-s0.transcript.txt))
- `case14-multistep-002-s0` formulation exact; declared:  ([narrative](traces/06_case14-multistep-002-s0.narrative.txt), [transcript](traces/06_case14-multistep-002-s0.transcript.txt))
- `case14-multistep-006-s0` formulation exact; declared:  ([narrative](traces/07_case14-multistep-006-s0.narrative.txt), [transcript](traces/07_case14-multistep-006-s0.transcript.txt))
- `case14-multistep-010-s0` formulation exact; declared:  ([narrative](traces/08_case14-multistep-010-s0.narrative.txt), [transcript](traces/08_case14-multistep-010-s0.transcript.txt))
- `case14-multistep-014-s0` formulation wrong_id; declared: modify_load: bus_id intended 13 != executed 4; modify_load: p_mw intended 18.9 != executed 59.1  ([narrative](traces/09_case14-multistep-014-s0.narrative.txt), [transcript](traces/09_case14-multistep-014-s0.transcript.txt))
- `case14-multistep-018-s0` formulation exact; declared:  ([narrative](traces/10_case14-multistep-018-s0.narrative.txt), [transcript](traces/10_case14-multistep-018-s0.transcript.txt))
- `case14-parameterized-001-s0` formulation exact; declared:  ([narrative](traces/11_case14-parameterized-001-s0.narrative.txt), [transcript](traces/11_case14-parameterized-001-s0.transcript.txt))
- `case14-parameterized-005-s0` formulation exact; declared:  ([narrative](traces/12_case14-parameterized-005-s0.narrative.txt), [transcript](traces/12_case14-parameterized-005-s0.transcript.txt))
- `case14-parameterized-009-s0` formulation exact; declared:  ([narrative](traces/13_case14-parameterized-009-s0.narrative.txt), [transcript](traces/13_case14-parameterized-009-s0.transcript.txt))
- `case14-parameterized-013-s0` formulation exact; declared:  ([narrative](traces/14_case14-parameterized-013-s0.narrative.txt), [transcript](traces/14_case14-parameterized-013-s0.transcript.txt))
- `case14-parameterized-017-s0` formulation exact; declared:  ([narrative](traces/15_case14-parameterized-017-s0.narrative.txt), [transcript](traces/15_case14-parameterized-017-s0.transcript.txt))
- `case14-plain-000-s0` formulation exact; declared:  ([narrative](traces/16_case14-plain-000-s0.narrative.txt), [transcript](traces/16_case14-plain-000-s0.transcript.txt))
- `case14-plain-004-s0` formulation exact; declared:  ([narrative](traces/17_case14-plain-004-s0.narrative.txt), [transcript](traces/17_case14-plain-004-s0.transcript.txt))
- `case14-plain-008-s0` formulation exact; declared:  ([narrative](traces/18_case14-plain-008-s0.narrative.txt), [transcript](traces/18_case14-plain-008-s0.transcript.txt))
- `case14-plain-012-s0` formulation exact; declared:  ([narrative](traces/19_case14-plain-012-s0.narrative.txt), [transcript](traces/19_case14-plain-012-s0.transcript.txt))
- `case14-plain-016-s0` formulation exact; declared:  ([narrative](traces/20_case14-plain-016-s0.narrative.txt), [transcript](traces/20_case14-plain-016-s0.transcript.txt))

## Formulation not exact (1)

- `case14-multistep-014-s0` wrong_id: declared: modify_load: bus_id intended 13 != executed 4; modify_load: p_mw intended 18.9 != executed 59.1  ([narrative](traces/09_case14-multistep-014-s0.narrative.txt), [transcript](traces/09_case14-multistep-014-s0.transcript.txt))

## Untraceable numbers in the answer (20)

- `case14-ambiguous-003-s0` 64 of 64 numbers; values ['41.63 MW', '194.43 MW', '0.0 MW', '1.06', '0.0', '1.045', '-0.0', '1.01', '-0.0', '1.0', '-0.0', '1.0', '-0.0', '1.07', '-0.0', '1.0', '-0.0', '1.09', '-0.0', '1.0']  ([narrative](traces/01_case14-ambiguous-003-s0.narrative.txt), [transcript](traces/01_case14-ambiguous-003-s0.transcript.txt))
- `case14-ambiguous-007-s0` 64 of 64 numbers; values ['39.51 MW', '188.5 MW', '5.2 MW', '1.06', '0.0', '1.045', '-2.5', '1.01', '-5.0', '1.02', '-3.0', '-1.0', '0.0', '0.0', '0.0', '0.0', '0.0', '0.0', '0.0', '0.0']  ([narrative](traces/02_case14-ambiguous-007-s0.narrative.txt), [transcript](traces/02_case14-ambiguous-007-s0.transcript.txt))
- `case14-ambiguous-011-s0` 68 of 68 numbers; values ['14.7 MW', '14.7 MW', '14.7', '14.7 MW', '38.38 MW', '14.7 MW', '0.0 MW', '1.06', '0.0', '1.045', '0.0', '1.01', '0.0', '1.0', '0.0', '1.0', '0.0', '1.07', '0.0', '1.0']  ([narrative](traces/03_case14-ambiguous-011-s0.narrative.txt), [transcript](traces/03_case14-ambiguous-011-s0.transcript.txt))
- `case14-ambiguous-015-s0` 79 of 79 numbers; values ['6.952678 MW', '1.06', '0.0', '1.045', '-4.0', '1.01', '-6.0', '1.02', '-5.0', '1.015', '-3.0', '1.07', '1.0', '0.0', '1.09', '10.0', '1.0', '0.0', '1.0', '0.0']  ([narrative](traces/04_case14-ambiguous-015-s0.narrative.txt), [transcript](traces/04_case14-ambiguous-015-s0.transcript.txt))
- `case14-ambiguous-019-s0` 64 of 64 numbers; values ['38.75 MW', '183.5 MW', '0.0 MW', '1.06', '0.0', '1.045', '-0.5', '1.01', '-1.0', '1.02', '-2.0', '1.015', '-1.5', '1.07', '-0.5', '0.0', '1.09', '0.5', '0.0', '0.0']  ([narrative](traces/05_case14-ambiguous-019-s0.narrative.txt), [transcript](traces/05_case14-ambiguous-019-s0.transcript.txt))
- `case14-multistep-002-s0` 44 of 44 numbers; values ['105.3%', '102.1%', '101.5%', '1.06', '0.0', '1.045', '-2.0', '1.01', '-4.0', '1.02', '-3.0', '1.01', '-1.0', '1.07', '-5.0', '1.0', '0.0', '1.09', '-2.0', '1.0']  ([narrative](traces/06_case14-multistep-002-s0.narrative.txt), [transcript](traces/06_case14-multistep-002-s0.transcript.txt))
- `case14-multistep-006-s0` 94 of 94 numbers; values ['22.73 MW', '13.30 Mvar', '86.30 MW', '17.41 Mvar', '-3.82 Mvar', '8.25 MW', '1.74 Mvar', '12.13 MW', '8.12 Mvar', '28.72 MW', '16.16 Mvar', '9.03 MW', '5.82 Mvar', '3.69 MW', '1.90 Mvar', '6.34 MW', '1.66 Mvar', '12.92 MW', '5.55 Mvar', '14.94 MW']  ([narrative](traces/07_case14-multistep-006-s0.narrative.txt), [transcript](traces/07_case14-multistep-006-s0.transcript.txt))
- `case14-multistep-010-s0` 68 of 68 numbers; values ['110.5%', '105.2%', '102.3%', '1.06', '0.0', '1.02', '-5.0', '1.01', '-10.0', '-15.0', '0.98', '-20.0', '1.07', '-2.0', '1.05', '0.0', '1.04', '0.0', '1.03', '-3.0']  ([narrative](traces/08_case14-multistep-010-s0.narrative.txt), [transcript](traces/08_case14-multistep-010-s0.transcript.txt))
- `case14-multistep-014-s0` 56 of 56 numbers; values ['48.716736 MW', '27.901811 MW', '14.299132 MW', '0.9512 p.u.', '1.06', '0.0', '1.045', '0.0', '1.01', '0.0', '0.965', '0.0', '0.98', '0.0', '1.07', '0.0', '1.0', '0.0', '1.09', '0.0']  ([narrative](traces/09_case14-multistep-014-s0.narrative.txt), [transcript](traces/09_case14-multistep-014-s0.transcript.txt))
- `case14-multistep-018-s0` 63 of 63 numbers; values ['92.5%', '95.3%', '91.1%', '1.06', '0.0', '1.045', '-2.5', '1.02', '-5.0', '1.01', '-7.0', '1.005', '-8.0', '1.07', '-10.0', '1.0', '-12.0', '1.09', '-15.0', '1.0']  ([narrative](traces/10_case14-multistep-018-s0.narrative.txt), [transcript](traces/10_case14-multistep-018-s0.transcript.txt))
- `case14-parameterized-001-s0` 77 of 77 numbers; values ['0.9345 p.u.', '0.9350 p.u.', '0.9355 p.u.', '1.06', '0.0', '1.025', '-5.0', '1.01', '-10.0', '1.02', '-15.0', '1.015', '-20.0', '1.07', '-25.0', '1.02', '-30.0', '1.03', '-35.0', '1.01']  ([narrative](traces/11_case14-parameterized-001-s0.narrative.txt), [transcript](traces/11_case14-parameterized-001-s0.transcript.txt))
- `case14-parameterized-005-s0` 61 of 61 numbers; values ['1.06', '0.0', '1.045', '-0.5', '1.01', '-1.0', '1.0', '-2.0', '1.0', '-3.0', '1.07', '-4.0', '1.0', '-5.0', '1.09', '-6.0', '1.0', '-7.0', '1.0', '-8.0']  ([narrative](traces/12_case14-parameterized-005-s0.narrative.txt), [transcript](traces/12_case14-parameterized-005-s0.transcript.txt))
- `case14-parameterized-009-s0` 90 of 90 numbers; values ['1.06', '0.0', '1.045', '-2.0', '1.01', '-5.0', '1.02', '-3.0', '1.01', '-1.0', '1.07', '2.0', '0.0', '1.09', '0.0', '0.0', '0.0', '0.0', '0.0', '0.0']  ([narrative](traces/13_case14-parameterized-009-s0.narrative.txt), [transcript](traces/13_case14-parameterized-009-s0.transcript.txt))
- `case14-parameterized-013-s0` 59 of 59 numbers; values ['1.06', '0.0', '1.045', '-2.0', '1.01', '-4.0', '1.0', '-6.0', '1.0', '-8.0', '1.07', '-10.0', '1.0', '-12.0', '1.09', '-14.0', '1.0', '-16.0', '1.0', '-18.0']  ([narrative](traces/14_case14-parameterized-013-s0.narrative.txt), [transcript](traces/14_case14-parameterized-013-s0.transcript.txt))
- `case14-parameterized-017-s0` 77 of 77 numbers; values ['1.06', '0.0', '1.045', '-2.0', '1.01', '-5.0', '-10.0', '-15.0', '1.07', '-20.0', '-25.0', '1.09', '-30.0', '-35.0', '-40.0', '-45.0', '-50.0', '-55.0', '-60.0', '156.9']  ([narrative](traces/15_case14-parameterized-017-s0.narrative.txt), [transcript](traces/15_case14-parameterized-017-s0.transcript.txt))
- `case14-plain-000-s0` 34 of 34 numbers; values ['0.95', '1.05 p.u.', '0.9734 p.u.', '1.06', '0.0', '1.045', '-4.0', '1.01', '-8.0', '1.0', '-12.0', '1.0', '-10.0', '0.9734', '-15.0', '1.0', '-20.0', '1.0', '-25.0', '1.0']  ([narrative](traces/16_case14-plain-000-s0.narrative.txt), [transcript](traces/16_case14-plain-000-s0.transcript.txt))
- `case14-plain-004-s0` 63 of 63 numbers; values ['120.5%', '1.06', '0.0', '1.045', '-2.5', '1.01', '-5.0', '1.02', '-3.0', '1.03', '-1.0', '1.07', '2.0', '1.04', '1.09', '0.0', '1.02', '-1.5', '1.01', '-2.0']  ([narrative](traces/17_case14-plain-004-s0.narrative.txt), [transcript](traces/17_case14-plain-004-s0.transcript.txt))
- `case14-plain-008-s0` 71 of 71 numbers; values ['20.92 MW', '43.95 MW', '0.0 MW', '1.06', '0.0', '1.045', '-0.5', '1.01', '-1.0', '1.02', '-2.0', '1.03', '-3.0', '1.07', '-4.0', '1.05', '-5.0', '1.09', '-6.0', '1.04']  ([narrative](traces/18_case14-plain-008-s0.narrative.txt), [transcript](traces/18_case14-plain-008-s0.transcript.txt))
- `case14-plain-012-s0` 74 of 74 numbers; values ['1.06', '0.0', '1.045', '-4.98', '1.01', '-12.53', '1.0', '-16.0', '1.0', '-18.0', '1.07', '-10.0', '1.0', '-20.0', '1.09', '-8.0', '1.0', '-15.0', '1.0', '-25.0']  ([narrative](traces/19_case14-plain-012-s0.narrative.txt), [transcript](traces/19_case14-plain-012-s0.transcript.txt))
- `case14-plain-016-s0` 63 of 63 numbers; values ['120.5%', '1.06', '0.0', '1.02', '-5.0', '1.01', '-10.0', '-15.0', '-20.0', '1.03', '-5.0', '-10.0', '-15.0', '1.01', '-5.0', '-10.0', '-15.0', '-20.0', '-25.0', '-30.0']  ([narrative](traces/20_case14-plain-016-s0.narrative.txt), [transcript](traces/20_case14-plain-016-s0.transcript.txt))

## Run errors (6)

- `case14-ambiguous-015-s0` ValueError: json_parse_failed  ([narrative](traces/04_case14-ambiguous-015-s0.narrative.txt), [transcript](traces/04_case14-ambiguous-015-s0.transcript.txt))
- `case14-multistep-014-s0` ValueError: json_parse_failed  ([narrative](traces/09_case14-multistep-014-s0.narrative.txt), [transcript](traces/09_case14-multistep-014-s0.transcript.txt))
- `case14-parameterized-001-s0` ValueError: json_parse_failed  ([narrative](traces/11_case14-parameterized-001-s0.narrative.txt), [transcript](traces/11_case14-parameterized-001-s0.transcript.txt))
- `case14-parameterized-009-s0` ValueError: json_parse_failed  ([narrative](traces/13_case14-parameterized-009-s0.narrative.txt), [transcript](traces/13_case14-parameterized-009-s0.transcript.txt))
- `case14-parameterized-017-s0` ValueError: json_parse_failed  ([narrative](traces/15_case14-parameterized-017-s0.narrative.txt), [transcript](traces/15_case14-parameterized-017-s0.transcript.txt))
- `case14-plain-012-s0` ValueError: json_parse_failed  ([narrative](traces/19_case14-plain-012-s0.narrative.txt), [transcript](traces/19_case14-plain-012-s0.transcript.txt))

## Files

- `summary.csv`: one line per run, the fields above plus tokens and time.
- `traces/NN_<request>.narrative.txt`: what happened in each run, step by step, with the verdicts.
- `traces/NN_<request>.transcript.txt`: the raw exchange, every message, tool call and tool output.
- `traces/NN_<request>.png`: the run as a picture: steps, gate verdicts, formulation, verification, outcome, with a two-line narrative.
- `overview.png`: all runs of this folder on one page.
- `traces/NN_<request>.json`: the raw trace the runner wrote.
- `raw/`: the runner's own outputs (report.json, rescored report, logs).
- `requests.jsonl`: the request set, with the intended tool calls that define formulation exactness.

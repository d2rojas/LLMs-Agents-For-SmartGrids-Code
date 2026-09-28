# plan_act_nogate on SDWPF with gpt-4o-mini

Generated 2026-09-28 12:12 by evaluation/postprocess.py from `raw/rows.jsonl`. Requests: 60. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the frozen target days, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-28 |
| model | openrouter:openai/gpt-4o-mini |
| method | plan_act_nogate |
| condition | normal |
| n | 60 |
| instances | ['t008-d201', 't008-d207', 't008-d212', 't008-d229', 't009-d201', 't009-d207', 't009-d212', 't009-d229', 't013-d201', 't013-d207', 't013-d212', 't013-d229', 't017-d201', 't017-d207', 't017-d212', 't017-d229', 't022-d201', 't022-d207', 't022-d212', 't022-d229'] |
| horizons | [3, 6, 48] |
| seed | 0 |
| requests_digest | 506b80a3fd46 |
| temperature | 0.0 |
| max_llm_calls | 8 |
| max_tool_calls | 12 |
| timeout_s | 600.0 |
| system_prompt_hash | 73f323fcf4e7 |
| git_commit | 2224ea80-dirty |
| gru_weights_hash | sha256:9a7b1330e56d249a |
| description | One planning call emits the whole sequence of tool calls; the harness executes it in order without feedback; one answer call writes the answer from the results. Tool access without iteration. |
| prompt files | _shared/common_rules.txt, _shared/output_contract.txt, _shared/agent_system_prompt.txt, plan_act_nogate/plan_system_prompt.txt |

## Where every request ended

The three outcomes are exclusive and sum to the request count. Escalation takes precedence: a request the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 30 | 50.0% |
| Escalated to a person | 0 | 0.0% |
| Wrong, unflagged | 30 | 50.0% |
| **Total** | **60** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Formulation exact | 53/60 (88.3%) |
| Task utility | Formulation error types | {'no_forecast_call': 5, 'no_formulation': 2} |
| Task utility | MAE / RMSE / overall, kW, over valid series (n=57) | 277.1 / 335.72 / 306.41 |
| Task utility | NBIAS / NMAE / NRMSE, % of installed capacity (ANEMOS protocol) | 8.47 / 18.47 / 22.38 |
| Task utility | Improvement over the protocol's reference model, % (its NMAE 19.18 %) | 0.17 |
| Task utility | Improvement over persistence, % (its NMAE 32.92 %) | 45.38 |
| Task utility | MAE / RMSE, kW, over solved requests | 298.89 / 366.23 |
| Task utility | Answer coherent with the series | 16/40 |
| Solver-grounded correctness | Valid series (schema and range) | 57/60 (95.0%) |
| Solver-grounded correctness | Traceable series | 53/58 (91.4%) |
| Solver-grounded correctness | Wrong, unflagged | 30/60 (50.0%) |
| Cost and time | Escalated | 0/60 (0.0%) |
| Cost and time | LLM calls / tool calls, mean | 2.0 / 1.93 |
| Cost and time | Prompt / completion tokens, mean | 4525.88 / 1032.5 |
| Cost and time | Cost, total | $0.0779 |
| Cost and time | Wall time, mean | 14.15 s |

## By horizon

Every error is the mean over the requests of that horizon whose series was valid; a method that returns no valid series at a horizon has nothing to average, which is itself the finding. NMAE and NRMSE are normalised by the 1500 kW installed capacity, and Imp. is the improvement score of the ANEMOS protocol (Madsen et al. 2005) over its reference model, `a_k P(t) + (1-a_k) Pbar`, fitted on the training period; the improvement over plain persistence is beside it because persistence is the reference most readers know, and the protocol warns it flatters a model at long horizons.

| horizon | n | solved | scored | MAE kW | RMSE kW | NMAE % | NRMSE % | reference NMAE % | Imp. % | persistence NMAE % | Imp. vs pers. % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 h | 20 | 13 | 19 | 194.75 | 238.41 | 12.98 | 15.89 | 13.05 | -6.49 | 28.15 | 52.44 |
| 6 h | 20 | 0 | 20 | 247.06 | 284.41 | 16.47 | 18.96 | 17.16 | 2.51 | 31.39 | 49.43 |
| 48 h | 20 | 17 | 18 | 397.39 | 495.44 | 26.49 | 33.03 | 27.9 | 4.61 | 39.64 | 33.44 |

## Wrong and unflagged (30)

- `02_wind-t008-d201-h06-energy_kwh-s0`: answer 453.3 contradicts the series (implies 2751.2)
- `05_wind-t008-d207-h06-energy_kwh-s0`: answer 748.5 contradicts the series (implies 4494.9)
- `07_wind-t008-d212-h03-peak_hour-s0`: answer 9.0 contradicts the series (implies 3.0)
- `08_wind-t008-d212-h06-energy_kwh-s0`: answer 204.3 contradicts the series (implies 1293.1)
- `11_wind-t008-d229-h06-energy_kwh-s0`: answer 288.0 contradicts the series (implies 2834.4)
- `14_wind-t009-d201-h06-energy_kwh-s0`: answer 487.5 contradicts the series (implies 2980.9)
- `17_wind-t009-d207-h06-energy_kwh-s0`: answer 775.1 contradicts the series (implies 4605.4)
- `20_wind-t009-d212-h06-energy_kwh-s0`: answer 56.5 contradicts the series (implies 1696.0)
- `22_wind-t009-d229-h03-peak_hour-s0`: the series matches no forecast-tool output
- `23_wind-t009-d229-h06-energy_kwh-s0`: answer 577.8 contradicts the series (implies 3282.1)
- `26_wind-t013-d201-h06-energy_kwh-s0`: answer 408.9 contradicts the series (implies 2476.3)
- `28_wind-t013-d207-h03-peak_hour-s0`: the series matches no forecast-tool output
- `29_wind-t013-d207-h06-energy_kwh-s0`: answer 103.5 contradicts the series (implies 3256.5)
- `31_wind-t013-d212-h03-peak_hour-s0`: answer 18.0 contradicts the series (implies 3.0)
- `32_wind-t013-d212-h06-energy_kwh-s0`: answer 246.5 contradicts the series (implies 1539.3)
- `35_wind-t013-d229-h06-energy_kwh-s0`: answer 469.4 contradicts the series (implies 2751.0)
- `36_wind-t013-d229-h48-none-s0`: the series matches no forecast-tool output
- `38_wind-t017-d201-h06-energy_kwh-s0`: answer 408.4 contradicts the series (implies 2551.8)
- `39_wind-t017-d201-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `41_wind-t017-d207-h06-energy_kwh-s0`: answer 389.4 contradicts the series (implies 2322.5)
- `44_wind-t017-d212-h06-energy_kwh-s0`: answer 601.5 contradicts the series (implies 3603.7)
- `46_wind-t017-d229-h03-peak_hour-s0`: the series matches no forecast-tool output
- `47_wind-t017-d229-h06-energy_kwh-s0`: answer 431.5 contradicts the series (implies 2561.6)
- `50_wind-t022-d201-h06-energy_kwh-s0`: answer 103.5 contradicts the series (implies 2623.3)
- `52_wind-t022-d207-h03-peak_hour-s0`: 19 values, the horizon needs 18
- `53_wind-t022-d207-h06-energy_kwh-s0`: answer 610.7 contradicts the series (implies 3613.1)
- `55_wind-t022-d212-h03-peak_hour-s0`: answer 18.0 contradicts the series (implies 3.0)
- `56_wind-t022-d212-h06-energy_kwh-s0`: answer 186.5 contradicts the series (implies 1163.4)
- `59_wind-t022-d229-h06-energy_kwh-s0`: answer 368.5 contradicts the series (implies 2213.0)
- `60_wind-t022-d229-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed

## Escalated (0)

none

## Every request

| nn | instance | h | question | outcome | formulation | values | MAE | answer ok | source | LLM/tool calls | tokens | why |
|---|---|---:|---|---|---|---:|---:|---|---|---|---:|---|
| 01 | t008-d201 | 3 | peak_hour | solved | ok | 18 | 166.09 | True | gru_forecast | 2/2 | 4367 | valid series, coherent answer, traceable to a tool output |
| 02 | t008-d201 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 133.84 | False | gru_forecast | 2/2 | 4627 | answer 453.3 contradicts the series (implies 2751.2) |
| 03 | t008-d201 | 48 | none | solved | ok | 288 | 238.56 | None | gru_forecast | 2/2 | 7555 | valid series, coherent answer, traceable to a tool output |
| 04 | t008-d207 | 3 | peak_hour | solved | ok | 18 | 238.24 | True | gru_forecast | 2/2 | 4360 | valid series, coherent answer, traceable to a tool output |
| 05 | t008-d207 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 360.13 | False | gru_forecast | 2/2 | 4583 | answer 748.5 contradicts the series (implies 4494.9) |
| 06 | t008-d207 | 48 | none | solved | ok | 288 | 338.65 | None | gru_forecast | 2/2 | 7605 | valid series, coherent answer, traceable to a tool output |
| 07 | t008-d212 | 3 | peak_hour | wrong_unflagged | ok | 18 | 272.96 | False | gru_forecast | 2/2 | 4359 | answer 9.0 contradicts the series (implies 3.0) |
| 08 | t008-d212 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 518.58 | False | gru_forecast | 2/2 | 4620 | answer 204.3 contradicts the series (implies 1293.1) |
| 09 | t008-d212 | 48 | none | solved | ok | 288 | 581.12 | None | gru_forecast | 2/2 | 7589 | valid series, coherent answer, traceable to a tool output |
| 10 | t008-d229 | 3 | peak_hour | solved | ok | 18 | 153.17 | True | gru_forecast | 2/2 | 4356 | valid series, coherent answer, traceable to a tool output |
| 11 | t008-d229 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 119.9 | False | gru_forecast | 2/2 | 4566 | answer 288.0 contradicts the series (implies 2834.4) |
| 12 | t008-d229 | 48 | none | solved | ok | 288 | 528.36 | None | gru_forecast | 2/2 | 7544 | valid series, coherent answer, traceable to a tool output |
| 13 | t009-d201 | 3 | peak_hour | solved | ok | 18 | 168.59 | True | gru_forecast | 2/2 | 4327 | valid series, coherent answer, traceable to a tool output |
| 14 | t009-d201 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 116.2 | False | gru_forecast | 2/2 | 4585 | answer 487.5 contradicts the series (implies 2980.9) |
| 15 | t009-d201 | 48 | none | solved | ok | 288 | 244.58 | None | gru_forecast | 2/2 | 7604 | valid series, coherent answer, traceable to a tool output |
| 16 | t009-d207 | 3 | peak_hour | solved | ok | 18 | 218.01 | True | gru_forecast | 2/2 | 4330 | valid series, coherent answer, traceable to a tool output |
| 17 | t009-d207 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 367.09 | False | gru_forecast | 2/2 | 4563 | answer 775.1 contradicts the series (implies 4605.4) |
| 18 | t009-d207 | 48 | none | solved | ok | 288 | 334.86 | None | gru_forecast | 2/2 | 7539 | valid series, coherent answer, traceable to a tool output |
| 19 | t009-d212 | 3 | peak_hour | solved | ok | 18 | 289.87 | True | gru_forecast | 2/2 | 4369 | valid series, coherent answer, traceable to a tool output |
| 20 | t009-d212 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 492.29 | False | gru_forecast | 2/2 | 4570 | answer 56.5 contradicts the series (implies 1696.0) |
| 21 | t009-d212 | 48 | none | solved | ok | 288 | 587.53 | None | gru_forecast | 2/2 | 7547 | valid series, coherent answer, traceable to a tool output |
| 22 | t009-d229 | 3 | peak_hour | wrong_unflagged | no_forecast_call | 18 | 135.17 | True | gru_forecast | 2/2 | 4328 | the series matches no forecast-tool output |
| 23 | t009-d229 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 93.02 | False | gru_forecast | 2/2 | 4557 | answer 577.8 contradicts the series (implies 3282.1) |
| 24 | t009-d229 | 48 | none | solved | ok | 288 | 524.95 | None | gru_forecast | 2/2 | 7562 | valid series, coherent answer, traceable to a tool output |
| 25 | t013-d201 | 3 | peak_hour | solved | ok | 18 | 209.35 | True | gru_forecast | 2/2 | 4328 | valid series, coherent answer, traceable to a tool output |
| 26 | t013-d201 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 173.96 | False | gru_forecast | 2/2 | 4574 | answer 408.9 contradicts the series (implies 2476.3) |
| 27 | t013-d201 | 48 | none | solved | ok | 288 | 220.96 | None | gru_forecast | 2/2 | 7554 | valid series, coherent answer, traceable to a tool output |
| 28 | t013-d207 | 3 | peak_hour | wrong_unflagged | no_forecast_call | 18 | 130.63 | True | gru_forecast | 2/2 | 4335 | the series matches no forecast-tool output |
| 29 | t013-d207 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 212.96 | False | gru_forecast | 2/2 | 4621 | answer 103.5 contradicts the series (implies 3256.5) |
| 30 | t013-d207 | 48 | none | solved | ok | 288 | 297.98 | None | gru_forecast | 2/2 | 7591 | valid series, coherent answer, traceable to a tool output |
| 31 | t013-d212 | 3 | peak_hour | wrong_unflagged | ok | 18 | 177.14 | False | gru_forecast | 2/2 | 4335 | answer 18.0 contradicts the series (implies 3.0) |
| 32 | t013-d212 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 425.49 | False | gru_forecast | 2/2 | 4560 | answer 246.5 contradicts the series (implies 1539.3) |
| 33 | t013-d212 | 48 | none | solved | ok | 288 | 538.7 | None | gru_forecast | 2/2 | 7565 | valid series, coherent answer, traceable to a tool output |
| 34 | t013-d229 | 3 | peak_hour | solved | ok | 18 | 119.59 | True | gru_forecast | 2/2 | 4369 | valid series, coherent answer, traceable to a tool output |
| 35 | t013-d229 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 112.44 | False | gru_forecast | 2/2 | 4618 | answer 469.4 contradicts the series (implies 2751.0) |
| 36 | t013-d229 | 48 | none | wrong_unflagged | no_forecast_call | 288 | 519.83 | None | gru_forecast | 2/2 | 7549 | the series matches no forecast-tool output |
| 37 | t017-d201 | 3 | peak_hour | solved | ok | 18 | 128.81 | True | gru_forecast | 2/2 | 4336 | valid series, coherent answer, traceable to a tool output |
| 38 | t017-d201 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 139.45 | False | gru_forecast | 2/2 | 4583 | answer 408.4 contradicts the series (implies 2551.8) |
| 39 | t017-d201 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 2/1 | 9786 | no JSON answer: the output hit the token cap before the object was closed |
| 40 | t017-d207 | 3 | peak_hour | solved | ok | 18 | 101.8 | True | gru_forecast | 2/2 | 4367 | valid series, coherent answer, traceable to a tool output |
| 41 | t017-d207 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 136.23 | False | gru_forecast | 2/2 | 4606 | answer 389.4 contradicts the series (implies 2322.5) |
| 42 | t017-d207 | 48 | none | solved | ok | 288 | 246.47 | None | gru_forecast | 2/2 | 7547 | valid series, coherent answer, traceable to a tool output |
| 43 | t017-d212 | 3 | peak_hour | solved | ok | 18 | 219.4 | True | gru_forecast | 2/2 | 4353 | valid series, coherent answer, traceable to a tool output |
| 44 | t017-d212 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 290.25 | False | gru_forecast | 2/2 | 4558 | answer 601.5 contradicts the series (implies 3603.7) |
| 45 | t017-d212 | 48 | none | solved | ok | 288 | 468.37 | None | gru_forecast | 2/2 | 7550 | valid series, coherent answer, traceable to a tool output |
| 46 | t017-d229 | 3 | peak_hour | wrong_unflagged | no_forecast_call | 18 | 356.66 | True | persistence_forecast | 2/1 | 3936 | the series matches no forecast-tool output |
| 47 | t017-d229 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 107.94 | False | gru_forecast | 2/2 | 4556 | answer 431.5 contradicts the series (implies 2561.6) |
| 48 | t017-d229 | 48 | none | solved | ok | 288 | 453.21 | None | gru_forecast | 2/2 | 7543 | valid series, coherent answer, traceable to a tool output |
| 49 | t022-d201 | 3 | peak_hour | solved | ok | 18 | 96.85 | True | gru_forecast | 2/2 | 4379 | valid series, coherent answer, traceable to a tool output |
| 50 | t022-d201 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 136.37 | False | gru_forecast | 2/2 | 4560 | answer 103.5 contradicts the series (implies 2623.3) |
| 51 | t022-d201 | 48 | none | solved | ok | 288 | 205.24 | None | gru_forecast | 2/2 | 7548 | valid series, coherent answer, traceable to a tool output |
| 52 | t022-d207 | 3 | peak_hour | wrong_unflagged | no_forecast_call | 19 | None | False | gru_forecast | 2/1 | 3968 | 19 values, the horizon needs 18 |
| 53 | t022-d207 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 209.9 | False | gru_forecast | 2/2 | 4564 | answer 610.7 contradicts the series (implies 3613.1) |
| 54 | t022-d207 | 48 | none | solved | ok | 288 | 277.42 | None | gru_forecast | 2/2 | 7556 | valid series, coherent answer, traceable to a tool output |
| 55 | t022-d212 | 3 | peak_hour | wrong_unflagged | ok | 18 | 294.37 | False | gru_forecast | 2/2 | 4369 | answer 18.0 contradicts the series (implies 3.0) |
| 56 | t022-d212 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 553.68 | False | gru_forecast | 2/2 | 4585 | answer 186.5 contradicts the series (implies 1163.4) |
| 57 | t022-d212 | 48 | none | solved | ok | 288 | 546.21 | None | gru_forecast | 2/2 | 7549 | valid series, coherent answer, traceable to a tool output |
| 58 | t022-d229 | 3 | peak_hour | solved | ok | 18 | 223.63 | True | gru_forecast | 2/2 | 4332 | valid series, coherent answer, traceable to a tool output |
| 59 | t022-d229 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 241.45 | False | gru_forecast | 2/2 | 4582 | answer 368.5 contradicts the series (implies 2213.0) |
| 60 | t022-d229 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 2/1 | 9779 | no JSON answer: the output hit the token cap before the object was closed |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace), `.png` (the series against the target).

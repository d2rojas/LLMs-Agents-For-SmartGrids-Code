# llm_only_structured on SDWPF with gpt-4o-mini

Generated 2026-09-28 10:38 by evaluation/postprocess.py from `raw/rows.jsonl`. Requests: 60. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the frozen target days, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-28 |
| model | openrouter:openai/gpt-4o-mini |
| method | llm_only_structured |
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
| system_prompt_hash | 91a32237835b |
| git_commit | 2224ea80-dirty |
| gru_weights_hash | sha256:9a7b1330e56d249a |
| description | One call, no tools. The model reads the 14-day history as CSV and the physical rules, and writes the forecast values itself with the answer contract. The LLM as the predictor, which is the setting the paper's Section 6.1 tested. |
| prompt files | _shared/common_rules.txt, _shared/output_contract.txt, _shared/llm_only_system_prompt.txt |

## Where every request ended

The three outcomes are exclusive and sum to the request count. Escalation takes precedence: a request the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 14 | 23.3% |
| Escalated to a person | 0 | 0.0% |
| Wrong, unflagged | 46 | 76.7% |
| **Total** | **60** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Formulation exact | 40/60 (66.7%) |
| Task utility | Formulation error types | {'no_formulation': 20} |
| Task utility | MAE / RMSE / overall, kW, over valid series (n=24) | 458.42 / 504.02 / 481.22 |
| Task utility | NBIAS / NMAE / NRMSE, % of installed capacity (ANEMOS protocol) | 29.27 / 30.56 / 33.6 |
| Task utility | Improvement over the protocol's reference model, % (its NMAE 14.95 %) | -153.96 |
| Task utility | Improvement over persistence, % (its NMAE 30.2 %) | -2.39 |
| Task utility | MAE / RMSE, kW, over solved requests | 461.91 / 513.63 |
| Task utility | Answer coherent with the series | 14/39 |
| Solver-grounded correctness | Valid series (schema and range) | 24/60 (40.0%) |
| Solver-grounded correctness | Traceable series | 0/40 (0.0%) |
| Solver-grounded correctness | Wrong, unflagged | 46/60 (76.7%) |
| Cost and time | Escalated | 0/60 (0.0%) |
| Cost and time | LLM calls / tool calls, mean | 1.0 / 0.0 |
| Cost and time | Prompt / completion tokens, mean | 45922.03 / 2186.62 |
| Cost and time | Cost, total | $0.4920 |
| Cost and time | Wall time, mean | 28.01 s |

## By horizon

Every error is the mean over the requests of that horizon whose series was valid; a method that returns no valid series at a horizon has nothing to average, which is itself the finding. NMAE and NRMSE are normalised by the 1500 kW installed capacity, and Imp. is the improvement score of the ANEMOS protocol (Madsen et al. 2005) over its reference model, `a_k P(t) + (1-a_k) Pbar`, fitted on the training period; the improvement over plain persistence is beside it because persistence is the reference most readers know, and the protocol warns it flatters a model at long horizons.

| horizon | n | solved | scored | MAE kW | RMSE kW | NMAE % | NRMSE % | reference NMAE % | Imp. % | persistence NMAE % | Imp. vs pers. % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 h | 20 | 13 | 18 | 425.35 | 471.0 | 28.36 | 31.4 | 13.28 | -159.02 | 28.99 | 0.44 |
| 6 h | 20 | 1 | 6 | 557.63 | 603.06 | 37.18 | 40.2 | 19.98 | -138.8 | 33.83 | -10.88 |
| 48 h | 20 | 0 | 0 | None | None | None | None | None | None | None | None |

## Wrong and unflagged (46)

- `02_wind-t008-d201-h06-energy_kwh-s0`: 41 values, the horizon needs 36
- `03_wind-t008-d201-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `05_wind-t008-d207-h06-energy_kwh-s0`: 38 values, the horizon needs 36
- `06_wind-t008-d207-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `07_wind-t008-d212-h03-peak_hour-s0`: answer 1.0 contradicts the series (implies 2.0)
- `08_wind-t008-d212-h06-energy_kwh-s0`: 40 values, the horizon needs 36
- `09_wind-t008-d212-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `11_wind-t008-d229-h06-energy_kwh-s0`: values outside [0, 1600] kW: -1.0 to 68.3
- `12_wind-t008-d229-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `14_wind-t009-d201-h06-energy_kwh-s0`: 38 values, the horizon needs 36
- `15_wind-t009-d201-h48-none-s0`: 57 values, the horizon needs 288
- `17_wind-t009-d207-h06-energy_kwh-s0`: 38 values, the horizon needs 36
- `18_wind-t009-d207-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `20_wind-t009-d212-h06-energy_kwh-s0`: answer 1.0 contradicts the series (implies 18.0)
- `21_wind-t009-d212-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `23_wind-t009-d229-h06-energy_kwh-s0`: 35 values, the horizon needs 36
- `24_wind-t009-d229-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `25_wind-t013-d201-h03-peak_hour-s0`: answer 1.0 contradicts the series (implies 3.0)
- `26_wind-t013-d201-h06-energy_kwh-s0`: 37 values, the horizon needs 36
- `27_wind-t013-d201-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `29_wind-t013-d207-h06-energy_kwh-s0`: 39 values, the horizon needs 36
- `30_wind-t013-d207-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `32_wind-t013-d212-h06-energy_kwh-s0`: 37 values, the horizon needs 36
- `33_wind-t013-d212-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `35_wind-t013-d229-h06-energy_kwh-s0`: 31 values, the horizon needs 36
- `36_wind-t013-d229-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `37_wind-t017-d201-h03-peak_hour-s0`: answer 1.0 contradicts the series (implies 2.0)
- `38_wind-t017-d201-h06-energy_kwh-s0`: 38 values, the horizon needs 36
- `39_wind-t017-d201-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `40_wind-t017-d207-h03-peak_hour-s0`: 20 values, the horizon needs 18
- `41_wind-t017-d207-h06-energy_kwh-s0`: answer 1.0 contradicts the series (implies 27.4)
- `42_wind-t017-d207-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `44_wind-t017-d212-h06-energy_kwh-s0`: 38 values, the horizon needs 36
- `45_wind-t017-d212-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `46_wind-t017-d229-h03-peak_hour-s0`: answer 1.0 contradicts the series (implies 2.0)
- `47_wind-t017-d229-h06-energy_kwh-s0`: answer 6.0 contradicts the series (implies 24.5)
- `48_wind-t017-d229-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `49_wind-t022-d201-h03-peak_hour-s0`: no JSON answer: the output hit the token cap before the object was closed
- `50_wind-t022-d201-h06-energy_kwh-s0`: 37 values, the horizon needs 36
- `51_wind-t022-d201-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `52_wind-t022-d207-h03-peak_hour-s0`: answer 1.0 contradicts the series (implies 2.0)
- `53_wind-t022-d207-h06-energy_kwh-s0`: 38 values, the horizon needs 36
- `54_wind-t022-d207-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `57_wind-t022-d212-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `59_wind-t022-d229-h06-energy_kwh-s0`: answer 6.0 contradicts the series (implies 15.1)
- `60_wind-t022-d229-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed

## Escalated (0)

none

## Every request

| nn | instance | h | question | outcome | formulation | values | MAE | answer ok | source | LLM/tool calls | tokens | why |
|---|---|---:|---|---|---|---:|---:|---|---|---|---:|---|
| 01 | t008-d201 | 3 | peak_hour | solved | ok | 18 | 567.25 | True | persistence_forecast | 1/0 | 46128 | valid series, coherent answer (LLM-written, nothing to trace) |
| 02 | t008-d201 | 6 | energy_kwh | wrong_unflagged | ok | 41 | None | False | persistence_forecast | 1/0 | 46284 | 41 values, the horizon needs 36 |
| 03 | t008-d201 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 51894 | no JSON answer: the output hit the token cap before the object was closed |
| 04 | t008-d207 | 3 | peak_hour | solved | ok | 18 | 500.61 | True | persistence_forecast | 1/0 | 46330 | valid series, coherent answer (LLM-written, nothing to trace) |
| 05 | t008-d207 | 6 | energy_kwh | wrong_unflagged | ok | 38 | None | False | persistence_forecast | 1/0 | 46449 | 38 values, the horizon needs 36 |
| 06 | t008-d207 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 52096 | no JSON answer: the output hit the token cap before the object was closed |
| 07 | t008-d212 | 3 | peak_hour | wrong_unflagged | ok | 18 | 394.6 | False | persistence_forecast | 1/0 | 46170 | answer 1.0 contradicts the series (implies 2.0) |
| 08 | t008-d212 | 6 | energy_kwh | wrong_unflagged | ok | 40 | None | False | persistence_forecast | 1/0 | 46309 | 40 values, the horizon needs 36 |
| 09 | t008-d212 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 51933 | no JSON answer: the output hit the token cap before the object was closed |
| 10 | t008-d229 | 3 | peak_hour | solved | ok | 18 | 603.77 | True | power_curve_forecast | 1/0 | 46051 | valid series, coherent answer (LLM-written, nothing to trace) |
| 11 | t008-d229 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 578.24 | False | persistence_forecast | 1/0 | 46104 | values outside [0, 1600] kW: -1.0 to 68.3 |
| 12 | t008-d229 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 51794 | no JSON answer: the output hit the token cap before the object was closed |
| 13 | t009-d201 | 3 | peak_hour | solved | ok | 18 | 194.92 | True | persistence_forecast | 1/0 | 46153 | valid series, coherent answer (LLM-written, nothing to trace) |
| 14 | t009-d201 | 6 | energy_kwh | wrong_unflagged | ok | 38 | None | False | persistence_forecast | 1/0 | 46307 | 38 values, the horizon needs 36 |
| 15 | t009-d201 | 48 | none | wrong_unflagged | ok | 57 | None | None | persistence_forecast | 1/0 | 46332 | 57 values, the horizon needs 288 |
| 16 | t009-d207 | 3 | peak_hour | solved | ok | 18 | 255.21 | True | persistence_forecast | 1/0 | 46359 | valid series, coherent answer (LLM-written, nothing to trace) |
| 17 | t009-d207 | 6 | energy_kwh | wrong_unflagged | ok | 38 | None | False | persistence_forecast | 1/0 | 46487 | 38 values, the horizon needs 36 |
| 18 | t009-d207 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 52118 | no JSON answer: the output hit the token cap before the object was closed |
| 19 | t009-d212 | 3 | peak_hour | solved | ok | 18 | 423.87 | True | persistence_forecast | 1/0 | 46197 | valid series, coherent answer (LLM-written, nothing to trace) |
| 20 | t009-d212 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 716.0 | False | persistence_forecast | 1/0 | 46274 | answer 1.0 contradicts the series (implies 18.0) |
| 21 | t009-d212 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 51949 | no JSON answer: the output hit the token cap before the object was closed |
| 22 | t009-d229 | 3 | peak_hour | solved | ok | 18 | 611.91 | True | persistence_forecast | 1/0 | 46028 | valid series, coherent answer (LLM-written, nothing to trace) |
| 23 | t009-d229 | 6 | energy_kwh | wrong_unflagged | ok | 35 | None | False | power_curve_forecast | 1/0 | 46155 | 35 values, the horizon needs 36 |
| 24 | t009-d229 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 51812 | no JSON answer: the output hit the token cap before the object was closed |
| 25 | t013-d201 | 3 | peak_hour | wrong_unflagged | ok | 18 | 152.0 | False | persistence_forecast | 1/0 | 46105 | answer 1.0 contradicts the series (implies 3.0) |
| 26 | t013-d201 | 6 | energy_kwh | wrong_unflagged | ok | 37 | None | False | persistence_forecast | 1/0 | 46213 | 37 values, the horizon needs 36 |
| 27 | t013-d201 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 51869 | no JSON answer: the output hit the token cap before the object was closed |
| 28 | t013-d207 | 3 | peak_hour | solved | ok | 18 | 409.86 | True | persistence_forecast | 1/0 | 46276 | valid series, coherent answer (LLM-written, nothing to trace) |
| 29 | t013-d207 | 6 | energy_kwh | wrong_unflagged | ok | 39 | None | False | persistence_forecast | 1/0 | 46420 | 39 values, the horizon needs 36 |
| 30 | t013-d207 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 52056 | no JSON answer: the output hit the token cap before the object was closed |
| 31 | t013-d212 | 3 | peak_hour | solved | ok | 18 | 317.92 | True | persistence_forecast | 1/0 | 46127 | valid series, coherent answer (LLM-written, nothing to trace) |
| 32 | t013-d212 | 6 | energy_kwh | wrong_unflagged | ok | 37 | None | False | persistence_forecast | 1/0 | 46257 | 37 values, the horizon needs 36 |
| 33 | t013-d212 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 51907 | no JSON answer: the output hit the token cap before the object was closed |
| 34 | t013-d229 | 3 | peak_hour | solved | ok | 18 | 531.31 | True | persistence_forecast | 1/0 | 46029 | valid series, coherent answer (LLM-written, nothing to trace) |
| 35 | t013-d229 | 6 | energy_kwh | wrong_unflagged | ok | 31 | None | False | persistence_forecast | 1/0 | 46090 | 31 values, the horizon needs 36 |
| 36 | t013-d229 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 51789 | no JSON answer: the output hit the token cap before the object was closed |
| 37 | t017-d201 | 3 | peak_hour | wrong_unflagged | ok | 18 | 457.34 | False | persistence_forecast | 1/0 | 46017 | answer 1.0 contradicts the series (implies 2.0) |
| 38 | t017-d201 | 6 | energy_kwh | wrong_unflagged | ok | 38 | None | False | persistence_forecast | 1/0 | 46163 | 38 values, the horizon needs 36 |
| 39 | t017-d201 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 51787 | no JSON answer: the output hit the token cap before the object was closed |
| 40 | t017-d207 | 3 | peak_hour | wrong_unflagged | ok | 20 | None | False | mean_of_tools | 1/0 | 46246 | 20 values, the horizon needs 18 |
| 41 | t017-d207 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 260.39 | False | persistence_forecast | 1/0 | 46301 | answer 1.0 contradicts the series (implies 27.4) |
| 42 | t017-d207 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 51973 | no JSON answer: the output hit the token cap before the object was closed |
| 43 | t017-d212 | 3 | peak_hour | solved | ok | 18 | 380.49 | True | power_curve_forecast | 1/0 | 46087 | valid series, coherent answer (LLM-written, nothing to trace) |
| 44 | t017-d212 | 6 | energy_kwh | wrong_unflagged | ok | 38 | None | False | persistence_forecast | 1/0 | 46196 | 38 values, the horizon needs 36 |
| 45 | t017-d212 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 51826 | no JSON answer: the output hit the token cap before the object was closed |
| 46 | t017-d229 | 3 | peak_hour | wrong_unflagged | ok | 18 | 411.91 | False | persistence_forecast | 1/0 | 46067 | answer 1.0 contradicts the series (implies 2.0) |
| 47 | t017-d229 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 470.96 | False | persistence_forecast | 1/0 | 46183 | answer 6.0 contradicts the series (implies 24.5) |
| 48 | t017-d229 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 51823 | no JSON answer: the output hit the token cap before the object was closed |
| 49 | t022-d201 | 3 | peak_hour | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 51859 | no JSON answer: the output hit the token cap before the object was closed |
| 50 | t022-d201 | 6 | energy_kwh | wrong_unflagged | ok | 37 | None | False | persistence_forecast | 1/0 | 46187 | 37 values, the horizon needs 36 |
| 51 | t022-d201 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 51831 | no JSON answer: the output hit the token cap before the object was closed |
| 52 | t022-d207 | 3 | peak_hour | wrong_unflagged | ok | 18 | 493.69 | False | persistence_forecast | 1/0 | 46299 | answer 1.0 contradicts the series (implies 2.0) |
| 53 | t022-d207 | 6 | energy_kwh | wrong_unflagged | ok | 38 | None | False | persistence_forecast | 1/0 | 46439 | 38 values, the horizon needs 36 |
| 54 | t022-d207 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 52069 | no JSON answer: the output hit the token cap before the object was closed |
| 55 | t022-d212 | 3 | peak_hour | solved | ok | 18 | 411.28 | True | persistence_forecast | 1/0 | 46149 | valid series, coherent answer (LLM-written, nothing to trace) |
| 56 | t022-d212 | 6 | energy_kwh | solved | ok | 36 | 719.87 | True | persistence_forecast | 1/0 | 46220 | valid series, coherent answer (LLM-written, nothing to trace) |
| 57 | t022-d212 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 51908 | no JSON answer: the output hit the token cap before the object was closed |
| 58 | t022-d229 | 3 | peak_hour | solved | ok | 18 | 538.42 | True | power_curve_forecast | 1/0 | 46056 | valid series, coherent answer (LLM-written, nothing to trace) |
| 59 | t022-d229 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 600.3 | False | persistence_forecast | 1/0 | 46159 | answer 6.0 contradicts the series (implies 15.1) |
| 60 | t022-d229 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 51823 | no JSON answer: the output hit the token cap before the object was closed |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace), `.png` (the series against the target).

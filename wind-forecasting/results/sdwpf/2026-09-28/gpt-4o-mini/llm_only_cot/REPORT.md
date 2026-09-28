# llm_only_cot on SDWPF with gpt-4o-mini

Generated 2026-09-28 12:38 by evaluation/postprocess.py from `raw/rows.jsonl`. Requests: 60. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the frozen target days, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-28 |
| model | openrouter:openai/gpt-4o-mini |
| method | llm_only_cot |
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
| description | The structured prompt plus one reasoning section asking the model to reason step by step before the answer. Identical to the row above in every other respect. |
| prompt files | _shared/common_rules.txt, _shared/output_contract.txt, _shared/llm_only_system_prompt.txt, llm_only_cot/reasoning_section.txt |

## Where every request ended

The three outcomes are exclusive and sum to the request count. Escalation takes precedence: a request the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 15 | 25.0% |
| Escalated to a person | 0 | 0.0% |
| Wrong, unflagged | 45 | 75.0% |
| **Total** | **60** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Formulation exact | 41/60 (68.3%) |
| Task utility | Formulation error types | {'no_formulation': 19} |
| Task utility | MAE / RMSE / overall, kW, over valid series (n=25) | 309.67 / 344.97 / 327.32 |
| Task utility | NBIAS / NMAE / NRMSE, % of installed capacity (ANEMOS protocol), over valid series (n=25) | 17.42 / 20.64 / 23.0 |
| Task utility | Improvement over the protocol's reference model, % (its NMAE 12.2 %), over valid series (n=25) | -84.36 |
| Task utility | Improvement over persistence, % (its NMAE 27.99 %), over valid series (n=25) | 24.99 |
| Task utility | MAE / RMSE, kW, over solved requests | 304.58 / 346.17 |
| Task utility | Answer coherent with the series | 15/34 |
| Solver-grounded correctness | Valid series (schema and range) | 25/60 (41.7%) |
| Solver-grounded correctness | Traceable series | 0/41 (0.0%) |
| Solver-grounded correctness | Wrong, unflagged | 45/60 (75.0%) |
| Cost and time | Escalated | 0/60 (0.0%) |
| Cost and time | LLM calls / tool calls, mean | 1.0 / 0.0 |
| Cost and time | Prompt / completion tokens, mean | 46035.03 / 2611.27 |
| Cost and time | Cost, total | $0.5083 |
| Cost and time | Wall time, mean | 34.04 s |

## By horizon

Every error is the mean over the requests of that horizon whose series was valid; a method that returns no valid series at a horizon has nothing to average, which is itself the finding. NMAE and NRMSE are normalised by the 1500 kW installed capacity, and Imp. is the improvement score of the ANEMOS protocol (Madsen et al. 2005) over its reference model, `a_k P(t) + (1-a_k) Pbar`, fitted on the training period; the improvement over plain persistence is beside it because persistence is the reference most readers know, and the protocol warns it flatters a model at long horizons.

| horizon | n | solved | scored | MAE kW | RMSE kW | NMAE % | NRMSE % | reference NMAE % | Imp. % | persistence NMAE % | Imp. vs pers. % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 h | 20 | 14 | 14 | 287.01 | 330.69 | 19.13 | 22.05 | 11.93 | -82.69 | 28.98 | 32.76 |
| 6 h | 20 | 1 | 11 | 338.51 | 363.16 | 22.57 | 24.21 | 12.54 | -86.49 | 26.73 | 15.09 |
| 48 h | 20 | 0 | 0 | None | None | None | None | None | None | None | None |

## Wrong and unflagged (45)

- `02_wind-t008-d201-h06-energy_kwh-s0`: answer 6.0 contradicts the series (implies 48.9)
- `03_wind-t008-d201-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `04_wind-t008-d207-h03-peak_hour-s0`: no answer with the contract
- `05_wind-t008-d207-h06-energy_kwh-s0`: no answer with the contract
- `06_wind-t008-d207-h48-none-s0`: 367 values, the horizon needs 288
- `08_wind-t008-d212-h06-energy_kwh-s0`: 38 values, the horizon needs 36
- `09_wind-t008-d212-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `11_wind-t008-d229-h06-energy_kwh-s0`: 38 values, the horizon needs 36
- `12_wind-t008-d229-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `14_wind-t009-d201-h06-energy_kwh-s0`: answer 1.0 contradicts the series (implies 883.3)
- `15_wind-t009-d201-h48-none-s0`: 198 values, the horizon needs 288
- `17_wind-t009-d207-h06-energy_kwh-s0`: answer 5.0 contradicts the series (implies 2520.0)
- `18_wind-t009-d207-h48-none-s0`: 468 values, the horizon needs 288
- `19_wind-t009-d212-h03-peak_hour-s0`: no answer with the contract
- `20_wind-t009-d212-h06-energy_kwh-s0`: no answer with the contract
- `21_wind-t009-d212-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `23_wind-t009-d229-h06-energy_kwh-s0`: answer 468.38 contradicts the series (implies 2810.3)
- `24_wind-t009-d229-h48-none-s0`: 204 values, the horizon needs 288
- `26_wind-t013-d201-h06-energy_kwh-s0`: answer 171.8 contradicts the series (implies 1149.5)
- `27_wind-t013-d201-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `29_wind-t013-d207-h06-energy_kwh-s0`: answer 1947.1 contradicts the series (implies 1755.1)
- `30_wind-t013-d207-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `32_wind-t013-d212-h06-energy_kwh-s0`: no answer with the contract
- `33_wind-t013-d212-h48-none-s0`: 269 values, the horizon needs 288
- `36_wind-t013-d229-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `38_wind-t017-d201-h06-energy_kwh-s0`: 37 values, the horizon needs 36
- `39_wind-t017-d201-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `40_wind-t017-d207-h03-peak_hour-s0`: 16 values, the horizon needs 18
- `41_wind-t017-d207-h06-energy_kwh-s0`: answer 38.75 contradicts the series (implies 37.0)
- `42_wind-t017-d207-h48-none-s0`: 108 values, the horizon needs 288
- `44_wind-t017-d212-h06-energy_kwh-s0`: 38 values, the horizon needs 36
- `45_wind-t017-d212-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `47_wind-t017-d229-h06-energy_kwh-s0`: answer 150.0 contradicts the series (implies 377.7)
- `48_wind-t017-d229-h48-none-s0`: 216 values, the horizon needs 288
- `49_wind-t022-d201-h03-peak_hour-s0`: 19 values, the horizon needs 18
- `50_wind-t022-d201-h06-energy_kwh-s0`: answer 200.0 contradicts the series (implies 1364.1)
- `51_wind-t022-d201-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `53_wind-t022-d207-h06-energy_kwh-s0`: 38 values, the horizon needs 36
- `54_wind-t022-d207-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `55_wind-t022-d212-h03-peak_hour-s0`: no answer with the contract
- `56_wind-t022-d212-h06-energy_kwh-s0`: 38 values, the horizon needs 36
- `57_wind-t022-d212-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed
- `58_wind-t022-d229-h03-peak_hour-s0`: 19 values, the horizon needs 18
- `59_wind-t022-d229-h06-energy_kwh-s0`: answer 333.33 contradicts the series (implies 459.9)
- `60_wind-t022-d229-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed

## Escalated (0)

none

## Every request

| nn | instance | h | question | outcome | formulation | values | MAE | answer ok | source | LLM/tool calls | tokens | why |
|---|---|---:|---|---|---|---:|---:|---|---|---|---:|---|
| 01 | t008-d201 | 3 | peak_hour | solved | ok | 18 | 518.14 | True | own_computation | 1/0 | 46860 | valid series, coherent answer (LLM-written, nothing to trace) |
| 02 | t008-d201 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 555.44 | False | own_computation | 1/0 | 47269 | answer 6.0 contradicts the series (implies 48.9) |
| 03 | t008-d201 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 54007 | no JSON answer: the output hit the token cap before the object was closed |
| 04 | t008-d207 | 3 | peak_hour | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 47213 | no answer with the contract |
| 05 | t008-d207 | 6 | energy_kwh | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 47217 | no answer with the contract |
| 06 | t008-d207 | 48 | none | wrong_unflagged | ok | 367 | None | None | own_computation | 1/0 | 50569 | 367 values, the horizon needs 288 |
| 07 | t008-d212 | 3 | peak_hour | solved | ok | 18 | 397.78 | True | persistence_forecast | 1/0 | 46979 | valid series, coherent answer (LLM-written, nothing to trace) |
| 08 | t008-d212 | 6 | energy_kwh | wrong_unflagged | ok | 38 | None | False | own_computation | 1/0 | 47110 | 38 values, the horizon needs 36 |
| 09 | t008-d212 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 54046 | no JSON answer: the output hit the token cap before the object was closed |
| 10 | t008-d229 | 3 | peak_hour | solved | ok | 18 | 376.09 | True | own_computation | 1/0 | 46916 | valid series, coherent answer (LLM-written, nothing to trace) |
| 11 | t008-d229 | 6 | energy_kwh | wrong_unflagged | ok | 38 | None | False | own_computation | 1/0 | 47132 | 38 values, the horizon needs 36 |
| 12 | t008-d229 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 53907 | no JSON answer: the output hit the token cap before the object was closed |
| 13 | t009-d201 | 3 | peak_hour | solved | ok | 18 | 279.92 | True | persistence_forecast | 1/0 | 46912 | valid series, coherent answer (LLM-written, nothing to trace) |
| 14 | t009-d201 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 431.13 | False | own_computation | 1/0 | 46946 | answer 1.0 contradicts the series (implies 883.3) |
| 15 | t009-d201 | 48 | none | wrong_unflagged | ok | 198 | None | None | own_computation | 1/0 | 47633 | 198 values, the horizon needs 288 |
| 16 | t009-d207 | 3 | peak_hour | solved | ok | 18 | 129.06 | True | own_computation | 1/0 | 47105 | valid series, coherent answer (LLM-written, nothing to trace) |
| 17 | t009-d207 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 100.96 | False | own_computation | 1/0 | 47123 | answer 5.0 contradicts the series (implies 2520.0) |
| 18 | t009-d207 | 48 | none | wrong_unflagged | ok | 468 | None | None | persistence_forecast | 1/0 | 49219 | 468 values, the horizon needs 288 |
| 19 | t009-d212 | 3 | peak_hour | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 47082 | no answer with the contract |
| 20 | t009-d212 | 6 | energy_kwh | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 47036 | no answer with the contract |
| 21 | t009-d212 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 54062 | no JSON answer: the output hit the token cap before the object was closed |
| 22 | t009-d229 | 3 | peak_hour | solved | ok | 18 | 314.0 | True | own_computation | 1/0 | 46578 | valid series, coherent answer (LLM-written, nothing to trace) |
| 23 | t009-d229 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 137.78 | False | persistence_forecast | 1/0 | 46731 | answer 468.38 contradicts the series (implies 2810.3) |
| 24 | t009-d229 | 48 | none | wrong_unflagged | ok | 204 | None | None | persistence_forecast | 1/0 | 47326 | 204 values, the horizon needs 288 |
| 25 | t013-d201 | 3 | peak_hour | solved | ok | 18 | 227.82 | True | own_computation | 1/0 | 47004 | valid series, coherent answer (LLM-written, nothing to trace) |
| 26 | t013-d201 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 380.43 | False | own_computation | 1/0 | 47209 | answer 171.8 contradicts the series (implies 1149.5) |
| 27 | t013-d201 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 53982 | no JSON answer: the output hit the token cap before the object was closed |
| 28 | t013-d207 | 3 | peak_hour | solved | ok | 18 | 171.72 | True | persistence_forecast | 1/0 | 46971 | valid series, coherent answer (LLM-written, nothing to trace) |
| 29 | t013-d207 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 76.15 | False | own_computation | 1/0 | 47322 | answer 1947.1 contradicts the series (implies 1755.1) |
| 30 | t013-d207 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 54169 | no JSON answer: the output hit the token cap before the object was closed |
| 31 | t013-d212 | 3 | peak_hour | solved | ok | 18 | 313.77 | True | own_computation | 1/0 | 46805 | valid series, coherent answer (LLM-written, nothing to trace) |
| 32 | t013-d212 | 6 | energy_kwh | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 47064 | no answer with the contract |
| 33 | t013-d212 | 48 | none | wrong_unflagged | ok | 269 | None | None | own_computation | 1/0 | 47532 | 269 values, the horizon needs 288 |
| 34 | t013-d229 | 3 | peak_hour | solved | ok | 18 | 292.6 | True | own_computation | 1/0 | 46603 | valid series, coherent answer (LLM-written, nothing to trace) |
| 35 | t013-d229 | 6 | energy_kwh | solved | ok | 36 | 550.47 | True | persistence_forecast | 1/0 | 46687 | valid series, coherent answer (LLM-written, nothing to trace) |
| 36 | t013-d229 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 53902 | no JSON answer: the output hit the token cap before the object was closed |
| 37 | t017-d201 | 3 | peak_hour | solved | ok | 18 | 251.97 | True | own_computation | 1/0 | 46710 | valid series, coherent answer (LLM-written, nothing to trace) |
| 38 | t017-d201 | 6 | energy_kwh | wrong_unflagged | ok | 37 | None | False | own_computation | 1/0 | 46980 | 37 values, the horizon needs 36 |
| 39 | t017-d201 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 53900 | no JSON answer: the output hit the token cap before the object was closed |
| 40 | t017-d207 | 3 | peak_hour | wrong_unflagged | ok | 16 | None | False | own_computation | 1/0 | 47224 | 16 values, the horizon needs 18 |
| 41 | t017-d207 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 258.79 | False | own_computation | 1/0 | 47354 | answer 38.75 contradicts the series (implies 37.0) |
| 42 | t017-d207 | 48 | none | wrong_unflagged | ok | 108 | None | None | own_computation | 1/0 | 47316 | 108 values, the horizon needs 288 |
| 43 | t017-d212 | 3 | peak_hour | solved | ok | 18 | 140.62 | True | own_computation | 1/0 | 47030 | valid series, coherent answer (LLM-written, nothing to trace) |
| 44 | t017-d212 | 6 | energy_kwh | wrong_unflagged | ok | 38 | None | False | own_computation | 1/0 | 46976 | 38 values, the horizon needs 36 |
| 45 | t017-d212 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 53939 | no JSON answer: the output hit the token cap before the object was closed |
| 46 | t017-d229 | 3 | peak_hour | solved | ok | 18 | 261.92 | True | own_computation | 1/0 | 46997 | valid series, coherent answer (LLM-written, nothing to trace) |
| 47 | t017-d229 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 422.27 | False | own_computation | 1/0 | 46716 | answer 150.0 contradicts the series (implies 377.7) |
| 48 | t017-d229 | 48 | none | wrong_unflagged | ok | 216 | None | None | own_computation | 1/0 | 47301 | 216 values, the horizon needs 288 |
| 49 | t022-d201 | 3 | peak_hour | wrong_unflagged | ok | 19 | None | False | own_computation | 1/0 | 46833 | 19 values, the horizon needs 18 |
| 50 | t022-d201 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 284.07 | False | own_computation | 1/0 | 46778 | answer 200.0 contradicts the series (implies 1364.1) |
| 51 | t022-d201 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 53944 | no JSON answer: the output hit the token cap before the object was closed |
| 52 | t022-d207 | 3 | peak_hour | solved | ok | 18 | 342.78 | True | own_computation | 1/0 | 47279 | valid series, coherent answer (LLM-written, nothing to trace) |
| 53 | t022-d207 | 6 | energy_kwh | wrong_unflagged | ok | 38 | None | False | own_computation | 1/0 | 47023 | 38 values, the horizon needs 36 |
| 54 | t022-d207 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 54182 | no JSON answer: the output hit the token cap before the object was closed |
| 55 | t022-d212 | 3 | peak_hour | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 46988 | no answer with the contract |
| 56 | t022-d212 | 6 | energy_kwh | wrong_unflagged | ok | 38 | None | False | own_computation | 1/0 | 47004 | 38 values, the horizon needs 36 |
| 57 | t022-d212 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 54021 | no JSON answer: the output hit the token cap before the object was closed |
| 58 | t022-d229 | 3 | peak_hour | wrong_unflagged | ok | 19 | None | False | own_computation | 1/0 | 46942 | 19 values, the horizon needs 18 |
| 59 | t022-d229 | 6 | energy_kwh | wrong_unflagged | ok | 36 | 526.17 | False | own_computation | 1/0 | 47177 | answer 333.33 contradicts the series (implies 459.9) |
| 60 | t022-d229 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 53936 | no JSON answer: the output hit the token cap before the object was closed |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace), `.png` (the series against the target).

# windagent on SDWPF with gpt-4o-mini

Generated 2026-09-28 12:38 by evaluation/postprocess.py from `raw/rows.jsonl`. Requests: 60. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the frozen target days, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-28 |
| model | openrouter:openai/gpt-4o-mini |
| method | windagent |
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
| description | The same loop as ReAct plus the verification gate W1-W5 on the final answer: schema, physical range, traceability to a tool output, consistency of the declared formulation with the call that produced the series, and coherence of the answer with the series. One retry, then a declared failure. The solver-grounded row. |
| prompt files | _shared/common_rules.txt, _shared/output_contract.txt, _shared/agent_system_prompt.txt, _shared/gate_retry_instruction.txt |

## Where every request ended

The three outcomes are exclusive and sum to the request count. Escalation takes precedence: a request the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 16 | 26.7% |
| Escalated to a person | 44 | 73.3% |
| Wrong, unflagged | 0 | 0.0% |
| **Total** | **60** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Formulation exact | 60/60 (100.0%) |
| Task utility | Formulation error types | {} |
| Task utility | MAE / RMSE / overall, kW, over valid series (n=16) | 302.51 / 356.31 / 329.41 |
| Task utility | NBIAS / NMAE / NRMSE, % of installed capacity (ANEMOS protocol), over valid series (n=16) | 10.91 / 20.17 / 23.75 |
| Task utility | Improvement over the protocol's reference model, % (its NMAE 17.65 %), over valid series (n=16) | -23.37 |
| Task utility | Improvement over persistence, % (its NMAE 30.43 %), over valid series (n=16) | 32.4 |
| Task utility | MAE / RMSE, kW, over solved requests | 302.51 / 356.31 |
| Task utility | Answer coherent with the series | 7/7 |
| Solver-grounded correctness | Valid series (schema and range) | 16/60 (26.7%) |
| Solver-grounded correctness | Traceable series | 16/16 (100.0%) |
| Solver-grounded correctness | Wrong, unflagged | 0/60 (0.0%) |
| Cost and time | Escalated | 44/60 (73.3%) |
| Cost and time | LLM calls / tool calls, mean | 5.78 / 9.83 |
| Cost and time | Prompt / completion tokens, mean | 33881.85 / 2274.88 |
| Cost and time | Cost, total | $0.3868 |
| Cost and time | Wall time, mean | 23.04 s |

## By horizon

Every error is the mean over the requests of that horizon whose series was valid; a method that returns no valid series at a horizon has nothing to average, which is itself the finding. NMAE and NRMSE are normalised by the 1500 kW installed capacity, and Imp. is the improvement score of the ANEMOS protocol (Madsen et al. 2005) over its reference model, `a_k P(t) + (1-a_k) Pbar`, fitted on the training period; the improvement over plain persistence is beside it because persistence is the reference most readers know, and the protocol warns it flatters a model at long horizons.

| horizon | n | solved | scored | MAE kW | RMSE kW | NMAE % | NRMSE % | reference NMAE % | Imp. % | persistence NMAE % | Imp. vs pers. % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 h | 20 | 7 | 7 | 310.3 | 338.97 | 20.69 | 22.6 | 13.68 | -58.47 | 31.19 | 32.3 |
| 6 h | 20 | 0 | 0 | None | None | None | None | None | None | None | None |
| 48 h | 20 | 9 | 9 | 296.45 | 369.81 | 19.76 | 24.65 | 20.73 | 3.93 | 29.84 | 32.48 |

## Wrong and unflagged (0)

none

## Escalated (44)

- `02_wind-t008-d201-h06-energy_kwh-s0`: escalated: declared cannot_forecast
- `05_wind-t008-d207-h06-energy_kwh-s0`: escalated: gate rejected coherent, declared cannot_forecast
- `06_wind-t008-d207-h48-none-s0`: escalated: declared cannot_forecast
- `07_wind-t008-d212-h03-peak_hour-s0`: escalated: declared cannot_forecast
- `08_wind-t008-d212-h06-energy_kwh-s0`: escalated: declared cannot_forecast
- `09_wind-t008-d212-h48-none-s0`: escalated: declared cannot_forecast
- `10_wind-t008-d229-h03-peak_hour-s0`: escalated: gate rejected schema, coherent, declared cannot_forecast
- `11_wind-t008-d229-h06-energy_kwh-s0`: escalated: declared cannot_forecast
- `12_wind-t008-d229-h48-none-s0`: escalated: declared cannot_forecast
- `14_wind-t009-d201-h06-energy_kwh-s0`: escalated: declared cannot_forecast
- `16_wind-t009-d207-h03-peak_hour-s0`: escalated: declared cannot_forecast
- `17_wind-t009-d207-h06-energy_kwh-s0`: escalated: declared cannot_forecast
- `18_wind-t009-d207-h48-none-s0`: escalated: declared cannot_forecast
- `20_wind-t009-d212-h06-energy_kwh-s0`: escalated: gate rejected coherent, declared cannot_forecast
- `21_wind-t009-d212-h48-none-s0`: escalated: declared cannot_forecast
- `22_wind-t009-d229-h03-peak_hour-s0`: escalated: declared cannot_forecast
- `23_wind-t009-d229-h06-energy_kwh-s0`: escalated: declared cannot_forecast
- `24_wind-t009-d229-h48-none-s0`: escalated: declared cannot_forecast
- `26_wind-t013-d201-h06-energy_kwh-s0`: escalated: gate rejected coherent, declared cannot_forecast
- `28_wind-t013-d207-h03-peak_hour-s0`: escalated: declared cannot_forecast
- `29_wind-t013-d207-h06-energy_kwh-s0`: escalated: declared cannot_forecast
- `31_wind-t013-d212-h03-peak_hour-s0`: escalated: declared cannot_forecast
- `32_wind-t013-d212-h06-energy_kwh-s0`: escalated: gate rejected coherent, declared cannot_forecast
- `33_wind-t013-d212-h48-none-s0`: escalated: declared cannot_forecast
- `34_wind-t013-d229-h03-peak_hour-s0`: escalated: declared cannot_forecast
- `35_wind-t013-d229-h06-energy_kwh-s0`: escalated: gate rejected coherent, declared cannot_forecast
- `36_wind-t013-d229-h48-none-s0`: escalated: declared cannot_forecast
- `38_wind-t017-d201-h06-energy_kwh-s0`: escalated: gate rejected coherent, declared cannot_forecast
- `40_wind-t017-d207-h03-peak_hour-s0`: escalated: declared cannot_forecast
- `41_wind-t017-d207-h06-energy_kwh-s0`: escalated: declared cannot_forecast
- `42_wind-t017-d207-h48-none-s0`: escalated: declared cannot_forecast
- `43_wind-t017-d212-h03-peak_hour-s0`: escalated: declared cannot_forecast
- `44_wind-t017-d212-h06-energy_kwh-s0`: escalated: declared cannot_forecast
- `45_wind-t017-d212-h48-none-s0`: escalated: declared cannot_forecast
- `46_wind-t017-d229-h03-peak_hour-s0`: escalated: declared cannot_forecast
- `47_wind-t017-d229-h06-energy_kwh-s0`: escalated: declared cannot_forecast
- `49_wind-t022-d201-h03-peak_hour-s0`: escalated: declared cannot_forecast
- `50_wind-t022-d201-h06-energy_kwh-s0`: escalated: declared cannot_forecast
- `53_wind-t022-d207-h06-energy_kwh-s0`: escalated: gate rejected coherent, declared cannot_forecast
- `55_wind-t022-d212-h03-peak_hour-s0`: escalated: declared cannot_forecast
- `56_wind-t022-d212-h06-energy_kwh-s0`: escalated: gate rejected coherent, declared cannot_forecast
- `58_wind-t022-d229-h03-peak_hour-s0`: escalated: gate rejected coherent, declared cannot_forecast
- `59_wind-t022-d229-h06-energy_kwh-s0`: escalated: declared cannot_forecast
- `60_wind-t022-d229-h48-none-s0`: escalated: gate rejected schema, range, traceable, consistent, declared cannot_forecast

## Every request

| nn | instance | h | question | outcome | formulation | values | MAE | answer ok | source | LLM/tool calls | tokens | why |
|---|---|---:|---|---|---|---:|---:|---|---|---|---:|---|
| 01 | t008-d201 | 3 | peak_hour | solved | ok | 18 | 166.09 | True | gru_forecast | 4/7 | 12769 | valid series, coherent answer, traceable to a tool output |
| 02 | t008-d201 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 7/11 | 37984 | escalated: declared cannot_forecast |
| 03 | t008-d201 | 48 | none | solved | ok | 288 | 238.56 | None | gru_forecast | 5/9 | 28527 | valid series, coherent answer, traceable to a tool output |
| 04 | t008-d207 | 3 | peak_hour | solved | ok | 18 | 238.24 | True | gru_forecast | 5/8 | 22129 | valid series, coherent answer, traceable to a tool output |
| 05 | t008-d207 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 5/9 | 15946 | escalated: gate rejected coherent, declared cannot_forecast |
| 06 | t008-d207 | 48 | none | escalated | ok | 0 | None | None | None | 6/10 | 52957 | escalated: declared cannot_forecast |
| 07 | t008-d212 | 3 | peak_hour | escalated | ok | 0 | None | None | None | 6/11 | 21820 | escalated: declared cannot_forecast |
| 08 | t008-d212 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 6/11 | 25140 | escalated: declared cannot_forecast |
| 09 | t008-d212 | 48 | none | escalated | ok | 0 | None | None | None | 6/11 | 53039 | escalated: declared cannot_forecast |
| 10 | t008-d229 | 3 | peak_hour | escalated | ok | 0 | None | None | None | 8/11 | 76205 | escalated: gate rejected schema, coherent, declared cannot_forecast |
| 11 | t008-d229 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 6/11 | 37945 | escalated: declared cannot_forecast |
| 12 | t008-d229 | 48 | none | escalated | ok | 0 | None | None | None | 6/11 | 48951 | escalated: declared cannot_forecast |
| 13 | t009-d201 | 3 | peak_hour | solved | ok | 18 | 486.25 | True | mean_of_tools | 4/7 | 12614 | valid series, coherent answer, traceable to a tool output |
| 14 | t009-d201 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 6/11 | 24311 | escalated: declared cannot_forecast |
| 15 | t009-d201 | 48 | none | solved | ok | 288 | 244.58 | None | gru_forecast | 5/9 | 28547 | valid series, coherent answer, traceable to a tool output |
| 16 | t009-d207 | 3 | peak_hour | escalated | ok | 0 | None | None | None | 7/10 | 24738 | escalated: declared cannot_forecast |
| 17 | t009-d207 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 6/10 | 23587 | escalated: declared cannot_forecast |
| 18 | t009-d207 | 48 | none | escalated | ok | 0 | None | None | None | 6/11 | 52947 | escalated: declared cannot_forecast |
| 19 | t009-d212 | 3 | peak_hour | solved | ok | 18 | 289.87 | True | gru_forecast | 4/6 | 14940 | valid series, coherent answer, traceable to a tool output |
| 20 | t009-d212 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 6/11 | 32026 | escalated: gate rejected coherent, declared cannot_forecast |
| 21 | t009-d212 | 48 | none | escalated | ok | 0 | None | None | None | 6/11 | 49911 | escalated: declared cannot_forecast |
| 22 | t009-d229 | 3 | peak_hour | escalated | ok | 0 | None | None | None | 6/11 | 21765 | escalated: declared cannot_forecast |
| 23 | t009-d229 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 6/11 | 24320 | escalated: declared cannot_forecast |
| 24 | t009-d229 | 48 | none | escalated | ok | 0 | None | None | None | 6/11 | 49035 | escalated: declared cannot_forecast |
| 25 | t013-d201 | 3 | peak_hour | solved | ok | 18 | 500.43 | True | mean_of_tools | 4/7 | 12651 | valid series, coherent answer, traceable to a tool output |
| 26 | t013-d201 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 6/10 | 29473 | escalated: gate rejected coherent, declared cannot_forecast |
| 27 | t013-d201 | 48 | none | solved | ok | 288 | 220.96 | None | gru_forecast | 5/9 | 28529 | valid series, coherent answer, traceable to a tool output |
| 28 | t013-d207 | 3 | peak_hour | escalated | ok | 0 | None | None | None | 6/11 | 21242 | escalated: declared cannot_forecast |
| 29 | t013-d207 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 7/12 | 42517 | escalated: declared cannot_forecast |
| 30 | t013-d207 | 48 | none | solved | ok | 288 | 297.98 | None | gru_forecast | 7/10 | 222317 | valid series, coherent answer, traceable to a tool output |
| 31 | t013-d212 | 3 | peak_hour | escalated | ok | 0 | None | None | None | 6/11 | 21478 | escalated: declared cannot_forecast |
| 32 | t013-d212 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 5/9 | 15988 | escalated: gate rejected coherent, declared cannot_forecast |
| 33 | t013-d212 | 48 | none | escalated | ok | 0 | None | None | None | 6/11 | 53034 | escalated: declared cannot_forecast |
| 34 | t013-d229 | 3 | peak_hour | escalated | ok | 0 | None | None | None | 7/13 | 64569 | escalated: declared cannot_forecast |
| 35 | t013-d229 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 5/9 | 16002 | escalated: gate rejected coherent, declared cannot_forecast |
| 36 | t013-d229 | 48 | none | escalated | ok | 0 | None | None | None | 6/11 | 48679 | escalated: declared cannot_forecast |
| 37 | t017-d201 | 3 | peak_hour | solved | ok | 18 | 411.7 | True | mean_of_tools | 4/7 | 12606 | valid series, coherent answer, traceable to a tool output |
| 38 | t017-d201 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 6/10 | 29522 | escalated: gate rejected coherent, declared cannot_forecast |
| 39 | t017-d201 | 48 | none | solved | ok | 288 | 183.87 | None | gru_forecast | 4/6 | 24275 | valid series, coherent answer, traceable to a tool output |
| 40 | t017-d207 | 3 | peak_hour | escalated | ok | 0 | None | None | None | 6/10 | 32854 | escalated: declared cannot_forecast |
| 41 | t017-d207 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 6/10 | 23413 | escalated: declared cannot_forecast |
| 42 | t017-d207 | 48 | none | escalated | ok | 0 | None | None | None | 6/11 | 52937 | escalated: declared cannot_forecast |
| 43 | t017-d212 | 3 | peak_hour | escalated | ok | 0 | None | None | None | 6/11 | 22593 | escalated: declared cannot_forecast |
| 44 | t017-d212 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 6/11 | 26727 | escalated: declared cannot_forecast |
| 45 | t017-d212 | 48 | none | escalated | ok | 0 | None | None | None | 6/11 | 52926 | escalated: declared cannot_forecast |
| 46 | t017-d229 | 3 | peak_hour | escalated | ok | 0 | None | None | None | 6/11 | 22024 | escalated: declared cannot_forecast |
| 47 | t017-d229 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 8/10 | 45827 | escalated: declared cannot_forecast |
| 48 | t017-d229 | 48 | none | solved | ok | 288 | 453.21 | None | gru_forecast | 4/6 | 24253 | valid series, coherent answer, traceable to a tool output |
| 49 | t022-d201 | 3 | peak_hour | escalated | ok | 0 | None | None | None | 6/11 | 22814 | escalated: declared cannot_forecast |
| 50 | t022-d201 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 7/13 | 46842 | escalated: declared cannot_forecast |
| 51 | t022-d201 | 48 | none | solved | ok | 288 | 205.24 | None | gru_forecast | 4/7 | 25403 | valid series, coherent answer, traceable to a tool output |
| 52 | t022-d207 | 3 | peak_hour | solved | ok | 18 | 79.53 | True | gru_forecast | 4/6 | 14882 | valid series, coherent answer, traceable to a tool output |
| 53 | t022-d207 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 6/10 | 29468 | escalated: gate rejected coherent, declared cannot_forecast |
| 54 | t022-d207 | 48 | none | solved | ok | 288 | 277.42 | None | gru_forecast | 5/9 | 28465 | valid series, coherent answer, traceable to a tool output |
| 55 | t022-d212 | 3 | peak_hour | escalated | ok | 0 | None | None | None | 6/10 | 21484 | escalated: declared cannot_forecast |
| 56 | t022-d212 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 7/10 | 36604 | escalated: gate rejected coherent, declared cannot_forecast |
| 57 | t022-d212 | 48 | none | solved | ok | 288 | 546.21 | None | gru_forecast | 4/6 | 24289 | valid series, coherent answer, traceable to a tool output |
| 58 | t022-d229 | 3 | peak_hour | escalated | ok | 0 | None | None | None | 8/11 | 76027 | escalated: gate rejected coherent, declared cannot_forecast |
| 59 | t022-d229 | 6 | energy_kwh | escalated | ok | 0 | None | None | None | 6/11 | 24218 | escalated: declared cannot_forecast |
| 60 | t022-d229 | 48 | none | escalated | ok | 0 | None | None | None | 8/10 | 80319 | escalated: gate rejected schema, range, traceable, consistent, declared cannot_forecast |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace), `.png` (the series against the target).

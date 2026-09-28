# rule_based on SDWPF with no-llm

Generated 2026-09-28 12:38 by evaluation/postprocess.py from `raw/rows.jsonl`. Requests: 60. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the frozen target days, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-28 |
| model | none:rule_based |
| method | rule_based |
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
| system_prompt_hash | None |
| git_commit | 92706f5e-dirty |
| gru_weights_hash | sha256:9a7b1330e56d249a |
| description | Regular expressions read the turbine, the history window and the horizon from the request; the conventional forecaster (the GRU tool) writes the series; the answer to the question is computed from it. No language model. The conventional-automation row. |
| prompt files | (none) |

## Where every request ended

The three outcomes are exclusive and sum to the request count. Escalation takes precedence: a request the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 60 | 100.0% |
| Escalated to a person | 0 | 0.0% |
| Wrong, unflagged | 0 | 0.0% |
| **Total** | **60** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Formulation exact | 60/60 (100.0%) |
| Task utility | Formulation error types | {} |
| Task utility | MAE / RMSE / overall, kW, over valid series (n=60) | 272.48 / 330.6 / 301.54 |
| Task utility | NBIAS / NMAE / NRMSE, % of installed capacity (ANEMOS protocol), over valid series (n=60) | 8.09 / 18.17 / 22.04 |
| Task utility | Improvement over the protocol's reference model, % (its NMAE 19.16 %), over valid series (n=60) | 3.77 |
| Task utility | Improvement over persistence, % (its NMAE 32.96 %), over valid series (n=60) | 46.57 |
| Task utility | MAE / RMSE, kW, over solved requests | 272.48 / 330.6 |
| Task utility | Answer coherent with the series | 40/40 |
| Solver-grounded correctness | Valid series (schema and range) | 60/60 (100.0%) |
| Solver-grounded correctness | Traceable series | 60/60 (100.0%) |
| Solver-grounded correctness | Wrong, unflagged | 0/60 (0.0%) |
| Cost and time | Escalated | 0/60 (0.0%) |
| Cost and time | LLM calls / tool calls, mean | 0.0 / 2.0 |
| Cost and time | Prompt / completion tokens, mean | 0.0 / 0.0 |
| Cost and time | Cost, total | $0.0000 |
| Cost and time | Wall time, mean | 0.03 s |

## By horizon

Every error is the mean over the requests of that horizon whose series was valid; a method that returns no valid series at a horizon has nothing to average, which is itself the finding. NMAE and NRMSE are normalised by the 1500 kW installed capacity, and Imp. is the improvement score of the ANEMOS protocol (Madsen et al. 2005) over its reference model, `a_k P(t) + (1-a_k) Pbar`, fitted on the training period; the improvement over plain persistence is beside it because persistence is the reference most readers know, and the protocol warns it flatters a model at long horizons.

| horizon | n | solved | scored | MAE kW | RMSE kW | NMAE % | NRMSE % | reference NMAE % | Imp. % | persistence NMAE % | Imp. vs pers. % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 h | 20 | 20 | 20 | 175.88 | 216.66 | 11.73 | 14.44 | 12.64 | 4.71 | 28.41 | 57.67 |
| 6 h | 20 | 20 | 20 | 247.06 | 284.41 | 16.47 | 18.96 | 17.16 | 2.51 | 31.39 | 49.43 |
| 48 h | 20 | 20 | 20 | 394.51 | 490.71 | 26.3 | 32.71 | 27.68 | 4.09 | 39.09 | 32.59 |

## Wrong and unflagged (0)

none

## Escalated (0)

none

## Every request

| nn | instance | h | question | outcome | formulation | values | MAE | answer ok | source | LLM/tool calls | tokens | why |
|---|---|---:|---|---|---|---:|---:|---|---|---|---:|---|
| 01 | t008-d201 | 3 | peak_hour | solved | ok | 18 | 166.09 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 02 | t008-d201 | 6 | energy_kwh | solved | ok | 36 | 133.84 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 03 | t008-d201 | 48 | none | solved | ok | 288 | 238.56 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 04 | t008-d207 | 3 | peak_hour | solved | ok | 18 | 238.24 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 05 | t008-d207 | 6 | energy_kwh | solved | ok | 36 | 360.13 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 06 | t008-d207 | 48 | none | solved | ok | 288 | 338.65 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 07 | t008-d212 | 3 | peak_hour | solved | ok | 18 | 272.96 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 08 | t008-d212 | 6 | energy_kwh | solved | ok | 36 | 518.58 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 09 | t008-d212 | 48 | none | solved | ok | 288 | 581.12 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 10 | t008-d229 | 3 | peak_hour | solved | ok | 18 | 153.17 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 11 | t008-d229 | 6 | energy_kwh | solved | ok | 36 | 119.9 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 12 | t008-d229 | 48 | none | solved | ok | 288 | 528.36 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 13 | t009-d201 | 3 | peak_hour | solved | ok | 18 | 168.59 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 14 | t009-d201 | 6 | energy_kwh | solved | ok | 36 | 116.2 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 15 | t009-d201 | 48 | none | solved | ok | 288 | 244.58 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 16 | t009-d207 | 3 | peak_hour | solved | ok | 18 | 218.01 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 17 | t009-d207 | 6 | energy_kwh | solved | ok | 36 | 367.09 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 18 | t009-d207 | 48 | none | solved | ok | 288 | 334.86 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 19 | t009-d212 | 3 | peak_hour | solved | ok | 18 | 289.87 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 20 | t009-d212 | 6 | energy_kwh | solved | ok | 36 | 492.29 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 21 | t009-d212 | 48 | none | solved | ok | 288 | 587.53 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 22 | t009-d229 | 3 | peak_hour | solved | ok | 18 | 135.17 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 23 | t009-d229 | 6 | energy_kwh | solved | ok | 36 | 93.02 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 24 | t009-d229 | 48 | none | solved | ok | 288 | 524.95 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 25 | t013-d201 | 3 | peak_hour | solved | ok | 18 | 209.35 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 26 | t013-d201 | 6 | energy_kwh | solved | ok | 36 | 173.96 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 27 | t013-d201 | 48 | none | solved | ok | 288 | 220.96 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 28 | t013-d207 | 3 | peak_hour | solved | ok | 18 | 130.63 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 29 | t013-d207 | 6 | energy_kwh | solved | ok | 36 | 212.96 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 30 | t013-d207 | 48 | none | solved | ok | 288 | 297.98 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 31 | t013-d212 | 3 | peak_hour | solved | ok | 18 | 177.14 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 32 | t013-d212 | 6 | energy_kwh | solved | ok | 36 | 425.49 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 33 | t013-d212 | 48 | none | solved | ok | 288 | 538.7 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 34 | t013-d229 | 3 | peak_hour | solved | ok | 18 | 119.59 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 35 | t013-d229 | 6 | energy_kwh | solved | ok | 36 | 112.44 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 36 | t013-d229 | 48 | none | solved | ok | 288 | 519.83 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 37 | t017-d201 | 3 | peak_hour | solved | ok | 18 | 128.81 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 38 | t017-d201 | 6 | energy_kwh | solved | ok | 36 | 139.45 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 39 | t017-d201 | 48 | none | solved | ok | 288 | 183.87 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 40 | t017-d207 | 3 | peak_hour | solved | ok | 18 | 101.8 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 41 | t017-d207 | 6 | energy_kwh | solved | ok | 36 | 136.23 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 42 | t017-d207 | 48 | none | solved | ok | 288 | 246.47 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 43 | t017-d212 | 3 | peak_hour | solved | ok | 18 | 219.4 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 44 | t017-d212 | 6 | energy_kwh | solved | ok | 36 | 290.25 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 45 | t017-d212 | 48 | none | solved | ok | 288 | 468.37 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 46 | t017-d229 | 3 | peak_hour | solved | ok | 18 | 94.44 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 47 | t017-d229 | 6 | energy_kwh | solved | ok | 36 | 107.94 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 48 | t017-d229 | 48 | none | solved | ok | 288 | 453.21 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 49 | t022-d201 | 3 | peak_hour | solved | ok | 18 | 96.85 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 50 | t022-d201 | 6 | energy_kwh | solved | ok | 36 | 136.37 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 51 | t022-d201 | 48 | none | solved | ok | 288 | 205.24 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 52 | t022-d207 | 3 | peak_hour | solved | ok | 18 | 79.53 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 53 | t022-d207 | 6 | energy_kwh | solved | ok | 36 | 209.9 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 54 | t022-d207 | 48 | none | solved | ok | 288 | 277.42 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 55 | t022-d212 | 3 | peak_hour | solved | ok | 18 | 294.37 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 56 | t022-d212 | 6 | energy_kwh | solved | ok | 36 | 553.68 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 57 | t022-d212 | 48 | none | solved | ok | 288 | 546.21 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 58 | t022-d229 | 3 | peak_hour | solved | ok | 18 | 223.63 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 59 | t022-d229 | 6 | energy_kwh | solved | ok | 36 | 241.45 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 60 | t022-d229 | 48 | none | solved | ok | 288 | 553.31 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace), `.png` (the series against the target).

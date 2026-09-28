# rule_based on SDWPF with no-llm

Generated 2026-09-28 00:02 by evaluation/postprocess.py from `raw/rows.jsonl`. Requests: 60. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the frozen target days, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-27 |
| model | none:rule_based |
| method | rule_based |
| condition | normal |
| n | 60 |
| instances | ['t008-d201', 't008-d207', 't008-d212', 't008-d229', 't009-d201', 't009-d207', 't009-d212', 't009-d229', 't013-d201', 't013-d207', 't013-d212', 't013-d229', 't017-d201', 't017-d207', 't017-d212', 't017-d229', 't022-d201', 't022-d207', 't022-d212', 't022-d229'] |
| horizons | [3, 6, 48] |
| seed | 0 |
| requests_digest | 393ed333a99b |
| temperature | 0.0 |
| max_llm_calls | 8 |
| max_tool_calls | 12 |
| timeout_s | 600.0 |
| system_prompt_hash | None |
| git_commit | 5ff343de-dirty |
| gru_weights_hash | sha256:c9c4fdf9709130aa |
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
| Task utility | MAE / RMSE / overall, kW, over valid series (n=60) | 280.7 / 333.08 / 306.89 |
| Task utility | MAE as a share of the 1500 kW rating | 18.71 % |
| Task utility | Skill against persistence (1 - MAE/MAE_persistence; 0 = no better, negative = worse) | 0.45 (persistence MAE 494.45 kW) |
| Task utility | MAE / RMSE, kW, over solved requests | 280.7 / 333.08 |
| Task utility | Answer coherent with the series | 40/40 |
| Solver-grounded correctness | Valid series (schema and range) | 60/60 (100.0%) |
| Solver-grounded correctness | Traceable series | 60/60 (100.0%) |
| Solver-grounded correctness | Wrong, unflagged | 0/60 (0.0%) |
| Cost and time | Escalated | 0/60 (0.0%) |
| Cost and time | LLM calls / tool calls, mean | 0.0 / 2.0 |
| Cost and time | Prompt / completion tokens, mean | 0.0 / 0.0 |
| Cost and time | Cost, total | $0.0000 |
| Cost and time | Wall time, mean | 0.05 s |

## By horizon

Every error is the mean over the requests of that horizon whose series was valid; a method that returns no valid series at a horizon has nothing to average, which is itself the finding. Skill is against persistence on the same points.

| horizon | n | solved | valid series scored | MAE kW | RMSE kW | overall kW | nMAE % | persistence MAE kW | skill |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 h | 20 | 20 | 20 | 196.01 | 229.4 | 212.71 | 13.07 | 426.12 | 0.53 |
| 6 h | 20 | 20 | 20 | 250.21 | 283.85 | 267.03 | 16.68 | 470.86 | 0.49 |
| 48 h | 20 | 20 | 20 | 395.89 | 486.0 | 440.94 | 26.39 | 586.38 | 0.32 |

## Wrong and unflagged (0)

none

## Escalated (0)

none

## Every request

| nn | instance | h | question | outcome | formulation | values | MAE | answer ok | source | LLM/tool calls | tokens | why |
|---|---|---:|---|---|---|---:|---:|---|---|---|---:|---|
| 01 | t008-d201 | 3 | peak_hour | solved | ok | 18 | 223.22 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 02 | t008-d201 | 6 | energy_kwh | solved | ok | 36 | 200.78 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 03 | t008-d201 | 48 | none | solved | ok | 288 | 243.87 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 04 | t008-d207 | 3 | peak_hour | solved | ok | 18 | 198.5 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 05 | t008-d207 | 6 | energy_kwh | solved | ok | 36 | 242.38 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 06 | t008-d207 | 48 | none | solved | ok | 288 | 332.79 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 07 | t008-d212 | 3 | peak_hour | solved | ok | 18 | 291.37 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 08 | t008-d212 | 6 | energy_kwh | solved | ok | 36 | 477.18 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 09 | t008-d212 | 48 | none | solved | ok | 288 | 573.78 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 10 | t008-d229 | 3 | peak_hour | solved | ok | 18 | 249.88 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 11 | t008-d229 | 6 | energy_kwh | solved | ok | 36 | 204.15 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 12 | t008-d229 | 48 | none | solved | ok | 288 | 553.32 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 13 | t009-d201 | 3 | peak_hour | solved | ok | 18 | 207.08 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 14 | t009-d201 | 6 | energy_kwh | solved | ok | 36 | 199.96 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 15 | t009-d201 | 48 | none | solved | ok | 288 | 249.91 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 16 | t009-d207 | 3 | peak_hour | solved | ok | 18 | 180.15 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 17 | t009-d207 | 6 | energy_kwh | solved | ok | 36 | 224.76 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 18 | t009-d207 | 48 | none | solved | ok | 288 | 326.12 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 19 | t009-d212 | 3 | peak_hour | solved | ok | 18 | 310.23 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 20 | t009-d212 | 6 | energy_kwh | solved | ok | 36 | 489.6 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 21 | t009-d212 | 48 | none | solved | ok | 288 | 576.83 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 22 | t009-d229 | 3 | peak_hour | solved | ok | 18 | 212.9 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 23 | t009-d229 | 6 | energy_kwh | solved | ok | 36 | 182.22 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 24 | t009-d229 | 48 | none | solved | ok | 288 | 545.53 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 25 | t013-d201 | 3 | peak_hour | solved | ok | 18 | 264.16 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 26 | t013-d201 | 6 | energy_kwh | solved | ok | 36 | 236.64 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 27 | t013-d201 | 48 | none | solved | ok | 288 | 228.22 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 28 | t013-d207 | 3 | peak_hour | solved | ok | 18 | 106.8 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 29 | t013-d207 | 6 | energy_kwh | solved | ok | 36 | 146.86 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 30 | t013-d207 | 48 | none | solved | ok | 288 | 293.99 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 31 | t013-d212 | 3 | peak_hour | solved | ok | 18 | 183.18 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 32 | t013-d212 | 6 | energy_kwh | solved | ok | 36 | 385.04 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 33 | t013-d212 | 48 | none | solved | ok | 288 | 532.56 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 34 | t013-d229 | 3 | peak_hour | solved | ok | 18 | 176.33 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 35 | t013-d229 | 6 | energy_kwh | solved | ok | 36 | 163.93 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 36 | t013-d229 | 48 | none | solved | ok | 288 | 526.91 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 37 | t017-d201 | 3 | peak_hour | solved | ok | 18 | 164.66 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 38 | t017-d201 | 6 | energy_kwh | solved | ok | 36 | 178.25 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 39 | t017-d201 | 48 | none | solved | ok | 288 | 193.36 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 40 | t017-d207 | 3 | peak_hour | solved | ok | 18 | 91.28 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 41 | t017-d207 | 6 | energy_kwh | solved | ok | 36 | 126.71 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 42 | t017-d207 | 48 | none | solved | ok | 288 | 240.23 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 43 | t017-d212 | 3 | peak_hour | solved | ok | 18 | 169.15 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 44 | t017-d212 | 6 | energy_kwh | solved | ok | 36 | 325.46 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 45 | t017-d212 | 48 | none | solved | ok | 288 | 476.04 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 46 | t017-d229 | 3 | peak_hour | solved | ok | 18 | 111.54 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 47 | t017-d229 | 6 | energy_kwh | solved | ok | 36 | 127.06 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 48 | t017-d229 | 48 | none | solved | ok | 288 | 454.09 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 49 | t022-d201 | 3 | peak_hour | solved | ok | 18 | 132.98 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 50 | t022-d201 | 6 | energy_kwh | solved | ok | 36 | 172.14 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 51 | t022-d201 | 48 | none | solved | ok | 288 | 210.4 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 52 | t022-d207 | 3 | peak_hour | solved | ok | 18 | 68.6 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 53 | t022-d207 | 6 | energy_kwh | solved | ok | 36 | 126.01 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 54 | t022-d207 | 48 | none | solved | ok | 288 | 273.14 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 55 | t022-d212 | 3 | peak_hour | solved | ok | 18 | 310.34 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 56 | t022-d212 | 6 | energy_kwh | solved | ok | 36 | 511.63 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 57 | t022-d212 | 48 | none | solved | ok | 288 | 529.08 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 58 | t022-d229 | 3 | peak_hour | solved | ok | 18 | 267.92 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 59 | t022-d229 | 6 | energy_kwh | solved | ok | 36 | 283.34 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 60 | t022-d229 | 48 | none | solved | ok | 288 | 557.55 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace), `.png` (the series against the target).

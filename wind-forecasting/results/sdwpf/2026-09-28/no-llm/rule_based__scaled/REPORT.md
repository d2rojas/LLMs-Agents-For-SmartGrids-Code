# rule_based on SDWPF with no-llm

Generated 2026-09-28 09:58 by evaluation/postprocess.py from `raw/rows.jsonl`. Requests: 60. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the frozen target days, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-28 |
| model | none:rule_based |
| method | rule_based |
| condition | scaled |
| n | 60 |
| instances | ['t008-d201', 't008-d207', 't008-d212', 't008-d229', 't009-d201', 't009-d207', 't009-d212', 't009-d229', 't013-d201', 't013-d207', 't013-d212', 't013-d229', 't017-d201', 't017-d207', 't017-d212', 't017-d229', 't022-d201', 't022-d207', 't022-d212', 't022-d229'] |
| horizons | [3, 6, 48] |
| seed | 0 |
| requests_digest | 82d2bdac7686 |
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
| Task utility | MAE / RMSE / overall, kW, over valid series (n=60) | 272.83 / 331.25 / 302.04 |
| Task utility | NBIAS / NMAE / NRMSE, % of installed capacity (ANEMOS protocol) | 8.09 / 18.17 / 22.04 |
| Task utility | Improvement over the protocol's reference model, % (its NMAE 19.16 %) | 3.77 |
| Task utility | Improvement over persistence, % (its NMAE 32.96 %) | 46.57 |
| Task utility | MAE / RMSE, kW, over solved requests | 272.83 / 331.25 |
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

Every error is the mean over the requests of that horizon whose series was valid; a method that returns no valid series at a horizon has nothing to average, which is itself the finding. NMAE and NRMSE are normalised by the 1500 kW installed capacity, and Imp. is the improvement score of the ANEMOS protocol (Madsen et al. 2005) over its reference model, `a_k P(t) + (1-a_k) Pbar`, fitted on the training period; the improvement over plain persistence is beside it because persistence is the reference most readers know, and the protocol warns it flatters a model at long horizons.

| horizon | n | solved | scored | MAE kW | RMSE kW | NMAE % | NRMSE % | reference NMAE % | Imp. % | persistence NMAE % | Imp. vs pers. % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 h | 20 | 20 | 20 | 175.03 | 216.07 | 11.73 | 14.44 | 12.64 | 4.71 | 28.41 | 57.67 |
| 6 h | 20 | 20 | 20 | 246.35 | 283.87 | 16.47 | 18.96 | 17.16 | 2.5 | 31.39 | 49.43 |
| 48 h | 20 | 20 | 20 | 397.11 | 493.82 | 26.3 | 32.71 | 27.68 | 4.09 | 39.09 | 32.59 |

## Wrong and unflagged (0)

none

## Escalated (0)

none

## Every request

| nn | instance | h | question | outcome | formulation | values | MAE | answer ok | source | LLM/tool calls | tokens | why |
|---|---|---:|---|---|---|---:|---:|---|---|---|---:|---|
| 01 | t008-d201 | 3 | peak_hour | solved | ok | 18 | 151.95 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 02 | t008-d201 | 6 | energy_kwh | solved | ok | 36 | 122.44 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 03 | t008-d201 | 48 | none | solved | ok | 288 | 218.21 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 04 | t008-d207 | 3 | peak_hour | solved | ok | 18 | 233.35 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 05 | t008-d207 | 6 | energy_kwh | solved | ok | 36 | 352.73 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 06 | t008-d207 | 48 | none | solved | ok | 288 | 331.71 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 07 | t008-d212 | 3 | peak_hour | solved | ok | 18 | 288.73 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 08 | t008-d212 | 6 | energy_kwh | solved | ok | 36 | 548.53 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 09 | t008-d212 | 48 | none | solved | ok | 288 | 614.71 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 10 | t008-d229 | 3 | peak_hour | solved | ok | 18 | 171.77 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 11 | t008-d229 | 6 | energy_kwh | solved | ok | 36 | 134.47 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 12 | t008-d229 | 48 | none | solved | ok | 288 | 592.55 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 13 | t009-d201 | 3 | peak_hour | solved | ok | 18 | 155.1 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 14 | t009-d201 | 6 | energy_kwh | solved | ok | 36 | 106.9 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 15 | t009-d201 | 48 | none | solved | ok | 288 | 225.04 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 16 | t009-d207 | 3 | peak_hour | solved | ok | 18 | 199.52 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 17 | t009-d207 | 6 | energy_kwh | solved | ok | 36 | 335.95 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 18 | t009-d207 | 48 | none | solved | ok | 288 | 306.46 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 19 | t009-d212 | 3 | peak_hour | solved | ok | 18 | 297.29 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 20 | t009-d212 | 6 | energy_kwh | solved | ok | 36 | 504.94 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 21 | t009-d212 | 48 | none | solved | ok | 288 | 602.63 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 22 | t009-d229 | 3 | peak_hour | solved | ok | 18 | 146.46 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 23 | t009-d229 | 6 | energy_kwh | solved | ok | 36 | 100.79 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 24 | t009-d229 | 48 | none | solved | ok | 288 | 568.89 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 25 | t013-d201 | 3 | peak_hour | solved | ok | 18 | 202.39 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 26 | t013-d201 | 6 | energy_kwh | solved | ok | 36 | 168.2 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 27 | t013-d201 | 48 | none | solved | ok | 288 | 213.62 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 28 | t013-d207 | 3 | peak_hour | solved | ok | 18 | 107.23 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 29 | t013-d207 | 6 | energy_kwh | solved | ok | 36 | 174.84 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 30 | t013-d207 | 48 | none | solved | ok | 288 | 244.64 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 31 | t013-d212 | 3 | peak_hour | solved | ok | 18 | 178.28 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 32 | t013-d212 | 6 | energy_kwh | solved | ok | 36 | 428.25 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 33 | t013-d212 | 48 | none | solved | ok | 288 | 542.19 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 34 | t013-d229 | 3 | peak_hour | solved | ok | 18 | 113.63 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 35 | t013-d229 | 6 | energy_kwh | solved | ok | 36 | 106.85 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 36 | t013-d229 | 48 | none | solved | ok | 288 | 493.99 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 37 | t017-d201 | 3 | peak_hour | solved | ok | 18 | 137.03 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 38 | t017-d201 | 6 | energy_kwh | solved | ok | 36 | 148.33 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 39 | t017-d201 | 48 | none | solved | ok | 288 | 195.6 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 40 | t017-d207 | 3 | peak_hour | solved | ok | 18 | 94.53 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 41 | t017-d207 | 6 | energy_kwh | solved | ok | 36 | 126.51 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 42 | t017-d207 | 48 | none | solved | ok | 288 | 228.87 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 43 | t017-d212 | 3 | peak_hour | solved | ok | 18 | 242.91 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 44 | t017-d212 | 6 | energy_kwh | solved | ok | 36 | 321.38 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 45 | t017-d212 | 48 | none | solved | ok | 288 | 518.57 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 46 | t017-d229 | 3 | peak_hour | solved | ok | 18 | 100.22 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 47 | t017-d229 | 6 | energy_kwh | solved | ok | 36 | 114.55 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 48 | t017-d229 | 48 | none | solved | ok | 288 | 480.99 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 49 | t022-d201 | 3 | peak_hour | solved | ok | 18 | 86.72 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 50 | t022-d201 | 6 | energy_kwh | solved | ok | 36 | 122.1 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 51 | t022-d201 | 48 | none | solved | ok | 288 | 183.77 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 52 | t022-d207 | 3 | peak_hour | solved | ok | 18 | 88.16 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 53 | t022-d207 | 6 | energy_kwh | solved | ok | 36 | 232.71 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 54 | t022-d207 | 48 | none | solved | ok | 288 | 307.55 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 55 | t022-d212 | 3 | peak_hour | solved | ok | 18 | 288.11 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 56 | t022-d212 | 6 | energy_kwh | solved | ok | 36 | 541.94 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 57 | t022-d212 | 48 | none | solved | ok | 288 | 534.63 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 58 | t022-d229 | 3 | peak_hour | solved | ok | 18 | 217.27 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 59 | t022-d229 | 6 | energy_kwh | solved | ok | 36 | 234.58 | True | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |
| 60 | t022-d229 | 48 | none | solved | ok | 288 | 537.59 | None | gru_forecast | 0/2 | 0 | valid series, coherent answer, traceable to a tool output |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace), `.png` (the series against the target).

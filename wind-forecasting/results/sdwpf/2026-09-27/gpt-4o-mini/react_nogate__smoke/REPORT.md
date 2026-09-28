# react_nogate on SDWPF with gpt-4o-mini

Generated 2026-09-28 00:18 by evaluation/postprocess.py from `raw/rows.jsonl`. Requests: 3. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the frozen target days, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-27 |
| model | openrouter:openai/gpt-4o-mini |
| method | react_nogate |
| condition | normal |
| n | 3 |
| instances | ['t008-d201', 't008-d207', 't008-d212'] |
| horizons | [48] |
| seed | 0 |
| requests_digest | 48dbfbdc1495 |
| temperature | 0.0 |
| max_llm_calls | 8 |
| max_tool_calls | 12 |
| timeout_s | 600.0 |
| system_prompt_hash | e1f6a815f011 |
| git_commit | 5ff343de-dirty |
| gru_weights_hash | sha256:c9c4fdf9709130aa |
| description | Tool call, observation, repeat, inside the round budget. The model sees every tool output and decides the next call; nothing checks the answer before it is surfaced. |
| prompt files | _shared/common_rules.txt, _shared/output_contract.txt, _shared/agent_system_prompt.txt |

## Where every request ended

The three outcomes are exclusive and sum to the request count. Escalation takes precedence: a request the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 1 | 33.3% |
| Escalated to a person | 1 | 33.3% |
| Wrong, unflagged | 1 | 33.3% |
| **Total** | **3** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Formulation exact | 3/3 (100.0%) |
| Task utility | Formulation error types | {} |
| Task utility | MAE / RMSE / overall, kW, over valid series (n=2) | 453.28 / 549.08 / 501.18 |
| Task utility | NBIAS / NMAE / NRMSE, % of installed capacity (ANEMOS protocol) | 15.24 / 30.22 / 36.6 |
| Task utility | Improvement over the protocol's reference model, % (its NMAE 31.38 %) | 3.0 |
| Task utility | Improvement over persistence, % (its NMAE 43.74 %) | 31.9 |
| Task utility | MAE / RMSE, kW, over solved requests | 573.78 / 682.68 |
| Task utility | Answer coherent with the series | 0/1 |
| Solver-grounded correctness | Valid series (schema and range) | 2/3 (66.7%) |
| Solver-grounded correctness | Traceable series | 2/2 (100.0%) |
| Solver-grounded correctness | Wrong, unflagged | 1/3 (33.3%) |
| Cost and time | Escalated | 1/3 (33.3%) |
| Cost and time | LLM calls / tool calls, mean | 5.33 / 10.67 |
| Cost and time | Prompt / completion tokens, mean | 38846.33 / 1403.67 |
| Cost and time | Cost, total | $0.0200 |
| Cost and time | Wall time, mean | 18.13 s |

## By horizon

Every error is the mean over the requests of that horizon whose series was valid; a method that returns no valid series at a horizon has nothing to average, which is itself the finding. NMAE and NRMSE are normalised by the 1500 kW installed capacity, and Imp. is the improvement score of the ANEMOS protocol (Madsen et al. 2005) over its reference model, `a_k P(t) + (1-a_k) Pbar`, fitted on the training period; the improvement over plain persistence is beside it because persistence is the reference most readers know, and the protocol warns it flatters a model at long horizons.

| horizon | n | solved | scored | MAE kW | RMSE kW | NMAE % | NRMSE % | reference NMAE % | Imp. % | persistence NMAE % | Imp. vs pers. % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 48 h | 3 | 1 | 2 | 453.28 | 549.08 | 30.22 | 36.6 | 31.38 | 3.0 | 43.74 | 31.9 |

## Wrong and unflagged (1)

- `02_wind-t008-d207-h48-energy_kwh-s0`: answer 554.5 contradicts the series (implies 26300.4)

## Escalated (1)

- `01_wind-t008-d201-h48-peak_hour-s0`: escalated: budget exhausted, declared cannot_forecast

## Every request

| nn | instance | h | question | outcome | formulation | values | MAE | answer ok | source | LLM/tool calls | tokens | why |
|---|---|---:|---|---|---|---:|---:|---|---|---|---:|---|
| 01 | t008-d201 | 48 | peak_hour | escalated | ok | 0 | None | None | None | 8/20 | 72806 | escalated: budget exhausted, declared cannot_forecast |
| 02 | t008-d207 | 48 | energy_kwh | wrong_unflagged | ok | 288 | 332.79 | False | gru_forecast | 4/7 | 24120 | answer 554.5 contradicts the series (implies 26300.4) |
| 03 | t008-d212 | 48 | none | solved | ok | 288 | 573.78 | None | gru_forecast | 4/5 | 23824 | valid series, coherent answer, traceable to a tool output |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace), `.png` (the series against the target).

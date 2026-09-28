# llm_only_structured on SDWPF with gpt-4o-mini

Generated 2026-09-28 00:18 by evaluation/postprocess.py from `raw/rows.jsonl`. Requests: 3. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the frozen target days, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-27 |
| model | openrouter:openai/gpt-4o-mini |
| method | llm_only_structured |
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
| system_prompt_hash | dd8ee2096b49 |
| git_commit | 5ff343de-dirty |
| gru_weights_hash | sha256:c9c4fdf9709130aa |
| description | One call, no tools. The model reads the 14-day history as CSV and the physical rules, and writes the forecast values itself with the answer contract. The LLM as the predictor, which is the setting the paper's Section 6.1 tested. |
| prompt files | _shared/common_rules.txt, _shared/output_contract.txt, _shared/llm_only_system_prompt.txt |

## Where every request ended

The three outcomes are exclusive and sum to the request count. Escalation takes precedence: a request the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 0 | 0.0% |
| Escalated to a person | 0 | 0.0% |
| Wrong, unflagged | 3 | 100.0% |
| **Total** | **3** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Formulation exact | 0/3 (0.0%) |
| Task utility | Formulation error types | {'no_formulation': 3} |
| Task utility | MAE / RMSE / overall, kW, over valid series (n=0) | None / None / None |
| Task utility | NBIAS / NMAE / NRMSE, % of installed capacity (ANEMOS protocol) | None / None / None |
| Task utility | Improvement over the protocol's reference model, % (its NMAE None %) | None |
| Task utility | Improvement over persistence, % (its NMAE None %) | None |
| Task utility | MAE / RMSE, kW, over solved requests | None / None |
| Task utility | Answer coherent with the series | 0/0 |
| Solver-grounded correctness | Valid series (schema and range) | 0/3 (0.0%) |
| Solver-grounded correctness | Traceable series | 0/0 (None%) |
| Solver-grounded correctness | Wrong, unflagged | 3/3 (100.0%) |
| Cost and time | Escalated | 0/3 (0.0%) |
| Cost and time | LLM calls / tool calls, mean | 1.0 / 0.0 |
| Cost and time | Prompt / completion tokens, mean | 45879.33 / 6000.0 |
| Cost and time | Cost, total | $0.0314 |
| Cost and time | Wall time, mean | 96.56 s |

## By horizon

Every error is the mean over the requests of that horizon whose series was valid; a method that returns no valid series at a horizon has nothing to average, which is itself the finding. NMAE and NRMSE are normalised by the 1500 kW installed capacity, and Imp. is the improvement score of the ANEMOS protocol (Madsen et al. 2005) over its reference model, `a_k P(t) + (1-a_k) Pbar`, fitted on the training period; the improvement over plain persistence is beside it because persistence is the reference most readers know, and the protocol warns it flatters a model at long horizons.

| horizon | n | solved | scored | MAE kW | RMSE kW | NMAE % | NRMSE % | reference NMAE % | Imp. % | persistence NMAE % | Imp. vs pers. % |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 48 h | 3 | 0 | 0 | None | None | None | None | None | None | None | None |

## Wrong and unflagged (3)

- `01_wind-t008-d201-h48-peak_hour-s0`: no JSON answer: the output hit the token cap before the object was closed
- `02_wind-t008-d207-h48-energy_kwh-s0`: no JSON answer: the output hit the token cap before the object was closed
- `03_wind-t008-d212-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed

## Escalated (0)

none

## Every request

| nn | instance | h | question | outcome | formulation | values | MAE | answer ok | source | LLM/tool calls | tokens | why |
|---|---|---:|---|---|---|---:|---:|---|---|---|---:|---|
| 01 | t008-d201 | 48 | peak_hour | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 51806 | no JSON answer: the output hit the token cap before the object was closed |
| 02 | t008-d207 | 48 | energy_kwh | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 52008 | no JSON answer: the output hit the token cap before the object was closed |
| 03 | t008-d212 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 51824 | no JSON answer: the output hit the token cap before the object was closed |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace), `.png` (the series against the target).

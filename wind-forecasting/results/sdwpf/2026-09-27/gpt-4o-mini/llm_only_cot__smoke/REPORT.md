# llm_only_cot on SDWPF with gpt-4o-mini

Generated 2026-09-28 00:05 by evaluation/postprocess.py from `raw/rows.jsonl`. Requests: 3. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the frozen target days, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-27 |
| model | openrouter:openai/gpt-4o-mini |
| method | llm_only_cot |
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
| description | The structured prompt plus one reasoning section asking the model to reason step by step before the answer. Identical to the row above in every other respect. |
| prompt files | _shared/common_rules.txt, _shared/output_contract.txt, _shared/llm_only_system_prompt.txt, llm_only_cot/reasoning_section.txt |

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
| Task utility | Formulation exact | 1/3 (33.3%) |
| Task utility | Formulation error types | {'no_formulation': 2} |
| Task utility | MAE / RMSE / overall, kW, over valid series (n=0) | None / None / None |
| Task utility | MAE as a share of the 1500 kW rating | None % |
| Task utility | Skill against persistence (1 - MAE/MAE_persistence; 0 = no better, negative = worse) | None (persistence MAE None kW) |
| Task utility | MAE / RMSE, kW, over solved requests | None / None |
| Task utility | Answer coherent with the series | 0/1 |
| Solver-grounded correctness | Valid series (schema and range) | 0/3 (0.0%) |
| Solver-grounded correctness | Traceable series | 0/1 (0.0%) |
| Solver-grounded correctness | Wrong, unflagged | 3/3 (100.0%) |
| Cost and time | Escalated | 0/3 (0.0%) |
| Cost and time | LLM calls / tool calls, mean | 1.0 / 0.0 |
| Cost and time | Prompt / completion tokens, mean | 45992.33 / 5778.67 |
| Cost and time | Cost, total | $0.0311 |
| Cost and time | Wall time, mean | 74.4 s |

## By horizon

Every error is the mean over the requests of that horizon whose series was valid; a method that returns no valid series at a horizon has nothing to average, which is itself the finding. Skill is against persistence on the same points.

| horizon | n | solved | valid series scored | MAE kW | RMSE kW | overall kW | nMAE % | persistence MAE kW | skill |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 48 h | 3 | 0 | 0 | None | None | None | None | None | None |

## Wrong and unflagged (3)

- `01_wind-t008-d201-h48-peak_hour-s0`: no JSON answer: the output hit the token cap before the object was closed
- `02_wind-t008-d207-h48-energy_kwh-s0`: 168 values, the horizon needs 288
- `03_wind-t008-d212-h48-none-s0`: no JSON answer: the output hit the token cap before the object was closed

## Escalated (0)

none

## Every request

| nn | instance | h | question | outcome | formulation | values | MAE | answer ok | source | LLM/tool calls | tokens | why |
|---|---|---:|---|---|---|---:|---:|---|---|---|---:|---|
| 01 | t008-d201 | 48 | peak_hour | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 53919 | no JSON answer: the output hit the token cap before the object was closed |
| 02 | t008-d207 | 48 | energy_kwh | wrong_unflagged | ok | 168 | None | False | own_computation | 1/0 | 47457 | 168 values, the horizon needs 288 |
| 03 | t008-d212 | 48 | none | wrong_unflagged | no_formulation | 0 | None | None | None | 1/0 | 53937 | no JSON answer: the output hit the token cap before the object was closed |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace), `.png` (the series against the target).

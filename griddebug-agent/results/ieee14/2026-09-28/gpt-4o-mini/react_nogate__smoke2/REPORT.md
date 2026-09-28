# react_nogate on IEEE 14-bus with gpt-4o-mini

Generated 2026-09-28 00:53 by evaluation/postprocess.py from `raw/rows.jsonl`. Scenarios: 7. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the harness's own power flow, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-28 |
| model | openrouter:openai/gpt-4o-mini |
| method | react_nogate |
| case | case14 |
| condition | normal |
| n | 7 |
| temperature | 0.0 |
| max_llm_calls | 20 |
| max_tool_calls | 40 |
| timeout_s | 600.0 |
| system_prompt_hash | ca24f91b2fe9 |
| git_commit | 46cefeca-dirty |
| pandapower | 3.5.5 |
| description | Tool call, observation, repeat, inside the round budget. The model sees every tool output and decides the next call; nothing checks the answer before it is surfaced. The original GridDebugAgent loop without the gate. |
| prompt files | _shared/common_rules.txt, _shared/output_contract.txt, _shared/agent_system_prompt.txt |

## Where every scenario ended

The three outcomes are exclusive and sum to the scenario count. Escalation takes precedence: a scenario the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 0 | 0.0% |
| Escalated to a person | 7 | 100.0% |
| Wrong, unflagged | 0 | 0.0% |
| **Total** | **7** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Diagnosis exact | 1/7 (14.3%) |
| Task utility | Diagnosis error types | {'wrong_type': 5, 'wrong_components': 1} |
| Task utility | Repaired (secure final network) | 1/7 (14.3%) |
| Task utility | Improved | 6/7 (85.7%) |
| Task utility | New violations, before -> after (scenarios converged at both ends, n=6) | 36 -> 13 |
| Task utility | Load served, mean / worst | 73.03 % / 27.1 % of the base network's demand |
| Solver-grounded correctness | Feasible (final power flow converges) | 7/7 (100.0%) |
| Solver-grounded correctness | Traceable answers | 7/7 (100.0%) |
| Solver-grounded correctness | Wrong, unflagged | 0/7 (0.0%) |
| Cost and operation | Escalated | 7/7 (100.0%) |
| Cost and operation | LLM calls / tool calls, mean | 14.0 / 36.29 |
| Cost and operation | Prompt / completion tokens, mean | 82603.14 / 1435.71 |
| Cost and operation | Cost, total | $0.0928 |
| Cost and operation | Wall time, mean | 28.38 s |

## By scenario category (the generator's intent)

| category | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| contingency | 2 | 0 | 2 | 0 | 0 | 0 |
| nonconvergence | 2 | 0 | 2 | 0 | 1 | 0 |
| normal | 1 | 0 | 1 | 0 | 0 | 1 |
| voltage | 2 | 0 | 2 | 0 | 0 | 0 |

## By measured initial state

| initial_state | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| islanded_load | 1 | 0 | 1 | 0 | 0 | 0 |
| not_converged | 1 | 0 | 1 | 0 | 1 | 0 |
| secure | 1 | 0 | 1 | 0 | 0 | 1 |
| violations | 4 | 0 | 4 | 0 | 0 | 0 |

## Why it escalated

An escalation after a real improvement is not the same as a refusal, and one caused by the budget ending on an action is not the same as either. The column counts them together because a person still has to act; this table says which kind they were.

| kind | count |
|---|---:|
| budget exhausted | 6 |
| declared, after improving the network | 1 |

## Wrong and unflagged (0)

none

## Escalated (7)

- `01_case14-disconnected_subnetwork-v0` disconnected_subnetwork: escalated: declared not_repaired — budget exhausted
- `02_case14-extreme_load_scaling-v0` extreme_load_scaling: escalated: declared not_repaired — declared, after improving the network
- `03_case14-heavy_loading_undervoltage-v0` heavy_loading_undervoltage: escalated: declared not_repaired — budget exhausted
- `04_case14-heavy_loading_undervoltage-v1` heavy_loading_undervoltage: escalated: declared not_repaired — budget exhausted
- `05_case14-line_contingency_overload-v0` line_contingency_overload: escalated: declared not_repaired — budget exhausted
- `06_case14-line_contingency_overload-v1` line_contingency_overload: escalated: declared cannot_repair — budget exhausted
- `07_case14-normal_operation-v0` normal_operation: escalated: budget exhausted, declared cannot_repair — budget exhausted

## Every scenario

| nn | scenario | initial | outcome | diagnosis | final | actions | LLM/tool calls | tokens | why |
|---|---|---|---|---|---|---:|---|---|---|
| 01 | disconnected_subnetwork-v0 | islanded_load (7) | escalated | wrong_type | 0 new, islanded [9, 10, 12, 13] | 19 | 18/40 | 96537 | escalated: declared not_repaired |
| 02 | extreme_load_scaling-v0 | not_converged (None) | escalated | wrong_type | secure | 12 | 6/20 | 25246 | escalated: declared not_repaired |
| 03 | heavy_loading_undervoltage-v0 | violations (11) | escalated | wrong_type | 2 new | 28 | 9/40 | 68122 | escalated: declared not_repaired |
| 04 | heavy_loading_undervoltage-v1 | violations (11) | escalated | wrong_type | 6 new | 17 | 18/40 | 146362 | escalated: declared not_repaired |
| 05 | line_contingency_overload-v0 | violations (5) | escalated | wrong_type | 4 new | 26 | 10/40 | 70206 | escalated: declared not_repaired |
| 06 | line_contingency_overload-v1 | violations (2) | escalated | wrong_components | 0 new, islanded [9, 10, 11, 12, 13] | 20 | 17/40 | 87048 | escalated: declared cannot_repair |
| 07 | normal_operation-v0 | secure (0) | escalated | ok | 1 new | 9 | 20/34 | 94751 | escalated: budget exhausted, declared cannot_repair |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace).

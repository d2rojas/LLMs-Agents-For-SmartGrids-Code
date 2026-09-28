# react_nogate on IEEE 14-bus with gpt-4o-mini

Generated 2026-09-28 10:23 by evaluation/postprocess.py from `raw/rows.jsonl`. Scenarios: 7. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the harness's own power flow, the same way for every method.

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
| system_prompt_hash | d59378ee7244 |
| git_commit | c7673488-dirty |
| pandapower | 3.5.5 |
| description | Tool call, observation, repeat, inside the round budget. The model sees every tool output and decides the next call; nothing checks the answer before it is surfaced. The original GridDebugAgent loop without the gate. |
| prompt files | _shared/common_rules.txt, _shared/output_contract.txt, _shared/agent_system_prompt.txt |

## Where every scenario ended

The three outcomes are exclusive and sum to the scenario count. Escalation takes precedence: a scenario the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 3 | 42.9% |
| Escalated to a person | 3 | 42.9% |
| Wrong, unflagged | 1 | 14.3% |
| **Total** | **7** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Diagnosis exact | 1/7 (14.3%) |
| Task utility | Diagnosis error types | {'wrong_type': 5, 'wrong_components': 1} |
| Task utility | Repaired (secure final network) | 3/7 (42.9%) |
| Task utility | Improved | 6/7 (85.7%) |
| Task utility | New violations, before -> after (scenarios converged at both ends, n=6) | 36 -> 6 |
| Task utility | Load served, mean / worst | 64.11 % / 0.0 % of the base network's demand |
| Solver-grounded correctness | Feasible (final power flow converges) | 7/7 (100.0%) |
| Solver-grounded correctness | Traceable answers | 7/7 (100.0%) |
| Solver-grounded correctness | Wrong, unflagged | 1/7 (14.3%) |
| Cost and operation | Escalated | 3/7 (42.9%) |
| Cost and operation | LLM calls / tool calls, mean | 11.43 / 29.14 |
| Cost and operation | Prompt / completion tokens, mean | 58182.71 / 1314.14 |
| Cost and operation | Cost, total | $0.0666 |
| Cost and operation | Wall time, mean | 23.15 s |

## By scenario category (the generator's intent)

| category | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| contingency | 2 | 1 | 1 | 0 | 1 | 0 |
| nonconvergence | 2 | 1 | 1 | 0 | 1 | 0 |
| normal | 1 | 1 | 0 | 0 | 1 | 0 |
| voltage | 2 | 0 | 1 | 1 | 0 | 1 |

## By measured initial state

| initial_state | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| islanded_load | 1 | 0 | 1 | 0 | 0 | 0 |
| not_converged | 1 | 1 | 0 | 0 | 1 | 0 |
| secure | 1 | 1 | 0 | 0 | 1 | 0 |
| violations | 4 | 1 | 2 | 1 | 1 | 1 |

## Why it escalated

An escalation after a real improvement is not the same as a refusal, and one caused by the budget ending on an action is not the same as either. The column counts them together because a person still has to act; this table says which kind they were.

| kind | count |
|---|---:|
| declared, after improving the network | 2 |
| budget exhausted | 1 |

## Wrong and unflagged (1)

- `03_case14-heavy_loading_undervoltage-v0` heavy_loading_undervoltage: claimed repaired but the solver's final network 1 violation(s) beyond the base network

## Escalated (3)

- `01_case14-disconnected_subnetwork-v0` disconnected_subnetwork: escalated: declared cannot_repair — declared, after improving the network
- `04_case14-heavy_loading_undervoltage-v1` heavy_loading_undervoltage: escalated: declared not_repaired — declared, after improving the network
- `06_case14-line_contingency_overload-v1` line_contingency_overload: escalated: declared not_repaired — budget exhausted

## Every scenario

| nn | scenario | initial | outcome | diagnosis | final | actions | LLM/tool calls | tokens | why |
|---|---|---|---|---|---|---:|---|---|---|
| 01 | disconnected_subnetwork-v0 | islanded_load (7) | escalated | wrong_type | 0 new, islanded [1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13] | 15 | 18/39 | 108555 | escalated: declared cannot_repair |
| 02 | extreme_load_scaling-v0 | not_converged (None) | solved | wrong_type | secure | 12 | 6/20 | 26120 | secure, claimed, traceable, consistent |
| 03 | heavy_loading_undervoltage-v0 | violations (11) | wrong_unflagged | ok | 1 new | 26 | 11/38 | 58911 | claimed repaired but the solver's final network 1 violation(s) beyond the base network |
| 04 | heavy_loading_undervoltage-v1 | violations (11) | escalated | wrong_type | 3 new | 26 | 11/38 | 59644 | escalated: declared not_repaired |
| 05 | line_contingency_overload-v0 | violations (5) | solved | wrong_components | secure | 11 | 7/19 | 31320 | secure, claimed, traceable, consistent |
| 06 | line_contingency_overload-v1 | violations (2) | escalated | wrong_type | 2 new | 13 | 20/40 | 105983 | escalated: declared not_repaired |
| 07 | normal_operation-v0 | secure (0) | solved | wrong_type | secure | 4 | 7/10 | 25945 | secure, claimed, traceable, consistent |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace).

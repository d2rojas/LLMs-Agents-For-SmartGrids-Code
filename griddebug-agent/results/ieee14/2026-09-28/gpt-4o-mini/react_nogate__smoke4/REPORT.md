# react_nogate on IEEE 14-bus with gpt-4o-mini

Generated 2026-09-28 10:02 by evaluation/postprocess.py from `raw/rows.jsonl`. Scenarios: 7. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the harness's own power flow, the same way for every method.

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
| git_commit | 96531b84-dirty |
| pandapower | 3.5.5 |
| description | Tool call, observation, repeat, inside the round budget. The model sees every tool output and decides the next call; nothing checks the answer before it is surfaced. The original GridDebugAgent loop without the gate. |
| prompt files | _shared/common_rules.txt, _shared/output_contract.txt, _shared/agent_system_prompt.txt |

## Where every scenario ended

The three outcomes are exclusive and sum to the scenario count. Escalation takes precedence: a scenario the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 2 | 28.6% |
| Escalated to a person | 4 | 57.1% |
| Wrong, unflagged | 1 | 14.3% |
| **Total** | **7** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Diagnosis exact | 0/7 (0.0%) |
| Task utility | Diagnosis error types | {'wrong_type': 6, 'wrong_components': 1} |
| Task utility | Repaired (secure final network) | 2/7 (28.6%) |
| Task utility | Improved | 6/7 (85.7%) |
| Task utility | New violations, before -> after (scenarios converged at both ends, n=6) | 36 -> 8 |
| Task utility | Load served, mean / worst | 73.97 % / 0.0 % of the base network's demand |
| Solver-grounded correctness | Feasible (final power flow converges) | 7/7 (100.0%) |
| Solver-grounded correctness | Traceable answers | 7/7 (100.0%) |
| Solver-grounded correctness | Wrong, unflagged | 1/7 (14.3%) |
| Cost and operation | Escalated | 4/7 (57.1%) |
| Cost and operation | LLM calls / tool calls, mean | 14.0 / 33.43 |
| Cost and operation | Prompt / completion tokens, mean | 67845.86 / 1267.86 |
| Cost and operation | Cost, total | $0.0766 |
| Cost and operation | Wall time, mean | 24.6 s |

## By scenario category (the generator's intent)

| category | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| contingency | 2 | 0 | 1 | 1 | 0 | 0 |
| nonconvergence | 2 | 0 | 2 | 0 | 0 | 0 |
| normal | 1 | 1 | 0 | 0 | 1 | 0 |
| voltage | 2 | 1 | 1 | 0 | 1 | 0 |

## By measured initial state

| initial_state | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| islanded_load | 1 | 0 | 1 | 0 | 0 | 0 |
| not_converged | 1 | 0 | 1 | 0 | 0 | 0 |
| secure | 1 | 1 | 0 | 0 | 1 | 0 |
| violations | 4 | 1 | 2 | 1 | 1 | 0 |

## Why it escalated

An escalation after a real improvement is not the same as a refusal, and one caused by the budget ending on an action is not the same as either. The column counts them together because a person still has to act; this table says which kind they were.

| kind | count |
|---|---:|
| budget exhausted | 3 |
| declared, after improving the network | 1 |

## Wrong and unflagged (1)

- `06_case14-line_contingency_overload-v1` line_contingency_overload: claimed repaired but the solver's final network 3 violation(s) beyond the base network

## Escalated (4)

- `01_case14-disconnected_subnetwork-v0` disconnected_subnetwork: escalated: declared not_repaired — budget exhausted
- `02_case14-extreme_load_scaling-v0` extreme_load_scaling: escalated: declared not_repaired — budget exhausted
- `04_case14-heavy_loading_undervoltage-v1` heavy_loading_undervoltage: escalated: declared not_repaired — declared, after improving the network
- `05_case14-line_contingency_overload-v0` line_contingency_overload: escalated: budget exhausted, declared cannot_repair — budget exhausted

## Every scenario

| nn | scenario | initial | outcome | diagnosis | final | actions | LLM/tool calls | tokens | why |
|---|---|---|---|---|---|---:|---|---|---|
| 01 | disconnected_subnetwork-v0 | islanded_load (7) | escalated | wrong_type | 1 new, islanded [10, 13] | 16 | 17/40 | 87682 | escalated: declared not_repaired |
| 02 | extreme_load_scaling-v0 | not_converged (None) | escalated | wrong_type | 2 new | 22 | 10/40 | 51614 | escalated: declared not_repaired |
| 03 | heavy_loading_undervoltage-v0 | violations (11) | solved | wrong_type | secure | 8 | 8/14 | 31733 | secure, claimed, traceable, consistent |
| 04 | heavy_loading_undervoltage-v1 | violations (11) | escalated | wrong_type | 4 new | 26 | 11/38 | 60059 | escalated: declared not_repaired |
| 05 | line_contingency_overload-v0 | violations (5) | escalated | wrong_type | 0 new, islanded [9, 10, 11, 13] | 12 | 20/40 | 99914 | escalated: budget exhausted, declared cannot_repair |
| 06 | line_contingency_overload-v1 | violations (2) | wrong_unflagged | wrong_components | 3 new | 18 | 19/40 | 97603 | claimed repaired but the solver's final network 3 violation(s) beyond the base network |
| 07 | normal_operation-v0 | secure (0) | solved | wrong_type | secure | 6 | 13/22 | 55191 | secure, claimed, traceable, consistent |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace).

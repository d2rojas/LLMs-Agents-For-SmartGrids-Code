# react_nogate on IEEE 14-bus with gpt-4o-mini

Generated 2026-09-28 01:07 by evaluation/postprocess.py from `raw/rows.jsonl`. Scenarios: 7. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the harness's own power flow, the same way for every method.

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
| system_prompt_hash | 4b8459433e97 |
| git_commit | 46cefeca-dirty |
| pandapower | 3.5.5 |
| description | Tool call, observation, repeat, inside the round budget. The model sees every tool output and decides the next call; nothing checks the answer before it is surfaced. The original GridDebugAgent loop without the gate. |
| prompt files | _shared/common_rules.txt, _shared/output_contract.txt, _shared/agent_system_prompt.txt |

## Where every scenario ended

The three outcomes are exclusive and sum to the scenario count. Escalation takes precedence: a scenario the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 2 | 28.6% |
| Escalated to a person | 5 | 71.4% |
| Wrong, unflagged | 0 | 0.0% |
| **Total** | **7** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Diagnosis exact | 2/7 (28.6%) |
| Task utility | Diagnosis error types | {'wrong_type': 4, 'wrong_components': 1} |
| Task utility | Repaired (secure final network) | 2/7 (28.6%) |
| Task utility | Improved | 6/7 (85.7%) |
| Task utility | New violations, before -> after (scenarios converged at both ends, n=6) | 36 -> 18 |
| Task utility | Load served, mean / worst | 96.6 % / 30.9 % of the base network's demand |
| Solver-grounded correctness | Feasible (final power flow converges) | 7/7 (100.0%) |
| Solver-grounded correctness | Traceable answers | 7/7 (100.0%) |
| Solver-grounded correctness | Wrong, unflagged | 0/7 (0.0%) |
| Cost and operation | Escalated | 5/7 (71.4%) |
| Cost and operation | LLM calls / tool calls, mean | 11.86 / 27.71 |
| Cost and operation | Prompt / completion tokens, mean | 70293.29 / 1113.71 |
| Cost and operation | Cost, total | $0.0785 |
| Cost and operation | Wall time, mean | 23.14 s |

## By scenario category (the generator's intent)

| category | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| contingency | 2 | 0 | 2 | 0 | 0 | 0 |
| nonconvergence | 2 | 1 | 1 | 0 | 1 | 1 |
| normal | 1 | 1 | 0 | 0 | 1 | 1 |
| voltage | 2 | 0 | 2 | 0 | 0 | 0 |

## By measured initial state

| initial_state | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| islanded_load | 1 | 1 | 0 | 0 | 1 | 1 |
| not_converged | 1 | 0 | 1 | 0 | 0 | 0 |
| secure | 1 | 1 | 0 | 0 | 1 | 1 |
| violations | 4 | 0 | 4 | 0 | 0 | 0 |

## Why it escalated

An escalation after a real improvement is not the same as a refusal, and one caused by the budget ending on an action is not the same as either. The column counts them together because a person still has to act; this table says which kind they were.

| kind | count |
|---|---:|
| budget exhausted | 3 |
| declared, after improving the network | 1 |
| declared, network no better than it started | 1 |

## Wrong and unflagged (0)

none

## Escalated (5)

- `02_case14-extreme_load_scaling-v0` extreme_load_scaling: escalated: declared not_repaired — budget exhausted
- `03_case14-heavy_loading_undervoltage-v0` heavy_loading_undervoltage: escalated: declared not_repaired — declared, after improving the network
- `04_case14-heavy_loading_undervoltage-v1` heavy_loading_undervoltage: escalated: declared not_repaired — budget exhausted
- `05_case14-line_contingency_overload-v0` line_contingency_overload: escalated: declared not_repaired — budget exhausted
- `06_case14-line_contingency_overload-v1` line_contingency_overload: escalated: declared not_repaired — declared, network no better than it started

## Every scenario

| nn | scenario | initial | outcome | diagnosis | final | actions | LLM/tool calls | tokens | why |
|---|---|---|---|---|---|---:|---|---|---|
| 01 | disconnected_subnetwork-v0 | islanded_load (7) | solved | ok | secure | 14 | 11/30 | 76462 | secure, claimed, traceable, consistent |
| 02 | extreme_load_scaling-v0 | not_converged (None) | escalated | wrong_type | 1 new | 15 | 20/40 | 109737 | escalated: declared not_repaired |
| 03 | heavy_loading_undervoltage-v0 | violations (11) | escalated | wrong_type | 9 new | 3 | 5/11 | 30740 | escalated: declared not_repaired |
| 04 | heavy_loading_undervoltage-v1 | violations (11) | escalated | wrong_type | 2 new | 28 | 9/40 | 68319 | escalated: declared not_repaired |
| 05 | line_contingency_overload-v0 | violations (5) | escalated | wrong_type | 3 new | 17 | 18/40 | 135340 | escalated: declared not_repaired |
| 06 | line_contingency_overload-v1 | violations (2) | escalated | wrong_components | 4 new | 3 | 7/11 | 25670 | escalated: declared not_repaired |
| 07 | normal_operation-v0 | secure (0) | solved | ok | secure | 6 | 13/22 | 53581 | secure, claimed, traceable, consistent |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace).

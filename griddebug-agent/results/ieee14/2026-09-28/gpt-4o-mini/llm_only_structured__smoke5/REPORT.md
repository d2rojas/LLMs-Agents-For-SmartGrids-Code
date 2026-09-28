# llm_only_structured on IEEE 14-bus with gpt-4o-mini

Generated 2026-09-28 10:18 by evaluation/postprocess.py from `raw/rows.jsonl`. Scenarios: 7. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the harness's own power flow, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-28 |
| model | openrouter:openai/gpt-4o-mini |
| method | llm_only_structured |
| case | case14 |
| condition | normal |
| n | 7 |
| temperature | 0.0 |
| max_llm_calls | 20 |
| max_tool_calls | 40 |
| timeout_s | 600.0 |
| system_prompt_hash | 728bd2aad76b |
| git_commit | c7673488-dirty |
| pandapower | 3.5.5 |
| description | One call, no tools. The model reads the evidence block and the action catalogue as text, and writes the diagnosis, the list of actions and the final state it claims. The harness applies the actions once and runs the power flow to score them. |
| prompt files | _shared/common_rules.txt, _shared/output_contract.txt, _shared/llm_only_system_prompt.txt |

## Where every scenario ended

The three outcomes are exclusive and sum to the scenario count. Escalation takes precedence: a scenario the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 1 | 14.3% |
| Escalated to a person | 1 | 14.3% |
| Wrong, unflagged | 5 | 71.4% |
| **Total** | **7** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Diagnosis exact | 2/7 (28.6%) |
| Task utility | Diagnosis error types | {'wrong_type': 5} |
| Task utility | Repaired (secure final network) | 1/7 (14.3%) |
| Task utility | Improved | 5/7 (71.4%) |
| Task utility | New violations, before -> after (scenarios converged at both ends, n=6) | 36 -> 29 |
| Task utility | Load served, mean / worst | 116.74 % / 72.6 % of the base network's demand |
| Solver-grounded correctness | Feasible (final power flow converges) | 7/7 (100.0%) |
| Solver-grounded correctness | Traceable answers | 4/7 (57.1%) |
| Solver-grounded correctness | Wrong, unflagged | 5/7 (71.4%) |
| Cost and operation | Escalated | 1/7 (14.3%) |
| Cost and operation | LLM calls / tool calls, mean | 1.0 / 0.0 |
| Cost and operation | Prompt / completion tokens, mean | 2575.86 / 374.29 |
| Cost and operation | Cost, total | $0.0043 |
| Cost and operation | Wall time, mean | 5.96 s |

## By scenario category (the generator's intent)

| category | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| contingency | 2 | 0 | 0 | 2 | 0 | 0 |
| nonconvergence | 2 | 0 | 1 | 1 | 0 | 1 |
| normal | 1 | 1 | 0 | 0 | 1 | 1 |
| voltage | 2 | 0 | 0 | 2 | 0 | 0 |

## By measured initial state

| initial_state | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| islanded_load | 1 | 0 | 0 | 1 | 0 | 1 |
| not_converged | 1 | 0 | 1 | 0 | 0 | 0 |
| secure | 1 | 1 | 0 | 0 | 1 | 1 |
| violations | 4 | 0 | 0 | 4 | 0 | 0 |

## Why it escalated

An escalation after a real improvement is not the same as a refusal, and one caused by the budget ending on an action is not the same as either. The column counts them together because a person still has to act; this table says which kind they were.

| kind | count |
|---|---:|
| declared, after improving the network | 1 |

## Wrong and unflagged (5)

- `01_case14-disconnected_subnetwork-v0` disconnected_subnetwork: claimed repaired but the solver's final network load on islanded bus(es) [1]
- `03_case14-heavy_loading_undervoltage-v0` heavy_loading_undervoltage: claimed repaired but the solver's final network 8 violation(s) beyond the base network
- `04_case14-heavy_loading_undervoltage-v1` heavy_loading_undervoltage: claimed repaired but the solver's final network 9 violation(s) beyond the base network
- `05_case14-line_contingency_overload-v0` line_contingency_overload: claimed repaired but the solver's final network 6 violation(s) beyond the base network
- `06_case14-line_contingency_overload-v1` line_contingency_overload: claimed repaired but the solver's final network 2 violation(s) beyond the base network

## Escalated (1)

- `02_case14-extreme_load_scaling-v0` extreme_load_scaling: escalated: declared not_repaired — declared, after improving the network

## Every scenario

| nn | scenario | initial | outcome | diagnosis | final | actions | LLM/tool calls | tokens | why |
|---|---|---|---|---|---|---:|---|---|---|
| 01 | disconnected_subnetwork-v0 | islanded_load (7) | wrong_unflagged | ok | 4 new, islanded [1] | 5 | 1/0 | 3078 | claimed repaired but the solver's final network load on islanded bus(es) [1] |
| 02 | extreme_load_scaling-v0 | not_converged (None) | escalated | wrong_type | 7 new | 2 | 1/0 | 2729 | escalated: declared not_repaired |
| 03 | heavy_loading_undervoltage-v0 | violations (11) | wrong_unflagged | wrong_type | 8 new | 11 | 1/0 | 3379 | claimed repaired but the solver's final network 8 violation(s) beyond the base network |
| 04 | heavy_loading_undervoltage-v1 | violations (11) | wrong_unflagged | wrong_type | 9 new | 4 | 1/0 | 3108 | claimed repaired but the solver's final network 9 violation(s) beyond the base network |
| 05 | line_contingency_overload-v0 | violations (5) | wrong_unflagged | wrong_type | 6 new | 4 | 1/0 | 2949 | claimed repaired but the solver's final network 6 violation(s) beyond the base network |
| 06 | line_contingency_overload-v1 | violations (2) | wrong_unflagged | wrong_type | 2 new | 2 | 1/0 | 2771 | claimed repaired but the solver's final network 2 violation(s) beyond the base network |
| 07 | normal_operation-v0 | secure (0) | solved | ok | secure | 0 | 1/0 | 2637 | secure, claimed, traceable, consistent |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace).

# llm_only_cot on IEEE 14-bus with gpt-4o-mini

Generated 2026-09-28 11:07 by evaluation/postprocess.py from `raw/rows.jsonl`. Scenarios: 7. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the harness's own power flow, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-28 |
| model | openrouter:openai/gpt-4o-mini |
| method | llm_only_cot |
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
| description | The structured prompt plus one reasoning section asking the model to reason step by step before the answer. Identical to the row above in every other respect. |
| prompt files | _shared/common_rules.txt, _shared/output_contract.txt, _shared/llm_only_system_prompt.txt, llm_only_cot/reasoning_section.txt |

## Where every scenario ended

The three outcomes are exclusive and sum to the scenario count. Escalation takes precedence: a scenario the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 1 | 14.3% |
| Escalated to a person | 2 | 28.6% |
| Wrong, unflagged | 4 | 57.1% |
| **Total** | **7** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Diagnosis exact | 0/7 (0.0%) |
| Task utility | Diagnosis error types | {'wrong_type': 7} |
| Task utility | Repaired (secure final network) | 1/7 (14.3%) |
| Task utility | Improved | 3/7 (42.9%) |
| Task utility | New violations, before -> after (scenarios converged at both ends, n=6) | 36 -> 35 |
| Task utility | Load served, mean / worst | 89.46 % / 67.3 % of the base network's demand (a scenario that still carries the injected load increase counts as 100, not more) |
| Solver-grounded correctness | Solved autonomously | 1/7 (14.3%) |
| Solver-grounded correctness | Escalated to a person | 2/7 (28.6%) |
| Solver-grounded correctness | Wrong, unflagged | 4/7 (57.1%) |
| Solver-grounded correctness | Feasible (final power flow converges) | 7/7 (100.0%) |
| Solver-grounded correctness | Traceable answers | 7/7 (100.0%) |
| Cost and operation | LLM calls / tool calls, mean | 1.0 / 0.0 |
| Cost and operation | Prompt / completion tokens, mean | 2667.86 / 645.57 |
| Cost and operation | Cost, total | $0.0055 |
| Cost and operation | Wall time, mean | 8.04 s |

## By scenario category (the generator's intent)

| category | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| contingency | 2 | 0 | 0 | 2 | 0 | 0 |
| nonconvergence | 2 | 0 | 1 | 1 | 0 | 0 |
| normal | 1 | 1 | 0 | 0 | 1 | 0 |
| voltage | 2 | 0 | 1 | 1 | 0 | 0 |

## By measured initial state

| initial_state | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| islanded_load | 1 | 0 | 1 | 0 | 0 | 0 |
| not_converged | 1 | 0 | 0 | 1 | 0 | 0 |
| secure | 1 | 1 | 0 | 0 | 1 | 0 |
| violations | 4 | 0 | 1 | 3 | 0 | 0 |

## Why it escalated

An escalation after a real improvement is not the same as a refusal, and one caused by the budget ending on an action is not the same as either. The column counts them together because a person still has to act; this table says which kind they were.

| kind | count |
|---|---:|
| declared, network no better than it started | 2 |

## Wrong and unflagged (4)

- `02_case14-extreme_load_scaling-v0` extreme_load_scaling: claimed repaired but the solver's final network 8 violation(s) beyond the base network
- `04_case14-heavy_loading_undervoltage-v1` heavy_loading_undervoltage: claimed repaired but the solver's final network 10 violation(s) beyond the base network
- `05_case14-line_contingency_overload-v0` line_contingency_overload: claimed repaired but the solver's final network 5 violation(s) beyond the base network
- `06_case14-line_contingency_overload-v1` line_contingency_overload: claimed repaired but the solver's final network 2 violation(s) beyond the base network

## Escalated (2)

- `01_case14-disconnected_subnetwork-v0` disconnected_subnetwork: escalated: declared not_repaired — declared, network no better than it started
- `03_case14-heavy_loading_undervoltage-v0` heavy_loading_undervoltage: escalated: declared not_repaired — declared, network no better than it started

## Every scenario

| nn | scenario | initial | outcome | diagnosis | final | actions | LLM/tool calls | tokens | why |
|---|---|---|---|---|---|---:|---|---|---|
| 01 | disconnected_subnetwork-v0 | islanded_load (7) | escalated | wrong_type | 7 new, islanded [1] | 2 | 1/0 | 3427 | escalated: declared not_repaired |
| 02 | extreme_load_scaling-v0 | not_converged (None) | wrong_unflagged | wrong_type | 8 new | 1 | 1/0 | 3022 | claimed repaired but the solver's final network 8 violation(s) beyond the base network |
| 03 | heavy_loading_undervoltage-v0 | violations (11) | escalated | wrong_type | 11 new | 2 | 1/0 | 3529 | escalated: declared not_repaired |
| 04 | heavy_loading_undervoltage-v1 | violations (11) | wrong_unflagged | wrong_type | 10 new | 3 | 1/0 | 3429 | claimed repaired but the solver's final network 10 violation(s) beyond the base network |
| 05 | line_contingency_overload-v0 | violations (5) | wrong_unflagged | wrong_type | 5 new | 3 | 1/0 | 3324 | claimed repaired but the solver's final network 5 violation(s) beyond the base network |
| 06 | line_contingency_overload-v1 | violations (2) | wrong_unflagged | wrong_type | 2 new | 2 | 1/0 | 3262 | claimed repaired but the solver's final network 2 violation(s) beyond the base network |
| 07 | normal_operation-v0 | secure (0) | solved | wrong_type | secure | 2 | 1/0 | 3201 | secure, claimed, traceable, consistent |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace).

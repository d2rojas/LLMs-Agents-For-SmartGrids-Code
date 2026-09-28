# griddebug on IEEE 14-bus with gpt-4o-mini

Generated 2026-09-28 13:37 by evaluation/postprocess.py from `raw/rows.jsonl`. Scenarios: 7. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the harness's own power flow, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-28 |
| model | openrouter:openai/gpt-4o-mini |
| method | griddebug |
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
| description | The same loop as ReAct plus the verification gate G1-G7 on the final answer: the harness re-runs the power flow on the final network and checks convergence, islanded load, security or a declared remainder, currency, traceability, consistency, and that the actions claimed are the ones the trace shows succeeding. One retry, then a declared failure. The solver-grounded row. |
| prompt files | _shared/common_rules.txt, _shared/output_contract.txt, _shared/agent_system_prompt.txt, _shared/gate_retry_instruction.txt |

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
| Task utility | Diagnosis error types | {'wrong_type': 6} |
| Task utility | Repaired (secure final network) | 0/7 (0.0%) |
| Task utility | Improved | 5/7 (71.4%) |
| Task utility | New violations, before -> after (scenarios converged at both ends, n=6) | 36 -> 21 |
| Task utility | Load served, mean / worst | 57.44 % / 0.0 % of the base network's demand (a scenario that still carries the injected load increase counts as 100, not more) |
| Solver-grounded correctness | Solved autonomously | 0/7 (0.0%) |
| Solver-grounded correctness | Escalated to a person | 7/7 (100.0%) |
| Solver-grounded correctness | Wrong, unflagged | 0/7 (0.0%) |
| Solver-grounded correctness | Feasible (final power flow converges) | 7/7 (100.0%) |
| Solver-grounded correctness | Traceable answers | 7/7 (100.0%) |
| Cost and operation | LLM calls / tool calls, mean | 16.0 / 39.14 |
| Cost and operation | Prompt / completion tokens, mean | 99935.29 / 1455.43 |
| Cost and operation | Cost, total | $0.1110 |
| Cost and operation | Wall time, mean | 28.67 s |

## By scenario category (the generator's intent)

| category | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| contingency | 2 | 0 | 2 | 0 | 0 | 0 |
| nonconvergence | 2 | 0 | 2 | 0 | 0 | 0 |
| normal | 1 | 0 | 1 | 0 | 0 | 1 |
| voltage | 2 | 0 | 2 | 0 | 0 | 0 |

## By measured initial state

| initial_state | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| islanded_load | 1 | 0 | 1 | 0 | 0 | 0 |
| not_converged | 1 | 0 | 1 | 0 | 0 | 0 |
| secure | 1 | 0 | 1 | 0 | 0 | 1 |
| violations | 4 | 0 | 4 | 0 | 0 | 0 |

## Why it escalated

An escalation after a real improvement is not the same as a refusal, and one caused by the budget ending on an action is not the same as either. The column counts them together because a person still has to act; this table says which kind they were.

| kind | count |
|---|---:|
| budget ended on an action, nothing verified it | 2 |
| budget exhausted | 2 |
| the gate rejected the answer: actions_match_trace | 1 |
| the gate rejected the answer: consistent, actions_match_trace | 1 |
| the gate rejected the answer: secure_or_declared, actions_match_trace | 1 |

## Wrong and unflagged (0)

none

## Escalated (7)

- `01_case14-disconnected_subnetwork-v0` disconnected_subnetwork: escalated: gate rejected no_islanded_load, currency, consistent, actions_match_trace, declared cannot_repair — budget ended on an action, nothing verified it
- `02_case14-extreme_load_scaling-v0` extreme_load_scaling: escalated: gate rejected actions_match_trace, declared cannot_repair — the gate rejected the answer: actions_match_trace
- `03_case14-heavy_loading_undervoltage-v0` heavy_loading_undervoltage: escalated: declared not_repaired — budget exhausted
- `04_case14-heavy_loading_undervoltage-v1` heavy_loading_undervoltage: escalated: declared not_repaired — budget exhausted
- `05_case14-line_contingency_overload-v0` line_contingency_overload: escalated: gate rejected currency, consistent, actions_match_trace, declared cannot_repair — budget ended on an action, nothing verified it
- `06_case14-line_contingency_overload-v1` line_contingency_overload: escalated: gate rejected consistent, actions_match_trace, declared cannot_repair — the gate rejected the answer: consistent, actions_match_trace
- `07_case14-normal_operation-v0` normal_operation: escalated: budget exhausted, declared cannot_repair — the gate rejected the answer: secure_or_declared, actions_match_trace

## Every scenario

| nn | scenario | initial | outcome | diagnosis | final | actions | LLM/tool calls | tokens | why |
|---|---|---|---|---|---|---:|---|---|---|
| 01 | disconnected_subnetwork-v0 | islanded_load (7) | escalated | wrong_type | 1 new, islanded [1, 10, 12, 13] | 16 | 20/40 | 109374 | escalated: gate rejected no_islanded_load, currency, consistent, actions_match_trace, declared cannot_repair |
| 02 | extreme_load_scaling-v0 | not_converged (None) | escalated | wrong_type | 2 new | 20 | 16/40 | 123798 | escalated: gate rejected actions_match_trace, declared cannot_repair |
| 03 | heavy_loading_undervoltage-v0 | violations (11) | escalated | wrong_type | 8 new | 8 | 17/40 | 104208 | escalated: declared not_repaired |
| 04 | heavy_loading_undervoltage-v1 | violations (11) | escalated | wrong_type | 5 new | 18 | 18/40 | 146036 | escalated: declared not_repaired |
| 05 | line_contingency_overload-v0 | violations (5) | escalated | wrong_type | 4 new | 26 | 10/40 | 70205 | escalated: gate rejected currency, consistent, actions_match_trace, declared cannot_repair |
| 06 | line_contingency_overload-v1 | violations (2) | escalated | wrong_type | 2 new | 25 | 11/40 | 61363 | escalated: gate rejected consistent, actions_match_trace, declared cannot_repair |
| 07 | normal_operation-v0 | secure (0) | escalated | ok | 1 new | 9 | 20/34 | 94751 | escalated: budget exhausted, declared cannot_repair |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace).

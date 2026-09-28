# griddebug on IEEE 14-bus with gpt-4o-mini

Generated 2026-09-28 10:05 by evaluation/postprocess.py from `raw/rows.jsonl`. Scenarios: 7. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the harness's own power flow, the same way for every method.

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
| system_prompt_hash | d59378ee7244 |
| git_commit | 96531b84-dirty |
| pandapower | 3.5.5 |
| description | The same loop as ReAct plus the verification gate G1-G6 on the final answer: the harness re-runs the power flow on the final network and checks convergence, islanded load, security or a declared remainder, currency, traceability and consistency. One retry, then a declared failure. The solver-grounded row. |
| prompt files | _shared/common_rules.txt, _shared/output_contract.txt, _shared/agent_system_prompt.txt, _shared/gate_retry_instruction.txt |

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
| Task utility | Diagnosis exact | 0/7 (0.0%) |
| Task utility | Diagnosis error types | {'wrong_type': 5, 'wrong_components': 2} |
| Task utility | Repaired (secure final network) | 2/7 (28.6%) |
| Task utility | Improved | 6/7 (85.7%) |
| Task utility | New violations, before -> after (scenarios converged at both ends, n=6) | 36 -> 8 |
| Task utility | Load served, mean / worst | 84.89 % / 37.6 % of the base network's demand |
| Solver-grounded correctness | Feasible (final power flow converges) | 7/7 (100.0%) |
| Solver-grounded correctness | Traceable answers | 7/7 (100.0%) |
| Solver-grounded correctness | Wrong, unflagged | 0/7 (0.0%) |
| Cost and operation | Escalated | 5/7 (71.4%) |
| Cost and operation | LLM calls / tool calls, mean | 13.14 / 32.43 |
| Cost and operation | Prompt / completion tokens, mean | 65658.86 / 1525.57 |
| Cost and operation | Cost, total | $0.0754 |
| Cost and operation | Wall time, mean | 26.45 s |

## By scenario category (the generator's intent)

| category | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| contingency | 2 | 0 | 2 | 0 | 0 | 0 |
| nonconvergence | 2 | 1 | 1 | 0 | 1 | 0 |
| normal | 1 | 1 | 0 | 0 | 1 | 0 |
| voltage | 2 | 0 | 2 | 0 | 0 | 0 |

## By measured initial state

| initial_state | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| islanded_load | 1 | 0 | 1 | 0 | 0 | 0 |
| not_converged | 1 | 1 | 0 | 0 | 1 | 0 |
| secure | 1 | 1 | 0 | 0 | 1 | 0 |
| violations | 4 | 0 | 4 | 0 | 0 | 0 |

## Why it escalated

An escalation after a real improvement is not the same as a refusal, and one caused by the budget ending on an action is not the same as either. The column counts them together because a person still has to act; this table says which kind they were.

| kind | count |
|---|---:|
| the gate rejected the answer: actions_match_trace | 2 |
| the gate rejected the answer: no_islanded_load | 1 |
| the gate rejected the answer: no_islanded_load, consistent, actions_match_trace | 1 |
| the gate rejected the answer: secure_or_declared, consistent, actions_match_trace | 1 |

## Wrong and unflagged (0)

none

## Escalated (5)

- `01_case14-disconnected_subnetwork-v0` disconnected_subnetwork: escalated: gate rejected no_islanded_load, declared cannot_repair — the gate rejected the answer: no_islanded_load
- `03_case14-heavy_loading_undervoltage-v0` heavy_loading_undervoltage: escalated: gate rejected actions_match_trace, declared cannot_repair — the gate rejected the answer: actions_match_trace
- `04_case14-heavy_loading_undervoltage-v1` heavy_loading_undervoltage: escalated: gate rejected actions_match_trace, declared cannot_repair — the gate rejected the answer: actions_match_trace
- `05_case14-line_contingency_overload-v0` line_contingency_overload: escalated: gate rejected no_islanded_load, consistent, actions_match_trace, declared cannot_repair — the gate rejected the answer: no_islanded_load, consistent, actions_match_trace
- `06_case14-line_contingency_overload-v1` line_contingency_overload: escalated: gate rejected secure_or_declared, consistent, actions_match_trace, declared cannot_repair — the gate rejected the answer: secure_or_declared, consistent, actions_match_trace

## Every scenario

| nn | scenario | initial | outcome | diagnosis | final | actions | LLM/tool calls | tokens | why |
|---|---|---|---|---|---|---:|---|---|---|
| 01 | disconnected_subnetwork-v0 | islanded_load (7) | escalated | wrong_type | 1 new, islanded [10, 13] | 16 | 17/40 | 87679 | escalated: gate rejected no_islanded_load, declared cannot_repair |
| 02 | extreme_load_scaling-v0 | not_converged (None) | solved | wrong_type | secure | 12 | 7/21 | 28898 | secure, claimed, traceable, consistent |
| 03 | heavy_loading_undervoltage-v0 | violations (11) | escalated | wrong_type | 1 new | 24 | 10/39 | 58651 | escalated: gate rejected actions_match_trace, declared cannot_repair |
| 04 | heavy_loading_undervoltage-v1 | violations (11) | escalated | wrong_type | 3 new | 26 | 12/38 | 68665 | escalated: gate rejected actions_match_trace, declared cannot_repair |
| 05 | line_contingency_overload-v0 | violations (5) | escalated | wrong_components | 0 new, islanded [9, 10, 11, 12, 13] | 11 | 20/39 | 102917 | escalated: gate rejected no_islanded_load, consistent, actions_match_trace, declared cannot_repair |
| 06 | line_contingency_overload-v1 | violations (2) | escalated | wrong_components | 3 new | 18 | 19/40 | 97538 | escalated: gate rejected secure_or_declared, consistent, actions_match_trace, declared cannot_repair |
| 07 | normal_operation-v0 | secure (0) | solved | wrong_type | secure | 4 | 7/10 | 25943 | secure, claimed, traceable, consistent |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace).

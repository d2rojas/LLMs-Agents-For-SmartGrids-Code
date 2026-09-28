# rule_based on IEEE 14-bus with no-llm

Generated 2026-09-28 13:38 by evaluation/postprocess.py from `raw/rows.jsonl`. Scenarios: 7. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the harness's own power flow, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-28 |
| model | none:rule_based |
| method | rule_based |
| case | case14 |
| condition | normal |
| n | 7 |
| temperature | 0.0 |
| max_llm_calls | 20 |
| max_tool_calls | 40 |
| timeout_s | 600.0 |
| system_prompt_hash | None |
| git_commit | 96531b84-dirty |
| pandapower | 3.5.5 |
| description | The rule engine classifies the evidence and a fixed policy maps each triggered rule to actions; the power flow verifies after each one, inside the same budget as the agents. No language model. The conventional-automation row. |
| prompt files | (none) |

## Where every scenario ended

The three outcomes are exclusive and sum to the scenario count. Escalation takes precedence: a scenario the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 5 | 71.4% |
| Escalated to a person | 2 | 28.6% |
| Wrong, unflagged | 0 | 0.0% |
| **Total** | **7** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Diagnosis exact | 3/7 (42.9%) |
| Task utility | Diagnosis error types | {'wrong_type': 4} |
| Task utility | Repaired (secure final network) | 5/7 (71.4%) |
| Task utility | Improved | 7/7 (100.0%) |
| Task utility | New violations, before -> after (scenarios converged at both ends, n=6) | 36 -> 4 |
| Task utility | Load served, mean / worst | 91.76 % / 46.8 % of the base network's demand (a scenario that still carries the injected load increase counts as 100, not more) |
| Solver-grounded correctness | Solved autonomously | 5/7 (71.4%) |
| Solver-grounded correctness | Escalated to a person | 2/7 (28.6%) |
| Solver-grounded correctness | Wrong, unflagged | 0/7 (0.0%) |
| Solver-grounded correctness | Feasible (final power flow converges) | 7/7 (100.0%) |
| Solver-grounded correctness | Traceable answers | 6/7 (85.7%) |
| Cost and operation | LLM calls / tool calls, mean | 0.0 / 20.86 |
| Cost and operation | Prompt / completion tokens, mean | 0.0 / 0.0 |
| Cost and operation | Cost, total | $0.0000 |
| Cost and operation | Wall time, mean | 0.39 s |

## By scenario category (the generator's intent)

| category | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| contingency | 2 | 2 | 0 | 0 | 2 | 2 |
| nonconvergence | 2 | 1 | 1 | 0 | 1 | 1 |
| normal | 1 | 1 | 0 | 0 | 1 | 0 |
| voltage | 2 | 1 | 1 | 0 | 1 | 0 |

## By measured initial state

| initial_state | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| islanded_load | 1 | 1 | 0 | 0 | 1 | 1 |
| not_converged | 1 | 0 | 1 | 0 | 0 | 0 |
| secure | 1 | 1 | 0 | 0 | 1 | 0 |
| violations | 4 | 3 | 1 | 0 | 3 | 2 |

## Why it escalated

An escalation after a real improvement is not the same as a refusal, and one caused by the budget ending on an action is not the same as either. The column counts them together because a person still has to act; this table says which kind they were.

| kind | count |
|---|---:|
| budget exhausted | 2 |

## Wrong and unflagged (0)

none

## Escalated (2)

- `02_case14-extreme_load_scaling-v0` extreme_load_scaling: escalated: declared not_repaired — budget exhausted
- `04_case14-heavy_loading_undervoltage-v1` heavy_loading_undervoltage: escalated: declared not_repaired — budget exhausted

## Every scenario

| nn | scenario | initial | outcome | diagnosis | final | actions | LLM/tool calls | tokens | why |
|---|---|---|---|---|---|---:|---|---|---|
| 01 | disconnected_subnetwork-v0 | islanded_load (7) | solved | ok | secure | 4 | 0/10 | 0 | secure, claimed, traceable, consistent |
| 02 | extreme_load_scaling-v0 | not_converged (None) | escalated | wrong_type | 7 new | 12 | 0/40 | 0 | escalated: declared not_repaired |
| 03 | heavy_loading_undervoltage-v0 | violations (11) | solved | wrong_type | secure | 8 | 0/40 | 0 | secure, claimed, traceable, consistent |
| 04 | heavy_loading_undervoltage-v1 | violations (11) | escalated | wrong_type | 4 new | 8 | 0/40 | 0 | escalated: declared not_repaired |
| 05 | line_contingency_overload-v0 | violations (5) | solved | ok | secure | 1 | 0/7 | 0 | secure, claimed, traceable, consistent |
| 06 | line_contingency_overload-v1 | violations (2) | solved | ok | secure | 1 | 0/7 | 0 | secure, claimed, traceable, consistent |
| 07 | normal_operation-v0 | secure (0) | solved | wrong_type | secure | 0 | 0/2 | 0 | secure, claimed, traceable, consistent |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace).

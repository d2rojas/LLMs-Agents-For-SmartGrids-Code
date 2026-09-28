# rule_based on IEEE 14-bus with no-llm

Generated 2026-09-27 18:40 by evaluation/postprocess.py from `raw/rows.jsonl`. Scenarios: 3. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the harness's own power flow, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-27 |
| model | none:rule_based |
| method | rule_based |
| case | case14 |
| condition | normal |
| n | 3 |
| temperature | 0.0 |
| max_llm_calls | 20 |
| max_tool_calls | 40 |
| timeout_s | 600.0 |
| system_prompt_hash | None |
| git_commit | 5ff343de |
| pandapower | 3.5.5 |
| description | The rule engine classifies the evidence and a fixed policy maps each triggered rule to actions; the power flow verifies after each one, inside the same budget as the agents. No language model. The conventional-automation row. |
| prompt files | (none) |

## Where every scenario ended

The three outcomes are exclusive and sum to the scenario count. Escalation takes precedence: a scenario the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 2 | 66.7% |
| Escalated to a person | 1 | 33.3% |
| Wrong, unflagged | 0 | 0.0% |
| **Total** | **3** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Diagnosis exact | 1/3 (33.3%) |
| Task utility | Diagnosis error types | {'wrong_type': 2} |
| Task utility | Repaired (secure final network) | 2/3 (66.7%) |
| Task utility | Improved | 3/3 (100.0%) |
| Task utility | New violations, before -> after (scenarios converged at both ends, n=2) | 16 -> 0 |
| Solver-grounded correctness | Feasible (final power flow converges) | 3/3 (100.0%) |
| Solver-grounded correctness | Traceable answers | 3/3 (100.0%) |
| Solver-grounded correctness | Wrong, unflagged | 0/3 (0.0%) |
| Cost and operation | Escalated | 1/3 (33.3%) |
| Cost and operation | LLM calls / tool calls, mean | 0.0 / 29.0 |
| Cost and operation | Prompt / completion tokens, mean | 0.0 / 0.0 |
| Cost and operation | Cost, total | $0.0000 |
| Cost and operation | Wall time, mean | 0.56 s |

## By scenario category (the generator's intent)

| category | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| contingency | 1 | 1 | 0 | 0 | 1 | 1 |
| nonconvergence | 1 | 0 | 1 | 0 | 0 | 0 |
| voltage | 1 | 1 | 0 | 0 | 1 | 0 |

## By measured initial state

| initial_state | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| not_converged | 1 | 0 | 1 | 0 | 0 | 0 |
| violations | 2 | 2 | 0 | 0 | 2 | 1 |

## Wrong and unflagged (0)

none

## Escalated (1)

- `01_case14-extreme_load_scaling` extreme_load_scaling: escalated: declared not_repaired

## Every scenario

| nn | scenario | initial | outcome | diagnosis | final | actions | LLM/tool calls | tokens | why |
|---|---|---|---|---|---|---:|---|---|---|
| 01 | extreme_load_scaling | not_converged (None) | escalated | wrong_type | 7 new | 12 | 0/40 | 0 | escalated: declared not_repaired |
| 02 | heavy_loading_undervoltage | violations (11) | solved | wrong_type | secure | 8 | 0/40 | 0 | secure, claimed, traceable, consistent |
| 03 | line_contingency_overload | violations (5) | solved | ok | secure | 1 | 0/7 | 0 | secure, claimed, traceable, consistent |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace).

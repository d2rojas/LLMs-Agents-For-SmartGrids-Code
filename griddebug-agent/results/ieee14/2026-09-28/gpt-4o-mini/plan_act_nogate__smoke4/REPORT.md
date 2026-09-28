# plan_act_nogate on IEEE 14-bus with gpt-4o-mini

Generated 2026-09-28 09:59 by evaluation/postprocess.py from `raw/rows.jsonl`. Scenarios: 7. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the harness's own power flow, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-28 |
| model | openrouter:openai/gpt-4o-mini |
| method | plan_act_nogate |
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
| description | One planning call emits the whole sequence of tool calls; the harness executes it in order without feedback; one answer call writes the answer from the results. Solver access without iteration. |
| prompt files | _shared/common_rules.txt, _shared/output_contract.txt, _shared/agent_system_prompt.txt, plan_act_nogate/plan_system_prompt.txt |

## Where every scenario ended

The three outcomes are exclusive and sum to the scenario count. Escalation takes precedence: a scenario the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 1 | 14.3% |
| Escalated to a person | 6 | 85.7% |
| Wrong, unflagged | 0 | 0.0% |
| **Total** | **7** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Diagnosis exact | 4/7 (57.1%) |
| Task utility | Diagnosis error types | {'wrong_type': 3} |
| Task utility | Repaired (secure final network) | 1/7 (14.3%) |
| Task utility | Improved | 5/7 (71.4%) |
| Task utility | New violations, before -> after (scenarios converged at both ends, n=6) | 36 -> 25 |
| Task utility | Load served, mean / worst | 128.16 % / 66.9 % of the base network's demand |
| Solver-grounded correctness | Feasible (final power flow converges) | 7/7 (100.0%) |
| Solver-grounded correctness | Traceable answers | 7/7 (100.0%) |
| Solver-grounded correctness | Wrong, unflagged | 0/7 (0.0%) |
| Cost and operation | Escalated | 6/7 (85.7%) |
| Cost and operation | LLM calls / tool calls, mean | 2.0 / 6.43 |
| Cost and operation | Prompt / completion tokens, mean | 5340.71 / 551.71 |
| Cost and operation | Cost, total | $0.0079 |
| Cost and operation | Wall time, mean | 8.1 s |

## By scenario category (the generator's intent)

| category | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| contingency | 2 | 0 | 2 | 0 | 0 | 0 |
| nonconvergence | 2 | 1 | 1 | 0 | 1 | 1 |
| normal | 1 | 0 | 1 | 0 | 0 | 1 |
| voltage | 2 | 0 | 2 | 0 | 0 | 2 |

## By measured initial state

| initial_state | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| islanded_load | 1 | 1 | 0 | 0 | 1 | 0 |
| not_converged | 1 | 0 | 1 | 0 | 0 | 1 |
| secure | 1 | 0 | 1 | 0 | 0 | 1 |
| violations | 4 | 0 | 4 | 0 | 0 | 2 |

## Why it escalated

An escalation after a real improvement is not the same as a refusal, and one caused by the budget ending on an action is not the same as either. The column counts them together because a person still has to act; this table says which kind they were.

| kind | count |
|---|---:|
| declared, after improving the network | 4 |
| declared, network no better than it started | 2 |

## Wrong and unflagged (0)

none

## Escalated (6)

- `02_case14-extreme_load_scaling-v0` extreme_load_scaling: escalated: declared not_repaired — declared, after improving the network
- `03_case14-heavy_loading_undervoltage-v0` heavy_loading_undervoltage: escalated: declared not_repaired — declared, after improving the network
- `04_case14-heavy_loading_undervoltage-v1` heavy_loading_undervoltage: escalated: declared not_repaired — declared, after improving the network
- `05_case14-line_contingency_overload-v0` line_contingency_overload: escalated: declared not_repaired — declared, after improving the network
- `06_case14-line_contingency_overload-v1` line_contingency_overload: escalated: declared not_repaired — declared, network no better than it started
- `07_case14-normal_operation-v0` normal_operation: escalated: declared not_repaired — declared, network no better than it started

## Every scenario

| nn | scenario | initial | outcome | diagnosis | final | actions | LLM/tool calls | tokens | why |
|---|---|---|---|---|---|---:|---|---|---|
| 01 | disconnected_subnetwork-v0 | islanded_load (7) | solved | wrong_type | secure | 4 | 2/8 | 6080 | secure, claimed, traceable, consistent |
| 02 | extreme_load_scaling-v0 | not_converged (None) | escalated | ok | 8 new | 1 | 2/5 | 5460 | escalated: declared not_repaired |
| 03 | heavy_loading_undervoltage-v0 | violations (11) | escalated | ok | 8 new | 1 | 2/5 | 6142 | escalated: declared not_repaired |
| 04 | heavy_loading_undervoltage-v1 | violations (11) | escalated | ok | 10 new | 3 | 2/7 | 6436 | escalated: declared not_repaired |
| 05 | line_contingency_overload-v0 | violations (5) | escalated | wrong_type | 3 new | 3 | 2/7 | 5943 | escalated: declared not_repaired |
| 06 | line_contingency_overload-v1 | violations (2) | escalated | wrong_type | 2 new | 2 | 2/6 | 5571 | escalated: declared not_repaired |
| 07 | normal_operation-v0 | secure (0) | escalated | ok | 2 new | 3 | 2/7 | 5615 | escalated: declared not_repaired |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace).

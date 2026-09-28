# react_nogate on IEEE 14-bus with gpt-4o-mini

Generated 2026-09-27 18:42 by evaluation/postprocess.py from `raw/rows.jsonl`. Scenarios: 3. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the harness's own power flow, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-27 |
| model | openrouter:openai/gpt-4o-mini |
| method | react_nogate |
| case | case14 |
| condition | normal |
| n | 3 |
| temperature | 0.0 |
| max_llm_calls | 20 |
| max_tool_calls | 40 |
| timeout_s | 600.0 |
| system_prompt_hash | ebc0129ac659 |
| git_commit | 5ff343de |
| pandapower | 3.5.5 |
| description | Tool call, observation, repeat, inside the round budget. The model sees every tool output and decides the next call; nothing checks the answer before it is surfaced. The original GridDebugAgent loop without the gate. |
| prompt files | _shared/common_rules.txt, _shared/output_contract.txt, _shared/agent_system_prompt.txt |

## Where every scenario ended

The three outcomes are exclusive and sum to the scenario count. Escalation takes precedence: a scenario the method handed to a person is not an autonomous answer, right or wrong.

| outcome | count | share |
|---|---:|---:|
| Solved autonomously | 0 | 0.0% |
| Escalated to a person | 3 | 100.0% |
| Wrong, unflagged | 0 | 0.0% |
| **Total** | **3** | 100% |

## Metrics

| group | metric | value |
|---|---|---|
| Task utility | Diagnosis exact | 0/3 (0.0%) |
| Task utility | Diagnosis error types | {'wrong_type': 3} |
| Task utility | Repaired (secure final network) | 0/3 (0.0%) |
| Task utility | Improved | 3/3 (100.0%) |
| Task utility | New violations, before -> after (scenarios converged at both ends, n=2) | 16 -> 11 |
| Solver-grounded correctness | Feasible (final power flow converges) | 3/3 (100.0%) |
| Solver-grounded correctness | Traceable answers | 3/3 (100.0%) |
| Solver-grounded correctness | Wrong, unflagged | 0/3 (0.0%) |
| Cost and operation | Escalated | 3/3 (100.0%) |
| Cost and operation | LLM calls / tool calls, mean | 13.0 / 40.33 |
| Cost and operation | Prompt / completion tokens, mean | 86685.33 / 1478.33 |
| Cost and operation | Cost, total | $0.0417 |
| Cost and operation | Wall time, mean | 22.13 s |

## By scenario category (the generator's intent)

| category | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| contingency | 1 | 0 | 1 | 0 | 0 | 0 |
| nonconvergence | 1 | 0 | 1 | 0 | 0 | 0 |
| voltage | 1 | 0 | 1 | 0 | 0 | 0 |

## By measured initial state

| initial_state | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| not_converged | 1 | 0 | 1 | 0 | 0 | 0 |
| violations | 2 | 0 | 2 | 0 | 0 | 0 |

## Wrong and unflagged (0)

none

## Escalated (3)

- `01_case14-extreme_load_scaling` extreme_load_scaling: escalated: declared not_repaired
- `02_case14-heavy_loading_undervoltage` heavy_loading_undervoltage: escalated: declared not_repaired
- `03_case14-line_contingency_overload` line_contingency_overload: escalated: declared not_repaired

## Every scenario

| nn | scenario | initial | outcome | diagnosis | final | actions | LLM/tool calls | tokens | why |
|---|---|---|---|---|---|---:|---|---|---|
| 01 | extreme_load_scaling | not_converged (None) | escalated | wrong_type | 2 new | 24 | 11/41 | 82280 | escalated: declared not_repaired |
| 02 | heavy_loading_undervoltage | violations (11) | escalated | wrong_type | 8 new | 8 | 17/40 | 102979 | escalated: declared not_repaired |
| 03 | line_contingency_overload | violations (5) | escalated | wrong_type | 3 new | 25 | 11/40 | 79232 | escalated: declared not_repaired |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace).

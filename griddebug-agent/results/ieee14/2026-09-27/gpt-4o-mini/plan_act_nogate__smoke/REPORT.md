# plan_act_nogate on IEEE 14-bus with gpt-4o-mini

Generated 2026-09-28 13:37 by evaluation/postprocess.py from `raw/rows.jsonl`. Scenarios: 3. Scored by the one scorer (evaluation/scoring.py): every verdict below is read from the answer JSON, the tool log and the harness's own power flow, the same way for every method.

## Run

| field | value |
|---|---|
| date | 2026-09-27 |
| model | openrouter:openai/gpt-4o-mini |
| method | plan_act_nogate |
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
| description | One planning call emits the whole sequence of tool calls; the harness executes it in order without feedback; one answer call writes the answer from the results. Solver access without iteration. |
| prompt files | _shared/common_rules.txt, _shared/output_contract.txt, _shared/agent_system_prompt.txt, plan_act_nogate/plan_system_prompt.txt |

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
| Task utility | Diagnosis exact | 2/3 (66.7%) |
| Task utility | Diagnosis error types | {'wrong_type': 1} |
| Task utility | Repaired (secure final network) | 0/3 (0.0%) |
| Task utility | Improved | 3/3 (100.0%) |
| Task utility | New violations, before -> after (scenarios converged at both ends, n=2) | 16 -> 11 |
| Task utility | Load served, mean / worst | None % / None % of the base network's demand (a scenario that still carries the injected load increase counts as 100, not more) |
| Solver-grounded correctness | Solved autonomously | 0/3 (0.0%) |
| Solver-grounded correctness | Escalated to a person | 3/3 (100.0%) |
| Solver-grounded correctness | Wrong, unflagged | 0/3 (0.0%) |
| Solver-grounded correctness | Feasible (final power flow converges) | 3/3 (100.0%) |
| Solver-grounded correctness | Traceable answers | 2/3 (66.7%) |
| Cost and operation | LLM calls / tool calls, mean | 2.0 / 7.0 |
| Cost and operation | Prompt / completion tokens, mean | 5201.33 / 575.0 |
| Cost and operation | Cost, total | $0.0034 |
| Cost and operation | Wall time, mean | 7.9 s |

## By scenario category (the generator's intent)

| category | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| contingency | 1 | 0 | 1 | 0 | 0 | 0 |
| nonconvergence | 1 | 0 | 1 | 0 | 0 | 1 |
| voltage | 1 | 0 | 1 | 0 | 0 | 1 |

## By measured initial state

| initial_state | n | solved | escalated | wrong unflagged | repaired | diagnosis exact |
|---|---:|---:|---:|---:|---:|---:|
| not_converged | 1 | 0 | 1 | 0 | 0 | 1 |
| violations | 2 | 0 | 2 | 0 | 0 | 1 |

## Why it escalated

An escalation after a real improvement is not the same as a refusal, and one caused by the budget ending on an action is not the same as either. The column counts them together because a person still has to act; this table says which kind they were.

| kind | count |
|---|---:|
| unlabelled | 3 |

## Wrong and unflagged (0)

none

## Escalated (3)

- `01_case14-extreme_load_scaling` extreme_load_scaling: escalated: declared not_repaired
- `02_case14-heavy_loading_undervoltage` heavy_loading_undervoltage: escalated: declared not_repaired
- `03_case14-line_contingency_overload` line_contingency_overload: escalated: declared not_repaired

## Every scenario

| nn | scenario | initial | outcome | diagnosis | final | actions | LLM/tool calls | tokens | why |
|---|---|---|---|---|---|---:|---|---|---|
| 01 | extreme_load_scaling-v0 | not_converged (None) | escalated | ok | 8 new | 1 | 2/5 | 5195 | escalated: declared not_repaired |
| 02 | heavy_loading_undervoltage-v0 | violations (11) | escalated | ok | 8 new | 4 | 2/8 | 6289 | escalated: declared not_repaired |
| 03 | line_contingency_overload-v0 | violations (5) | escalated | wrong_type | 3 new | 4 | 2/8 | 5845 | escalated: declared not_repaired |

Traces: `traces/NN_<request-id>.narrative.txt` (what happened), `.transcript.txt` (the raw exchange), `.json` (the trace).

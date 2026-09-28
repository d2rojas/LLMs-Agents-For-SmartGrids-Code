# results/

One line per method folder, newest first. `python run.py index` rebuilds this.

| case | date | model | method | n | solved | escalated | wrong | diagnosis % | trace % | repaired | tokens | cost $ | kind | path |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ieee14 | 2026-09-27 | no-llm | rule_based__smoke | 3 | 2 | 1 | 0 | 33.3 | 100.0 | 2 | 0 | 0.0 | run | `ieee14/2026-09-27/no-llm/rule_based__smoke` |
| ieee14 | 2026-09-27 | gpt-4o-mini | react_nogate__smoke | 3 | 0 | 3 | 0 | 0.0 | 100.0 | 0 | 264491 | 0.0 | run | `ieee14/2026-09-27/gpt-4o-mini/react_nogate__smoke` |
| ieee14 | 2026-09-27 | gpt-4o-mini | plan_act_nogate__smoke | 3 | 0 | 3 | 0 | 66.7 | 66.7 | 0 | 17329 | 0.0 | run | `ieee14/2026-09-27/gpt-4o-mini/plan_act_nogate__smoke` |
| ieee14 | 2026-09-27 | gpt-4o-mini | llm_only_structured__smoke | 3 | 0 | 1 | 2 | 0.0 | 33.3 | 0 | 8698 | 0.0 | run | `ieee14/2026-09-27/gpt-4o-mini/llm_only_structured__smoke` |
| ieee14 | 2026-09-27 | gpt-4o-mini | llm_only_cot__smoke | 3 | 0 | 2 | 1 | 0.0 | 100.0 | 0 | 9650 | 0.0 | run | `ieee14/2026-09-27/gpt-4o-mini/llm_only_cot__smoke` |
| ieee14 | 2026-09-27 | gpt-4o-mini | griddebug__smoke | 3 | 0 | 3 | 0 | 0.0 | 100.0 | 0 | 279253 | 0.0 | run | `ieee14/2026-09-27/gpt-4o-mini/griddebug__smoke` |

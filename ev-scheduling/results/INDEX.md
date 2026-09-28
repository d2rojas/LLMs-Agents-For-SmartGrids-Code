# results/

One line per method folder, newest first. `python run.py index` rebuilds this.

| instance | date | model | method | n | solved | escalated | wrong | form % | trace % | tokens | cost $ | path |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| caltech | 2026-09-28 | no-llm | rule_based | 20 | 18 | 0 | 2 | 100.0 | - | 0 | 0.0 | `caltech/2026-09-28/no-llm/rule_based` |
| caltech | 2026-09-28 | gpt-4o-mini | react_nogate | 20 | 0 | 0 | 20 | 0.0 | 100.0 | 213684 | 0.1 | `caltech/2026-09-28/gpt-4o-mini/react_nogate` |
| caltech | 2026-09-28 | gpt-4o-mini | plan_act_nogate | 20 | 0 | 0 | 20 | 0.0 | 100.0 | 192442 | 0.1 | `caltech/2026-09-28/gpt-4o-mini/plan_act_nogate` |
| caltech | 2026-09-28 | gpt-4o-mini | llm_only_structured | 20 | 0 | 0 | 20 | 0.0 | - | 126140 | 0.1 | `caltech/2026-09-28/gpt-4o-mini/llm_only_structured` |
| caltech | 2026-09-28 | gpt-4o-mini | llm_only_cot | 20 | 0 | 0 | 20 | 5.3 | - | 162873 | 0.1 | `caltech/2026-09-28/gpt-4o-mini/llm_only_cot` |
| caltech | 2026-09-28 | gpt-4o-mini | evagent | 20 | 0 | 20 | 0 | 0.0 | 95.0 | 338793 | 0.1 | `caltech/2026-09-28/gpt-4o-mini/evagent` |

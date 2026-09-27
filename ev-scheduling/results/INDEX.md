# results/

One line per method folder, newest first. `python run.py index` rebuilds this.

| instance | date | model | method | n | solved | escalated | wrong | form % | trace % | tokens | cost $ | path |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| caltech | 2026-09-21 | no-llm | optimum | 20 | 20 | 0 | 0 | - | - | 0 | 0.0 | `caltech/2026-09-21/no-llm/optimum` |
| caltech | 2026-09-21 | no-llm | charge_asap | 20 | 0 | 0 | 20 | - | - | 0 | 0.0 | `caltech/2026-09-21/no-llm/charge_asap` |
| caltech | 2026-09-21 | gpt-4o-mini | llm_only_structured | 20 | 0 | 0 | 20 | - | - | 373337 | 0.2 | `caltech/2026-09-21/gpt-4o-mini/llm_only_structured` |
| caltech | 2026-09-21 | gpt-4o-mini | llm_only_cot | 20 | 0 | 0 | 20 | - | - | 378157 | 0.2 | `caltech/2026-09-21/gpt-4o-mini/llm_only_cot` |
| caltech | 2026-09-21 | gpt-4o-mini | evagent | 20 | 0 | 0 | 20 | 0.0 | 100.0 | 254543 | 0.1 | `caltech/2026-09-21/gpt-4o-mini/evagent` |

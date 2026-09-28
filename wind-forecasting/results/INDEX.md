# results/

One line per method folder, newest first. `python run.py index` rebuilds this.

| date | model | method | cond. | n | solved | escalated | wrong | Form. % | Trace. % | MAE kW | RMSE kW | tokens | cost $ | kind | path |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-09-28 | no-llm | rule_based | normal | 60 | 60 | 0 | 0 | 100.0 | 100.0 | 272.5 | 330.6 | 0 | 0.0 | run | `sdwpf/2026-09-28/no-llm/rule_based` |
| 2026-09-28 | no-llm | rule_based__scaled | scaled | 60 | 60 | 0 | 0 | 100.0 | 100.0 | 272.8 | 331.2 | 0 | 0.0 | run | `sdwpf/2026-09-28/no-llm/rule_based__scaled` |
| 2026-09-28 | gpt-4o-mini | windagent | normal | 60 | 16 | 44 | 0 | 100.0 | 100.0 | 302.5 | 356.3 | 2169404 | 0.4 | run | `sdwpf/2026-09-28/gpt-4o-mini/windagent` |
| 2026-09-28 | gpt-4o-mini | react_nogate | normal | 60 | 14 | 1 | 45 | 86.7 | 57.7 | 321.6 | 371.8 | 1244502 | 0.2 | run | `sdwpf/2026-09-28/gpt-4o-mini/react_nogate` |
| 2026-09-28 | gpt-4o-mini | plan_act_nogate | normal | 60 | 30 | 0 | 30 | 88.3 | 91.4 | 277.1 | 335.7 | 333503 | 0.1 | run | `sdwpf/2026-09-28/gpt-4o-mini/plan_act_nogate` |
| 2026-09-28 | gpt-4o-mini | llm_only_structured | normal | 60 | 14 | 0 | 46 | 66.7 | 0.0 | 458.4 | 504.0 | 2886519 | 0.5 | run | `sdwpf/2026-09-28/gpt-4o-mini/llm_only_structured` |
| 2026-09-28 | gpt-4o-mini | llm_only_cot | normal | 60 | 15 | 0 | 45 | 68.3 | 0.0 | 309.7 | 345.0 | 2918778 | 0.5 | run | `sdwpf/2026-09-28/gpt-4o-mini/llm_only_cot` |
| 2026-09-27 | no-llm | rule_based | normal | 60 | 60 | 0 | 0 | 100.0 | 100.0 | 280.7 | 333.1 | 0 | 0.0 | run | `sdwpf/2026-09-27/no-llm/rule_based` |
| 2026-09-27 | gpt-4o-mini | windagent__smoke | normal | 3 | 1 | 2 | 0 | 100.0 | 100.0 | 573.8 | 682.7 | 148951 | 0.0 | run | `sdwpf/2026-09-27/gpt-4o-mini/windagent__smoke` |
| 2026-09-27 | gpt-4o-mini | react_nogate__smoke | normal | 3 | 1 | 1 | 1 | 100.0 | 100.0 | 453.3 | 549.1 | 120750 | 0.0 | run | `sdwpf/2026-09-27/gpt-4o-mini/react_nogate__smoke` |
| 2026-09-27 | gpt-4o-mini | plan_act_nogate__smoke | normal | 3 | 1 | 0 | 2 | 100.0 | 100.0 | 383.5 | 465.8 | 22389 | 0.0 | run | `sdwpf/2026-09-27/gpt-4o-mini/plan_act_nogate__smoke` |
| 2026-09-27 | gpt-4o-mini | llm_only_structured__smoke | normal | 3 | 0 | 0 | 3 | 0.0 | - | - | - | 155638 | 0.0 | run | `sdwpf/2026-09-27/gpt-4o-mini/llm_only_structured__smoke` |
| 2026-09-27 | gpt-4o-mini | llm_only_cot__smoke | normal | 3 | 0 | 0 | 3 | 33.3 | 0.0 | - | - | 155313 | 0.0 | run | `sdwpf/2026-09-27/gpt-4o-mini/llm_only_cot__smoke` |

# Results index

Generated 2026-09-23 11:18 by `run.py index`. One line per run directory, newest first. Counts are runs; Form. and Trace. are percentages. Open the folder for `REPORT.md`, `summary.csv` and `traces/`.

## ieee14

| date | model | method | cond. | tools | n | solved | escalated | wrong unflagged | Form. % | Trace. % | tokens/run | cost $ | in the paper | folder |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 2026-09-21 | no-llm | rule_based | normal | v1 | 40 | 22 | 9 | 9 | 72.5 | 100.0 | 0 | 0.00 | main protocol table (Table 5 / S8) | [rule_based](ieee14/2026-09-21/no-llm/rule_based/REPORT.md) |
| 2026-09-21 | gpt-5.6-sol | single_call_structured | normal | load_split | 40 | 5 | 18 | 17 | 20.0 | 95.0 | 4930 | – | main protocol table (Table 5 / S8) | [single_call_structured](ieee14/2026-09-21/gpt-5.6-sol/single_call_structured/REPORT.md) |
| 2026-09-21 | gpt-5.6-sol | react_nogate | normal | v1 | 40 | 25 | 0 | 15 | 62.5 | 90.0 | 13465 | 1.25 | split-tool appendix, before side (original modify_load tool) | [react_nogate__v1](ieee14/2026-09-21/gpt-5.6-sol/react_nogate__v1/REPORT.md) |
| 2026-09-21 | gpt-5.6-sol | react_nogate | normal | load_split | 40 | 39 | 0 | 1 | 97.5 | 97.5 | 13385 | – | main protocol table (Table 5 / S8); split-tool appendix, after side (set_active_load/set_load) | [react_nogate](ieee14/2026-09-21/gpt-5.6-sol/react_nogate/REPORT.md) |
| 2026-09-21 | gpt-5.6-sol | plan_act_nogate | normal | load_split | 40 | 35 | 0 | 5 | 87.5 | 97.5 | 6469 | – | main protocol table (Table 5 / S8) | [plan_act_nogate](ieee14/2026-09-21/gpt-5.6-sol/plan_act_nogate/REPORT.md) |
| 2026-09-21 | gpt-5.6-sol | pfagent | normal | v1 | 40 | 25 | 0 | 15 | 62.5 | 100.0 | 17449 | 1.58 | split-tool appendix, before side (original modify_load tool) | [pfagent__v1](ieee14/2026-09-21/gpt-5.6-sol/pfagent__v1/REPORT.md) |
| 2026-09-21 | gpt-5.6-sol | pfagent | normal | load_split | 40 | 36 | 4 | 0 | 97.5 | 100.0 | 18210 | – | main protocol table (Table 5 / S8); split-tool appendix, after side (set_active_load/set_load) | [pfagent](ieee14/2026-09-21/gpt-5.6-sol/pfagent/REPORT.md) |
| 2026-09-21 | gpt-5.6-sol | llm_only_structured | normal | v1 | 40 | 11 | 0 | 29 | – | 0.0 | 10364 | 3.50 | main protocol table (Table 5 / S8) | [llm_only_structured](ieee14/2026-09-21/gpt-5.6-sol/llm_only_structured/REPORT.md) |
| 2026-09-21 | gpt-5.6-sol | llm_only_cot | normal | v1 | 40 | 14 | 2 | 24 | – | 0.0 | 10052 | 3.32 | main protocol table (Table 5 / S8) | [llm_only_cot](ieee14/2026-09-21/gpt-5.6-sol/llm_only_cot/REPORT.md) |
| 2026-09-21 | gpt-4o-mini | single_call_structured | normal | load_split | 40 | 26 | 0 | 14 | 95.0 | 95.0 | 10131 | – | main protocol table (Table 5 / S8) | [single_call_structured](ieee14/2026-09-21/gpt-4o-mini/single_call_structured/REPORT.md) |
| 2026-09-21 | gpt-4o-mini | react_nogate | normal | load_split | 40 | 29 | 0 | 11 | 100.0 | 97.5 | 7423 | – | main protocol table (Table 5 / S8); split-tool appendix, after side (set_active_load/set_load) | [react_nogate](ieee14/2026-09-21/gpt-4o-mini/react_nogate/REPORT.md) |
| 2026-09-21 | gpt-4o-mini | plan_act_nogate | normal | load_split | 40 | 18 | 0 | 22 | 75.0 | 82.5 | 5878 | – | main protocol table (Table 5 / S8) | [plan_act_nogate](ieee14/2026-09-21/gpt-4o-mini/plan_act_nogate/REPORT.md) |
| 2026-09-21 | gpt-4o-mini | pfagent | normal | load_split | 40 | 28 | 12 | 0 | 100.0 | 97.5 | 11714 | – | main protocol table (Table 5 / S8); split-tool appendix, after side (set_active_load/set_load) | [pfagent](ieee14/2026-09-21/gpt-4o-mini/pfagent/REPORT.md) |
| 2026-09-18 | gpt-5.4 | react_nogate | normal | load_split | 40 | 36 | 0 | 4 | 100.0 | 90.0 | 11460 | 1.30 | split-tool appendix, after side (set_active_load/set_load) | [react_nogate](ieee14/2026-09-18/gpt-5.4/react_nogate/REPORT.md) |
| 2026-09-18 | gpt-5.4 | plan_act_nogate | normal | v1 | 40 | 17 | 0 | 23 | 47.5 | 97.5 | 6209 | 0.82 | main protocol table (Table 5 / S8) | [plan_act_nogate](ieee14/2026-09-18/gpt-5.4/plan_act_nogate/REPORT.md) |
| 2026-09-18 | gpt-5.4 | pfagent | normal | load_split | 40 | 34 | 2 | 4 | 100.0 | 100.0 | 13475 | 1.53 | split-tool appendix, after side (set_active_load/set_load) | [pfagent](ieee14/2026-09-18/gpt-5.4/pfagent/REPORT.md) |
| 2026-09-18 | gpt-5.4 | llm_only_cot | normal | v1 | 40 | 6 | 0 | 34 | – | 0.0 | 2911 | 0.65 | main protocol table (Table 5 / S8) | [llm_only_cot](ieee14/2026-09-18/gpt-5.4/llm_only_cot/REPORT.md) |
| 2026-09-18 | gpt-4o-mini | llm_only_cot | normal | v1 | 40 | 0 | 32 | 8 | – | 5.0 | 2647 | 0.02 | main protocol table (Table 5 / S8) | [llm_only_cot](ieee14/2026-09-18/gpt-4o-mini/llm_only_cot/REPORT.md) |
| 2026-09-16 | no-llm | rule_based | stress | v1 | 40 | 0 | 22 | 18 | 40.0 | 97.5 | 0 | 0.00 | stress table (S6) | [rule_based__stress__from-stress_gpt-4o-mini](ieee14/2026-09-16/no-llm/rule_based__stress__from-stress_gpt-4o-mini/REPORT.md) |
| 2026-09-16 | no-llm | rule_based | stress | v1 | 10 | 0 | 4 | 6 | 50.0 | 100.0 | 0 | 0.00 | stress table (S6) | [rule_based__stress](ieee14/2026-09-16/no-llm/rule_based__stress/REPORT.md) |
| 2026-09-16 | no-llm | rule_based | normal | v1 | 40 | 22 | 9 | 9 | 72.5 | 100.0 | 0 | 0.00 | main protocol table (Table 5 / S8) | [rule_based](ieee14/2026-09-16/no-llm/rule_based/REPORT.md) |
| 2026-09-16 | gpt-5.4 | single_call_structured | normal | v1 | 40 | 4 | 0 | 36 | 20.0 | 87.5 | 4637 | 0.56 | main protocol table (Table 5 / S8) | [single_call_structured](ieee14/2026-09-16/gpt-5.4/single_call_structured/REPORT.md) |
| 2026-09-16 | gpt-5.4 | react_nogate | stress | v1 | 10 | 5 | 0 | 5 | 50.0 | 50.0 | 16333 | 0.46 | stress table (S6) | [react_nogate__stress](ieee14/2026-09-16/gpt-5.4/react_nogate__stress/REPORT.md) |
| 2026-09-16 | gpt-5.4 | react_nogate | normal | v1 | 40 | 24 | 0 | 16 | 62.5 | 90.0 | 11468 | 1.32 | main protocol table (Table 5 / S8); split-tool appendix, before side (original modify_load tool) | [react_nogate](ieee14/2026-09-16/gpt-5.4/react_nogate/REPORT.md) |
| 2026-09-16 | gpt-5.4 | pfagent | stress | v1 | 10 | 0 | 10 | 0 | 50.0 | 100.0 | 24422 | 0.69 | stress table (S6) | [pfagent__stress](ieee14/2026-09-16/gpt-5.4/pfagent__stress/REPORT.md) |
| 2026-09-16 | gpt-5.4 | pfagent | normal | v1 | 40 | 24 | 1 | 15 | 62.5 | 100.0 | 14195 | 1.61 | main protocol table (Table 5 / S8); split-tool appendix, before side (original modify_load tool) | [pfagent](ieee14/2026-09-16/gpt-5.4/pfagent/REPORT.md) |
| 2026-09-16 | gpt-5.4 | llm_only_structured | normal | v1 | 40 | 7 | 0 | 33 | – | 0.0 | 2578 | 0.54 | main protocol table (Table 5 / S8) | [llm_only_structured](ieee14/2026-09-16/gpt-5.4/llm_only_structured/REPORT.md) |
| 2026-09-16 | gpt-5.4 | llm_only_forced_structured | normal | v1 | 40 | 7 | 0 | 33 | – | 0.0 | 2817 | 0.67 | main protocol table (Table 5 / S8) | [llm_only_forced_structured](ieee14/2026-09-16/gpt-5.4/llm_only_forced_structured/REPORT.md) |
| 2026-09-16 | gpt-4o-mini | pfagent | stress | v1 | 40 | 0 | 40 | 0 | 100.0 | 100.0 | 20906 | 0.13 | stress table (S6) | [pfagent__stress](ieee14/2026-09-16/gpt-4o-mini/pfagent__stress/REPORT.md) |
| 2026-09-16 | gpt-4o-mini | pfagent | normal | v1 | 40 | 26 | 3 | 11 | 97.5 | 97.5 | 10441 | 0.07 | split-tool appendix, before side (original modify_load tool) | [pfagent](ieee14/2026-09-16/gpt-4o-mini/pfagent/REPORT.md) |
| 2026-09-16 | gpt-4o-mini | llm_only_structured | normal | v1 | 40 | 0 | 0 | 40 | – | 5.0 | 2082 | 0.01 | main protocol table (Table 5 / S8) | [llm_only_structured](ieee14/2026-09-16/gpt-4o-mini/llm_only_structured/REPORT.md) |
| 2026-09-16 | gpt-4o-mini | llm_only_forced_structured | normal | v1 | 40 | 0 | 0 | 40 | – | 0.0 | 2928 | 0.03 | main protocol table (Table 5 / S8) | [llm_only_forced_structured](ieee14/2026-09-16/gpt-4o-mini/llm_only_forced_structured/REPORT.md) |
| 2026-09-14 | no-llm | rule_based | normal | v1 | 40 | 22 | 9 | 9 | 72.5 | 100.0 | 0 | 0.00 | main protocol table (Table 5 / S8) | [rule_based](ieee14/2026-09-14/no-llm/rule_based/REPORT.md) |
| 2026-09-14 | gpt-4o-mini | react_nogate | normal | v1 | 40 | 26 | 0 | 14 | 97.5 | 87.5 | 7620 | 0.05 | split-tool appendix, before side (original modify_load tool) | [react_nogate](ieee14/2026-09-14/gpt-4o-mini/react_nogate/REPORT.md) |

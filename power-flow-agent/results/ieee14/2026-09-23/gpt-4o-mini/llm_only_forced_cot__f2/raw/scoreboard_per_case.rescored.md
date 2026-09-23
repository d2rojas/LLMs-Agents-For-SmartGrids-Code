# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only_forced:cot | case14 | 0.6 | 0.00 (0/40) | 0.0277 | 35.18 | 0.5561 | 0.582 | 1 | 1 | 2850 | 1267 | 4118 | 0.001188 | 0.04752 | 0.40 (16/40) | 0.09266 | n/a | n/a | 0.00 (0/40) | n/a | n/a | n/a | 1 | 0 | 15.03 |

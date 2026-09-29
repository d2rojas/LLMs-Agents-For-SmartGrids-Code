# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:cot | case14 | 0.8 | 0.00 (0/20) | 0.02521 | 22.08 | 58.5 | 0.5836 | 0.5128 | 1 | 3277 | 1485 | 4762 | 0.001383 | 0.02765 | 0.94 (15/16) | 0.07586 | n/a | n/a | 0.00 (0/20) | n/a | n/a | n/a | 1 | 0 | 20.33 |

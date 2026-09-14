# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | single_call:structured | case118 | 1 | 6.983e-06 | 1.436 | 0.0001207 | 0.9914 | 1 | 1 | 5.612e+04 | 221.4 | 5.634e+04 | 0.008551 | 0.342 | 0.82 (33/40) | 1 | n/a | n/a | 0.00 (0/26) | 0.00 (0/26) | 0.00 (0/26) | 2 | 2.05 | 7.33 |

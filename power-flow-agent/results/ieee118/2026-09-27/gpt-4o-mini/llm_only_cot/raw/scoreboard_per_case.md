# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:cot | case118 | 1 | 0.00 (0/20) | 0.07729 | 61.71 | 41.45 | 0.01619 | 0.2222 | 1 | 1.424e+04 | 6167 | 2.04e+04 | 0.005836 | 0.1167 | 1.00 (20/20) | 0.1431 | n/a | n/a | 0.00 (0/20) | n/a | n/a | n/a | 1 | 0 | 46.51 |

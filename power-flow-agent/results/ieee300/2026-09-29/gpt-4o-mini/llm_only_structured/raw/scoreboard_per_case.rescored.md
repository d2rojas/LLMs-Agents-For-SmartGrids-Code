# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:structured | case300 | 0.9 | 0.00 (0/20) | 0.04299 | 41.3 | 47.84 | 0.0272 | 0.07692 | 0.8889 | 2.553e+04 | 7514 | 3.304e+04 | 0.008338 | 0.1668 | 1.00 (18/18) | 0.1185 | n/a | n/a | 0.10 (2/20) | n/a | n/a | n/a | 1 | 0 | 173.1 |

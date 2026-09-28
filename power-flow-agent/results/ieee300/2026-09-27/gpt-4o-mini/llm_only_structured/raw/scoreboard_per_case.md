# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:structured | case300 | 0.9 | 0.00 (0/20) | 0.07981 | 65.29 | 41.5 | 0.03105 | 0.1429 | 1 | 2.553e+04 | 8405 | 3.393e+04 | 0.008872 | 0.1774 | 1.00 (18/18) | 0.1068 | n/a | n/a | 0.00 (0/20) | n/a | n/a | n/a | 1 | 0 | 60.75 |

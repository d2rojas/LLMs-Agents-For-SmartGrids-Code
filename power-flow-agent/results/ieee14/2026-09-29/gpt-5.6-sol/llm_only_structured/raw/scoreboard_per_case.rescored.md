# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.6-sol | llm_only:structured | case14 | 1 | 0.20 (4/20) | 0.0009965 | 0.3247 | 2.565 | 0.2899 | 0.7 | 0.3 | 3100 | 6258 | 9358 | 0.06878 | 1.376 | 1.00 (20/20) | 0.07395 | n/a | n/a | 0.70 (14/20) | n/a | n/a | n/a | 1 | 0 | 89.96 |

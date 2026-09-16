# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | single_call:structured | case14 | 1 | 0.20 (1/5) | 0.004302 | 1.573 | 0.02101 | 0.9538 | 1 | 1 | 4439 | 190.2 | 4629 | 0.01395 | 0.06975 | 0.20 (1/5) | 1 | n/a | n/a | 0.00 (0/5) | n/a | n/a | n/a | 2 | 1 | 5.079 |

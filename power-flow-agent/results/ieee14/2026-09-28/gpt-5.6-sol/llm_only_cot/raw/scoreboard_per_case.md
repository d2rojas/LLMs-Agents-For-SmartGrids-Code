# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.6-sol | llm_only:cot | case14 | 1 | 0.10 (2/20) | 0.0006886 | 0.8272 | 4.956 | 0.1 | 0.6 | 0.1 | 3276 | 4699 | 7975 | 0.05354 | 1.071 | 1.00 (20/20) | 0.09193 | n/a | n/a | 0.90 (18/20) | n/a | n/a | n/a | 1 | 0 | 75.11 |

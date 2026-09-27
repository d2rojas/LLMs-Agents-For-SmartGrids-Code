# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | case57 | 1 | 0.67 (2/3) | 2.229e-07 | 0.05283 | 0.314 | 1 | 1 | 1 | 5.694e+04 | 1.594e+04 | 7.288e+04 | 0.01811 | 0.05432 | 1.00 (3/3) | 1 | n/a | n/a | 0.33 (1/3) | 0.00 (0/3) | 0.00 (0/3) | 0.00 (0/3) | 5.333 | 3.667 | 118.2 |

# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | case118 | 1 | 0.33 (1/3) | 1.341e-07 | 1.742 | 3.104 | 0.8571 | 0.9744 | 1 | 2.166e+05 | 4.906e+04 | 2.656e+05 | 0.06192 | 0.1858 | 1.00 (3/3) | 1 | n/a | n/a | 0.67 (2/3) | 0.00 (0/3) | 0.00 (0/3) | 0.00 (0/3) | 7.333 | 4.333 | 573.2 |

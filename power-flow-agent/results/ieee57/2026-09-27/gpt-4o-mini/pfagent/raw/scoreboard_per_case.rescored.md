# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | case57 | 1 | 0.35 (7/20) | 2.243e-07 | 0.0525 | 0.2933 | 1 | 1 | 1 | 5.647e+04 | 1.09e+04 | 6.737e+04 | 0.01501 | 0.3002 | 1.00 (20/20) | 1 | n/a | n/a | 0.70 (14/20) | 0.00 (0/6) | 0.00 (0/6) | 0.00 (0/6) | 5.6 | 3.55 | 113 |

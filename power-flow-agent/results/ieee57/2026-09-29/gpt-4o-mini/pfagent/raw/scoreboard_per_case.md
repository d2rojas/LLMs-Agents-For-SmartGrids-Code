# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | case57 | 1 | 0.80 (16/20) | 2.243e-07 | 0.0525 | 0.2933 | 1 | 1 | 1 | 3.268e+04 | 8756 | 4.144e+04 | 0.01016 | 0.2031 | 1.00 (20/20) | 1 | n/a | n/a | 0.25 (5/20) | 0.00 (0/6) | 0.00 (0/6) | 0.00 (0/6) | 4.65 | 3 | 77.48 |

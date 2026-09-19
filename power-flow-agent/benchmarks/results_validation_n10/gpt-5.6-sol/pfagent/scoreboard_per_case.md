# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.6-sol | pfagent | case14 | 1 | 0.80 (8/10) | 8.147e-07 | 5.59e-05 | 2.918e-06 | 1 | 1 | 1 | 1.357e+04 | 458.6 | 1.403e+04 | 0.03174 | 0.3174 | 0.80 (8/10) | 1 | n/a | n/a | 0.00 (0/10) | 0.00 (0/6) | 0.00 (0/6) | 0.00 (0/6) | 4.2 | 3.2 | 18.08 |

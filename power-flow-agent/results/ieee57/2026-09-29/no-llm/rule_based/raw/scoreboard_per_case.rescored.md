# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none:rule_based | rule_based | case57 | 0.85 | 0.85 (17/20) | 2.261e-07 | 0.0528 | 0.2925 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0.85 (17/20) | 0.85 | n/a | n/a | 0.15 (3/20) | 0.00 (0/9) | 0.00 (0/9) | 0.00 (0/9) | 0 | 2.35 | 1.936 |

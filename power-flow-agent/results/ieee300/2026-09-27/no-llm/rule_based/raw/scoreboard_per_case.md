# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none:rule_based | rule_based | case300 | 0.9 | 0.90 (18/20) | 1.926e-07 | 0.000248 | 0.002882 | 0.9931 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0.90 (18/20) | 0.9 | n/a | n/a | 0.10 (2/20) | 0.00 (0/11) | 0.00 (0/11) | 0.00 (0/11) | 0 | 2.9 | 10.57 |

# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none:rule_based | rule_based | case14 | 0.775 | 0.55 (22/40) | 1.892e-05 | 0.05905 | 0.001041 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0.72 (29/40) | 1 | n/a | n/a | 0.23 (9/40) | 0.00 (0/23) | 0.00 (0/23) | 0.00 (0/23) | 0 | 1.875 | 0.2102 |

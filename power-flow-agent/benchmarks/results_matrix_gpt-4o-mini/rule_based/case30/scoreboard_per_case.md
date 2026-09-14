# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none:rule_based | rule_based | case30 | 0.775 | 4.82e-05 | 0.06482 | 0.5583 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0.68 (27/40) | 1 | n/a | n/a | 0.10 (2/21) | 0.00 (0/21) | 0.10 (2/21) | 0 | 1.9 | 0.08396 |

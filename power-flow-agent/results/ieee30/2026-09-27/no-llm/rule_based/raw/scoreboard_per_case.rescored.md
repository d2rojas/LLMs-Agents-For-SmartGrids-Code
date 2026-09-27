# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none:rule_based | rule_based | case30 | 0.9 | 0.85 (17/20) | 2.841e-05 | 0.02421 | 1.672 | 1 | 0.9722 | 1 | 0 | 0 | 0 | 0 | 0 | 0.85 (17/20) | 0.9 | n/a | n/a | 0.15 (3/20) | 0.00 (0/10) | 0.00 (0/10) | 0.00 (0/10) | 0 | 2.8 | 0.5825 |

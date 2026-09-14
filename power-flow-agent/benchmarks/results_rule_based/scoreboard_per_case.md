# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none:rule_based | rule_based | case118 | 0.725 | 4.493e-06 | 1.472 | 0.0001479 | 0.9931 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0.68 (27/40) | 1 | n/a | n/a | 0 | 1.725 | 0.07954 |
| none:rule_based | rule_based | case14 | 0.775 | 1.892e-05 | 0.05905 | 0.001041 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0.72 (29/40) | 1 | n/a | n/a | 0 | 1.875 | 0.1628 |
| none:rule_based | rule_based | case30 | 0.775 | 4.82e-05 | 0.06482 | 0.5583 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0.68 (27/40) | 1 | n/a | n/a | 0 | 1.9 | 0.07097 |
| none:rule_based | rule_based | case57 | 0.7 | 4.09e-05 | 0.1237 | 0.005898 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0.66 (25/38) | 1 | n/a | n/a | 0 | 1.675 | 0.1577 |

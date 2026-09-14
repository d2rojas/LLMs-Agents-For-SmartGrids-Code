# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14', 'case30', 'case57', 'case118'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none:rule_based | rule_based | 0.7438 | 2.82e-05 | 0.4201 | 0.1471 | 0.9983 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0.68 (108/158) | 1 | n/a | n/a | 0 | 1.794 | 0.1172 |

# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case118'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none:rule_based | rule_based | 0.725 | 0.50 (20/40) | 4.493e-06 | 1.472 | 0.0001479 | 0.9931 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0.68 (27/40) | 1 | n/a | n/a | 0.28 (11/40) | 0.00 (0/21) | 0.00 (0/21) | 0.00 (0/21) | 0 | 1.725 | 0.07997 |

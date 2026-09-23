# LLM Power-Flow Benchmark

k=1, seeds=[0, 1], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 5, 'difficulties': ['stress']}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none:rule_based | rule_based | 0.6 | 0.00 (0/10) | nan | 0 | nan | 1 | 1 | 0.8333 | 0 | 0 | 0 | 0 | 0 | 0.50 (5/10) | 1 | 0.40 (4/10) | 0.60 (6/10) | n/a | 0.00 (0/6) | 0.00 (0/6) | 0.00 (0/6) | 0 | 1.7 | 0.1483 |

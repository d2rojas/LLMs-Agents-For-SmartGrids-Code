# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case118'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | react | 1 | 0.80 (32/40) | 0 | 1.327 | 4.825e-05 | 1 | 1 | 1 | 3.26e+04 | 237.9 | 3.283e+04 | 0.005032 | 0.2013 | 1.00 (40/40) | 0.9953 | n/a | n/a | 0.00 (0/40) | 0.00 (0/26) | 0.00 (0/26) | 0.00 (0/26) | 2.8 | 2.35 | 5.698 |

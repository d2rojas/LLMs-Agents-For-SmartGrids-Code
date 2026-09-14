# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case30'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | single_call:structured | 1 | 1.759e-05 | 0.04351 | 0.2341 | 1 | 1 | 1 | 1.486e+04 | 195.9 | 1.506e+04 | 0.002347 | 0.09388 | 0.82 (33/40) | 0.995 | n/a | n/a | 0.04 (1/25) | 0.00 (0/25) | 0.04 (1/25) | 2 | 2.025 | 4.567 |

# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case30'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | single_call:few_shot | 1 | 0.93 (37/40) | 1.759e-05 | 0.04351 | 0.2341 | 1 | 1 | 1 | 1.5e+04 | 192.8 | 1.519e+04 | 0.002365 | 0.09461 | 0.93 (37/40) | 0.9964 | n/a | n/a | 0.00 (0/40) | 0.04 (1/25) | 0.00 (0/25) | 0.04 (1/25) | 2 | 1.975 | 3.754 |

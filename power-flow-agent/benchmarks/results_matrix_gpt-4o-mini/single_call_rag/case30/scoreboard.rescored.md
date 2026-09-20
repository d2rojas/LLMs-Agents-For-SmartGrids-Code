# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case30'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | single_call:rag | 1 | 0.78 (31/40) | 1.759e-05 | 0.04351 | 0.2341 | 1 | 1 | 1 | 9849 | 178.9 | 1.003e+04 | 0.001585 | 0.06339 | 0.90 (36/40) | 0.9949 | n/a | n/a | 0.03 (1/40) | 0.08 (2/25) | 0.00 (0/25) | 0.08 (2/25) | 2 | 1.775 | 3.982 |

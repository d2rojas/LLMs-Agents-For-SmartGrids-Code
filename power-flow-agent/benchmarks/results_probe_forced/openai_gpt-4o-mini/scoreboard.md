# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14', 'case30'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 20, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only_forced:cot | 0.875 | 0.00 (0/40) | 0.1593 | 25.58 | 34.8 | 0.7651 | 0.4303 | 1 | 3273 | 1741 | 5014 | 0.001535 | 0.06141 | n/a | 0.08548 | n/a | n/a | 0.03 (1/40) | n/a | n/a | n/a | 1 | 0 | 15.29 |
| openrouter:openai/gpt-4o-mini | llm_only_forced:structured | 0.925 | 0.00 (0/40) | 0.2195 | 20.36 | 25.34 | 0.8248 | 0.4595 | 1 | 3097 | 1444 | 4541 | 0.001331 | 0.05324 | n/a | 0.07223 | n/a | n/a | 0.00 (0/40) | n/a | n/a | n/a | 1 | 0 | 14.29 |

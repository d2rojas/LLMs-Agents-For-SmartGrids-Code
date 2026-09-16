# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 5, 'difficulties': ['stress']}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | pfagent | 1 | 0.60 (3/5) | nan | 0.01116 | nan | 1 | 1 | 1 | 2.581e+04 | 649.8 | 2.646e+04 | 0.07427 | 0.3714 | 0.60 (3/5) | None | 1.00 (5/5) | 0.00 (0/5) | 1.00 (3/3) | 0.00 (0/5) | 0.00 (0/5) | 0.00 (0/5) | 6 | 4 | 12.57 |
| openrouter:openai/gpt-5.4 | react_nogate | 1 | 0.60 (3/5) | nan | 0.01116 | nan | 1 | 1 | 1 | 1.31e+04 | 383.2 | 1.348e+04 | 0.0385 | 0.1925 | 0.60 (3/5) | 0.9667 | 1.00 (5/5) | 0.00 (0/5) | 0.00 (0/3) | 0.40 (2/5) | 0.00 (0/5) | 0.40 (2/5) | 4.4 | 3.4 | 8.985 |

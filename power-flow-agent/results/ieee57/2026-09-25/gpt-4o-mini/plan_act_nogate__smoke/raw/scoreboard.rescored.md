# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case57'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 3, 'difficulties': ['parameterized', 'multistep', 'ambiguous']}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | plan_act_nogate | 0.6667 | 0.67 (2/3) | 2.252e-07 | 0.05413 | 0.3197 | 1 | 1 | 1 | 1.5e+04 | 2902 | 1.79e+04 | 0.003991 | 0.01197 | 1.00 (3/3) | 1 | n/a | n/a | 0.33 (1/3) | 0.00 (0/3) | 0.00 (0/3) | 0.00 (0/3) | 2 | 3 | 252.3 |

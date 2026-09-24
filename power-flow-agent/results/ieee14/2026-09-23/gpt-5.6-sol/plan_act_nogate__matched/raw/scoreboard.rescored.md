# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.6-sol | plan_act_nogate | 1 | 1.00 (40/40) | 0 | 0 | 0 | 1 | 1 | 1 | 6052 | 401.5 | 6453 | 0.01612 | 0.6447 | 1.00 (40/40) | 1 | n/a | n/a | 0.00 (0/40) | 0.07 (1/15) | 0.00 (0/15) | 0.07 (1/15) | 2 | 2.85 | 10.13 |

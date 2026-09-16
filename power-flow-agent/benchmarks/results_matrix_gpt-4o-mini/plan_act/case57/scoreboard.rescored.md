# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case57'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | plan_act | 0.95 | 0.42 (17/40) | 0.0003964 | 0.1113 | 0.005783 | 1 | 1 | 1 | 1.567e+04 | 244.1 | 1.592e+04 | 0.002498 | 0.09491 | 0.42 (17/40) | 0.9881 | 0.00 (0/2) | 0.00 (0/2) | 0.00 (0/38) | 0.00 (0/24) | 0.00 (0/24) | 0.00 (0/24) | 1.9 | 2.6 | 5.324 |

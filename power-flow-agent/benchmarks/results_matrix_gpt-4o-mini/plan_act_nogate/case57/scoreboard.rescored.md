# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case57'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | plan_act_nogate | 0.95 | 0.42 (17/40) | 0.0003964 | 0.1113 | 0.005783 | 1 | 1 | 1 | 1.567e+04 | 238.8 | 1.591e+04 | 0.002494 | 0.09478 | 0.42 (17/40) | 0.9925 | 0.00 (0/2) | 0.00 (0/2) | 0.00 (0/38) | 0.04 (1/24) | 0.00 (0/24) | 0.04 (1/24) | 1.9 | 2.6 | 4.871 |

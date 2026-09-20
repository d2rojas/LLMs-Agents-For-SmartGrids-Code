# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | plan_act_nogate | 1 | 0.28 (11/40) | 0.0004362 | 0.07463 | 0.001978 | 0.9956 | 1 | 1 | 5527 | 210.8 | 5738 | 0.0009555 | 0.03822 | 0.47 (19/40) | 0.9845 | n/a | n/a | 0.03 (1/40) | 0.04 (1/26) | 0.00 (0/26) | 0.04 (1/26) | 2 | 2.775 | 4.187 |

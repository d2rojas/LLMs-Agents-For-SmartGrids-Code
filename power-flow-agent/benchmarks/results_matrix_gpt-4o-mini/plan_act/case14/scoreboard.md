# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | plan_act | 1 | 0.0004362 | 0.07463 | 0.001978 | 0.9956 | 1 | 1 | 5527 | 209.2 | 5736 | 0.0009546 | 0.03818 | 0.35 (14/40) | 0.9845 | n/a | n/a | 0.08 (2/26) | 0.00 (0/26) | 0.08 (2/26) | 2 | 2.775 | 4.701 |

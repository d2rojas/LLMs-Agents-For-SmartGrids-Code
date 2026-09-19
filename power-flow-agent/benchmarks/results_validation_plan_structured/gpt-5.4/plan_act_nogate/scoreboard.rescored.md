# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | plan_act_nogate | 1 | 0.33 (13/40) | 0.001398 | 1.965 | 0.03201 | 0.9623 | 1 | 1 | 2429 | 266.6 | 2695 | 0.01007 | 0.4028 | 0.33 (13/40) | 1 | n/a | n/a | 0.00 (0/40) | 0.00 (0/7) | 0.00 (0/7) | 0.00 (0/7) | 2 | 1.55 | 5.863 |

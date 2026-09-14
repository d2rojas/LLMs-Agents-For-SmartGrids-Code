# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case57'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': ['stress']}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none:rule_based | rule_based | 0.5 | 0.00 (0/40) | nan | 0.05264 | nan | 1 | 1 | 0.8 | 0 | 0 | 0 | 0 | 0 | 0.40 (16/40) | 1 | 0.50 (20/40) | 0.50 (20/40) | 0.00 (0/16) | 0.05 (1/20) | 0.00 (0/20) | 0.05 (1/20) | 0 | 1.45 | 0.1362 |
| openrouter:openai/gpt-4o-mini | pfagent | 1 | 0.60 (24/40) | nan | 0.05264 | nan | 1 | 1 | 1 | 1.542e+04 | 220.1 | 1.564e+04 | 0.002445 | 0.09781 | 1.00 (40/40) | 1 | 0.60 (24/40) | 0.40 (16/40) | 0.00 (0/16) | 0.17 (7/40) | 0.00 (0/40) | 0.17 (7/40) | 2.35 | 2.825 | 3.878 |
| openrouter:openai/gpt-4o-mini | react_nogate | 1 | 0.60 (24/40) | nan | 0.05264 | nan | 1 | 1 | 1 | 1.632e+04 | 225.3 | 1.654e+04 | 0.002583 | 0.1033 | 0.97 (39/40) | 1 | 0.60 (24/40) | 0.40 (16/40) | 0.00 (0/16) | 0.12 (5/40) | 0.00 (0/40) | 0.12 (5/40) | 2.425 | 2.875 | 4.185 |
| openrouter:openai/gpt-4o-mini | single_call:structured | 1 | 0.60 (24/40) | nan | 0.05264 | nan | 1 | 1 | 1 | 2.798e+04 | 189.3 | 2.817e+04 | 0.004311 | 0.1725 | 1.00 (40/40) | 0.9673 | 0.60 (24/40) | 0.40 (16/40) | 0.00 (0/16) | 0.03 (1/40) | 0.00 (0/40) | 0.03 (1/40) | 2 | 2.5 | 3.84 |

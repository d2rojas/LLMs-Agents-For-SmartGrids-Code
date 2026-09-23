# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': ['stress']}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | 1 | 1.00 (40/40) | nan | 0 | nan | 1 | 1 | 1 | 2.051e+04 | 392.4 | 2.091e+04 | 0.003312 | 0.1325 | 1.00 (40/40) | 1 | 1.00 (40/40) | 0.00 (0/40) | n/a | 0.00 (0/40) | 0.00 (0/40) | 0.00 (0/40) | 4.35 | 4.55 | 6.544 |

# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | react_nogate | 1 | 0.88 (35/40) | 1.897e-07 | 0.01516 | 0.000442 | 1 | 1 | 1 | 7414 | 206 | 7620 | 0.001236 | 0.04943 | 0.88 (35/40) | 0.9824 | n/a | n/a | 0.00 (0/40) | 0.04 (1/26) | 0.00 (0/26) | 0.04 (1/26) | 2.775 | 2.325 | 4.169 |

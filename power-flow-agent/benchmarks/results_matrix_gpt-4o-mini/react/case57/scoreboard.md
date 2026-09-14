# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case57'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | react | 0.95 | 0 | 0.05223 | 0.004884 | 1 | 1 | 1 | 1.852e+04 | 251.9 | 1.877e+04 | 0.002929 | 0.1113 | 0.89 (34/38) | 0.9716 | n/a | n/a | 0.00 (0/24) | 0.00 (0/24) | 0.00 (0/24) | 2.7 | 2.175 | 5.062 |

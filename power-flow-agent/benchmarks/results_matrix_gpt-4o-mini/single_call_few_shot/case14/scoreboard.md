# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | single_call:few_shot | 1 | 1.466e-05 | 0.04577 | 0.0008065 | 1 | 1 | 1 | 9833 | 184 | 1.002e+04 | 0.001585 | 0.06342 | 0.75 (30/40) | 0.9854 | n/a | n/a | 0.00 (0/26) | 0.00 (0/26) | 0.00 (0/26) | 2 | 1.95 | 3.405 |

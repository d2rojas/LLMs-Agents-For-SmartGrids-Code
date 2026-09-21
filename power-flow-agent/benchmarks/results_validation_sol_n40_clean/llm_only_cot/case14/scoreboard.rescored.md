# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.6-sol | llm_only:cot | 1 | 0.35 (14/40) | 0.001461 | 0.5349 | 0.4946 | 0.7471 | 1 | 0.8 | 2196 | 7856 | 1.005e+04 | 0.08295 | 3.318 | n/a | 0.02007 | n/a | n/a | 0.03 (1/40) | n/a | n/a | n/a | 1 | 0 | 184.2 |

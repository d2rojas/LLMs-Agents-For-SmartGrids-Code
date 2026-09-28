# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case300'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 20, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:cot | 0.85 | 0.00 (0/20) | 0.03612 | 96.47 | 38.74 | 0.0162 | 0.5385 | 1 | 2.57e+04 | 4020 | 2.972e+04 | 0.006268 | 0.1254 | 1.00 (17/17) | 0.07969 | n/a | n/a | 0.00 (0/20) | n/a | n/a | n/a | 1 | 0 | 101.5 |

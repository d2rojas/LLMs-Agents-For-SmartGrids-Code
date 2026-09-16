# LLM Power-Flow Benchmark

k=3, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 5, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | llm_only_forced:structured | 1 | 0.00 (0/5) | 0.005898 | 6.539 | 0.495 | 0.8862 | 1 | 1 | 2042 | 771.8 | 2814 | 0.01668 | 0.08341 | n/a | 0 | n/a | n/a | 0.00 (0/5) | n/a | n/a | n/a | 1 | 0 | 7.363 |

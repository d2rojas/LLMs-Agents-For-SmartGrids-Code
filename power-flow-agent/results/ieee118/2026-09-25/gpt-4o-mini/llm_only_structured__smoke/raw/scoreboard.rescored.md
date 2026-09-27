# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case118'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 3, 'difficulties': ['parameterized', 'multistep', 'ambiguous']}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:structured | 1 | 0.00 (0/3) | 0.02325 | 55.2 | 43.56 | 0 | 0 | 1 | 1.404e+04 | 5520 | 1.956e+04 | 0.005418 | 0.01625 | 1.00 (3/3) | 0.06857 | n/a | n/a | 0.00 (0/3) | n/a | n/a | n/a | 1 | 0 | 102.9 |

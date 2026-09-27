# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case118'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 3, 'difficulties': ['parameterized', 'multistep', 'ambiguous']}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | react_nogate | 0.6667 | 0.67 (2/3) | 1.341e-07 | 1.372 | 0.02027 | 0.8571 | 1 | 1 | 6.357e+04 | 1.017e+04 | 7.374e+04 | 0.01564 | 0.04691 | 1.00 (3/3) | 1 | n/a | n/a | 0.33 (1/3) | 0.00 (0/3) | 0.00 (0/3) | 0.00 (0/3) | 3.333 | 2.667 | 324.3 |

# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case118'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 3, 'difficulties': ['parameterized', 'multistep', 'ambiguous']}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:cot | 1 | 0.00 (0/3) | 0.04027 | 102.9 | 62.89 | 0 | 0.3333 | 1 | 1.422e+04 | 1387 | 1.56e+04 | 0.002965 | 0.008895 | 1.00 (3/3) | 0.02142 | n/a | n/a | 0.00 (0/3) | n/a | n/a | n/a | 1 | 0 | 266.5 |

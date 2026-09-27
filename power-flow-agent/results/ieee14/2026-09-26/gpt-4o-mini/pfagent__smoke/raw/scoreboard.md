# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 3, 'difficulties': ['parameterized', 'multistep', 'ambiguous']}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | 0.6667 | 0.67 (2/3) | 1.922e-07 | 0.0002044 | 0.002643 | 1 | 1 | 1 | 1.256e+04 | 3604 | 1.617e+04 | 0.004046 | 0.008093 | 1.00 (2/2) | 1 | n/a | n/a | 0.00 (0/3) | 0.00 (0/2) | 0.00 (0/2) | 0.00 (0/2) | 3.333 | 2.333 | 39.38 |

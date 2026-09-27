# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case300'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 3, 'difficulties': ['parameterized', 'multistep', 'ambiguous']}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | 0.3333 | 0.00 (0/3) | 2.045e-07 | 0.0002552 | 0.00298 | 0.9865 | 1 | 1 | 3.116e+05 | 4.186e+04 | 3.535e+05 | 0.07185 | 0.2156 | 1.00 (1/1) | 1 | 1.00 (2/2) | 0.00 (0/2) | 0.67 (2/3) | 0.00 (0/3) | 0.00 (0/3) | 0.00 (0/3) | 7.667 | 4.667 | 537.2 |

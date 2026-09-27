# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case30'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 3, 'difficulties': ['parameterized', 'multistep', 'ambiguous']}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | 1 | 1.00 (3/3) | 2.151e-07 | 0.0002281 | 0.002764 | 1 | 1 | 1 | 1.74e+04 | 5816 | 2.322e+04 | 0.0061 | 0.0183 | 1.00 (3/3) | 1 | n/a | n/a | 0.00 (0/3) | 0.00 (0/3) | 0.00 (0/3) | 0.00 (0/3) | 3.333 | 2.333 | 64.99 |

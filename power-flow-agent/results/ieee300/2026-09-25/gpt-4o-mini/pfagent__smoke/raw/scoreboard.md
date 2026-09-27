# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case300'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 3, 'difficulties': ['parameterized', 'multistep', 'ambiguous']}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | 0 | 0.00 (0/3) | None | None | None | None | None | None | 1.353e+05 | 1.369e+04 | 1.49e+05 | 0.02851 | 0.08554 | n/a | None | 1.00 (3/3) | 0.00 (0/3) | 1.00 (3/3) | 0.00 (0/3) | 0.00 (0/3) | 0.00 (0/3) | 4.333 | 3 | 565 |

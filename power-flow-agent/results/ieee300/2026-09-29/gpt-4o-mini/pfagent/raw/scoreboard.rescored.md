# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case300'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 20, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | 0.6 | 0.15 (3/20) | 1.922e-07 | 0.0002453 | 0.002896 | 0.9966 | 1 | 1 | 2.005e+05 | 2.679e+04 | 2.273e+05 | 0.04615 | 0.923 | 1.00 (20/20) | 1 | n/a | n/a | 1.00 (20/20) | 0.00 (0/9) | 0.00 (0/9) | 0.00 (0/9) | 6.35 | 4.05 | 361.6 |

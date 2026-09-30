# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case57'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 20, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.6-sol | plan_act_nogate | 1 | 1.00 (20/20) | 2.243e-07 | 0.0525 | 0.2933 | 1 | 1 | 1 | 1.277e+04 | 4112 | 1.689e+04 | 0.06667 | 1.333 | 1.00 (20/20) | 0.9998 | n/a | n/a | 0.20 (4/20) | 0.00 (0/6) | 0.00 (0/6) | 0.00 (0/6) | 2 | 3.05 | 34.52 |

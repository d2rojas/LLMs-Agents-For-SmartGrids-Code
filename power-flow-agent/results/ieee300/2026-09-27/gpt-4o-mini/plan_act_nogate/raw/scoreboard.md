# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case300'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 20, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | plan_act_nogate | 1 | 0.75 (15/20) | 1.92e-07 | 0.0002492 | 0.002886 | 0.9928 | 1 | 1 | 2.792e+04 | 4789 | 3.271e+04 | 0.007061 | 0.1412 | 1.00 (20/20) | 0.98 | n/a | n/a | 0.25 (5/20) | 0.00 (0/9) | 0.00 (0/9) | 0.00 (0/9) | 2 | 3.1 | 46.4 |

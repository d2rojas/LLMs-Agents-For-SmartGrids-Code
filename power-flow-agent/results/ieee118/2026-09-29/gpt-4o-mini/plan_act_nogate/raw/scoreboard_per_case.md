# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | plan_act_nogate | case118 | 1 | 0.85 (17/20) | 1.329e-07 | 1.327 | 0.003583 | 0.8793 | 1 | 1 | 1.437e+04 | 5373 | 1.974e+04 | 0.00538 | 0.1076 | 1.00 (20/20) | 0.8839 | n/a | n/a | 0.00 (0/20) | 0.00 (0/9) | 0.00 (0/9) | 0.00 (0/9) | 2 | 3.15 | 53.39 |

# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | plan_act_nogate | case30 | 1 | 1.00 (3/3) | 2.151e-07 | 0.0002281 | 0.002764 | 1 | 1 | 1 | 3477 | 746 | 4223 | 0.0009691 | 0.002907 | 1.00 (3/3) | 1 | n/a | n/a | 0.00 (0/3) | 0.00 (0/3) | 0.00 (0/3) | 0.00 (0/3) | 2 | 3 | 7.165 |

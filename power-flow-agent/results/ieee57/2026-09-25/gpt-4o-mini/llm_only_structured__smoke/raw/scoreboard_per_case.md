# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:structured | case57 | 1 | 0.00 (0/3) | 0.104 | 24.9 | 76.94 | 0.6166 | 0 | 1 | 6663 | 3563 | 1.023e+04 | 0.003137 | 0.009411 | 1.00 (3/3) | 0.07602 | n/a | n/a | 0.00 (0/3) | n/a | n/a | n/a | 1 | 0 | 73 |

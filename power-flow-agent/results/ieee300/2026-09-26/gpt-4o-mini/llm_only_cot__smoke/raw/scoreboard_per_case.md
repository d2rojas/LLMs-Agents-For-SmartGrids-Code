# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:cot | case300 | 1 | 0.00 (0/3) | 0.02435 | 0 | 0 | 0 | 0.3333 | 1 | 2.568e+04 | 500.3 | 2.618e+04 | 0.004153 | 0.01246 | 1.00 (3/3) | 0.07018 | n/a | n/a | 0.00 (0/3) | n/a | n/a | n/a | 1 | 0 | 8.38 |

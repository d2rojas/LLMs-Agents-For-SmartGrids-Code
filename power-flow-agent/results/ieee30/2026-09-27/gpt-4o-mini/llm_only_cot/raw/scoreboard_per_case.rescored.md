# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:cot | case30 | 1 | 0.00 (0/20) | 0.03151 | 7.129 | 59.74 | 0.9375 | 0.1301 | 1 | 4283 | 2634 | 6918 | 0.002223 | 0.04446 | 0.90 (18/20) | 0.1348 | n/a | n/a | 0.00 (0/20) | n/a | n/a | n/a | 1 | 0 | 19.77 |

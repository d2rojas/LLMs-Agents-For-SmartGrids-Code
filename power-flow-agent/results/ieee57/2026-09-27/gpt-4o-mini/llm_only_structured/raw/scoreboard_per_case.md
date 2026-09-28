# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:structured | case57 | 1 | 0.00 (0/20) | 0.1287 | 61.34 | 127.2 | 0.5457 | 0.1453 | 0.95 | 6682 | 2799 | 9481 | 0.002682 | 0.05363 | 1.00 (20/20) | 0.06035 | n/a | n/a | 0.05 (1/20) | n/a | n/a | n/a | 1 | 0 | 27.08 |

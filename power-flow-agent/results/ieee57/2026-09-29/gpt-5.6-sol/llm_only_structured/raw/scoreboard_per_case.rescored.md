# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.6-sol | llm_only:structured | case57 | 1 | 0.00 (0/20) | None | None | None | 0 | 0.15 | 0 | 6681 | 432.1 | 7114 | 0.01768 | 0.3537 | 1.00 (20/20) | 0.1294 | n/a | n/a | 1.00 (20/20) | n/a | n/a | n/a | 1 | 0 | 6.963 |

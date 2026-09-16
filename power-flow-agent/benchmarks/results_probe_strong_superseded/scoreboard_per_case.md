# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o | llm_only:structured | case14 | 1 | None | None | None | 0 | 1 | 0 | 2422 | 65.33 | 2487 | 0.006708 | 0.02013 | n/a | 0 | 0.00 (0/3) | 1.00 (3/3) | n/a | n/a | n/a | 1 | 0 | 2.264 |

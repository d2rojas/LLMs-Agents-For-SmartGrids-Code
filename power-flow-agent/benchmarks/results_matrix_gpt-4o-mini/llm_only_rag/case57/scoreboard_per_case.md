# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:rag | case57 | 0.95 | None | None | None | 0 | 1 | 0 | 794.5 | 61.5 | 856 | 0.0001561 | 0.005931 | n/a | 0.05263 | 0.00 (0/38) | 1.00 (38/38) | n/a | n/a | n/a | 0.95 | 0 | 1.858 |

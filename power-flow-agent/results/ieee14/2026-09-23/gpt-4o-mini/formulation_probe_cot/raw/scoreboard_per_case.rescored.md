# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | formulation_probe:cot | case14 | 0 | 0.00 (0/40) | None | None | None | None | None | None | 2416 | 292.1 | 2708 | 0.0005376 | 0.0215 | 0.70 (28/40) | 0.8947 | n/a | n/a | 0.00 (0/40) | n/a | n/a | n/a | 1 | 0 | 3.486 |

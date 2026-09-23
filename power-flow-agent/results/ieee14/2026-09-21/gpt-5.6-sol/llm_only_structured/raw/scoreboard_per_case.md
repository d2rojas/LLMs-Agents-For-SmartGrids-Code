# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.6-sol | llm_only:structured | case14 | 1 | 0.45 (18/40) | 0.001757 | 0.4983 | 0.4952 | 0.8703 | 1 | 0.925 | 2020 | 8344 | 1.036e+04 | 0.08748 | 3.499 | n/a | 0.02007 | n/a | n/a | 0.00 (0/40) | n/a | n/a | n/a | 1 | 0 | 148 |

# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | llm_only_forced:nr | case14 | 1 | 0.60 (24/40) | 0.005925 | 4.761 | 0.4944 | 0.8741 | 1 | 1 | 2408 | 1032 | 3440 | 0.0215 | 0.8601 | n/a | 0.0169 | n/a | n/a | 0.00 (0/40) | n/a | n/a | n/a | 1 | 0 | 7.914 |

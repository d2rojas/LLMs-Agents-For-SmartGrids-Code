# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | llm_only_forced:structured | case14 | 1 | 0.00 (0/5) | 0.006902 | 8.001 | 0.5019 | 0.8267 | 1 | 1 | 2042 | 773 | 2815 | 0.0167 | 0.0835 | n/a | 0 | n/a | n/a | 0.00 (0/5) | n/a | n/a | n/a | 1 | 0 | 7.466 |

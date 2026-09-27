# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:cot | case14 | 0.7 | 0.00 (0/20) | 0.02738 | 19.67 | 58.26 | 0.5169 | 0.4156 | 1 | 3277 | 1506 | 4783 | 0.001395 | 0.02791 | 1.00 (14/14) | 0.09171 | n/a | n/a | 0.00 (0/20) | n/a | n/a | n/a | 1 | 0 | 10.45 |

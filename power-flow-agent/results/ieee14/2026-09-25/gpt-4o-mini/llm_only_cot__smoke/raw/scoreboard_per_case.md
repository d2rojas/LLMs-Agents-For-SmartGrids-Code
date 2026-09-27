# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:cot | case14 | 0.6667 | 0.00 (0/3) | 0.02968 | 15.65 | 49.1 | 0.5 | 0 | 1 | 3256 | 1523 | 4779 | 0.001402 | 0.004206 | 1.00 (2/2) | 0.1343 | n/a | n/a | 0.00 (0/3) | n/a | n/a | n/a | 1 | 0 | 74 |

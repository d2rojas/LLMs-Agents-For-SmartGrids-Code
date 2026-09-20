# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | single_call:cot | case118 | 1 | 0.68 (27/40) | 3.258e-06 | 1.436 | 0.0001207 | 0.995 | 1 | 1 | 5.579e+04 | 224.9 | 5.601e+04 | 0.008503 | 0.3401 | 0.95 (38/40) | 1 | n/a | n/a | 0.00 (0/40) | 0.00 (0/26) | 0.00 (0/26) | 0.00 (0/26) | 2 | 2.05 | 6.044 |

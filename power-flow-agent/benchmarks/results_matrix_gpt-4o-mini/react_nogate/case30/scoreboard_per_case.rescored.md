# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | react_nogate | case30 | 1 | 0.82 (33/40) | 1.427e-06 | 0.01733 | 0.01969 | 1 | 1 | 1 | 9833 | 215.2 | 1.005e+04 | 0.001604 | 0.06416 | 0.97 (39/40) | 1 | n/a | n/a | 0.00 (0/40) | 0.08 (2/26) | 0.00 (0/26) | 0.08 (2/26) | 2.725 | 2.3 | 4.145 |

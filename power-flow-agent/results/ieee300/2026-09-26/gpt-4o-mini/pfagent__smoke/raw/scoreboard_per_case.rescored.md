# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | case300 | 0.3333 | 0.00 (0/3) | 2.045e-07 | 0.0002552 | 0.00298 | 0.9865 | 1 | 1 | 3.172e+05 | 3.721e+04 | 3.544e+05 | 0.0699 | 0.0699 | 0.33 (1/3) | 1 | n/a | n/a | 0.00 (0/3) | 0.00 (0/1) | 0.00 (0/1) | 0.00 (0/1) | 2.667 | 1.667 | 311.5 |

# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | single_call:structured | case57 | 0.95 | 0.80 (32/40) | 1.339e-05 | 0.1043 | 0.005649 | 1 | 1 | 1 | 2.916e+04 | 236.4 | 2.94e+04 | 0.004516 | 0.1716 | 0.80 (32/40) | 0.9823 | 0.00 (0/2) | 0.00 (0/2) | 0.13 (5/38) | 0.04 (1/24) | 0.00 (0/24) | 0.04 (1/24) | 1.9 | 1.925 | 6.013 |

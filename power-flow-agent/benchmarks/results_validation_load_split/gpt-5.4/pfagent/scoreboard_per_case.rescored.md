# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | pfagent | case14 | 1 | 0.85 (34/40) | 0 | 0 | 0 | 1 | 1 | 1 | 1.311e+04 | 361.9 | 1.348e+04 | 0.03821 | 1.529 | 1.00 (40/40) | 1 | n/a | n/a | 0.03 (1/40) | 0.00 (0/15) | 0.00 (0/15) | 0.00 (0/15) | 3.675 | 2.7 | 10.35 |

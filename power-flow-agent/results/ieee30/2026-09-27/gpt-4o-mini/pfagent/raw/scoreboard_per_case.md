# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | case30 | 1 | 0.90 (18/20) | 1.972e-07 | 0.0002357 | 0.002837 | 1 | 1 | 1 | 2.385e+04 | 5090 | 2.894e+04 | 0.006632 | 0.1326 | 1.00 (20/20) | 1 | n/a | n/a | 0.10 (2/20) | 0.00 (0/9) | 0.00 (0/9) | 0.00 (0/9) | 5.1 | 3.35 | 38.44 |

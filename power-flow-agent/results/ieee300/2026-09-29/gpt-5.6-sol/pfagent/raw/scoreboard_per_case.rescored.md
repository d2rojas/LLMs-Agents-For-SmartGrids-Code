# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.6-sol | pfagent | case300 | 1 | 1.00 (20/20) | 1.92e-07 | 0.0002492 | 0.002886 | 0.9928 | 1 | 1 | 1.144e+05 | 1.599e+04 | 1.304e+05 | 0.3887 | 7.775 | 1.00 (20/20) | 1 | n/a | n/a | 0.25 (5/20) | 0.00 (0/9) | 0.00 (0/9) | 0.00 (0/9) | 5.55 | 3.3 | 155.5 |

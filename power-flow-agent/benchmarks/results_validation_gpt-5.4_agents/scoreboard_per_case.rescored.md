# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | pfagent | case14 | 1 | 1.00 (5/5) | 0 | 0 | 0 | 1 | 1 | 1 | 9105 | 337.8 | 9443 | 0.02783 | 0.1391 | 1.00 (5/5) | 1 | n/a | n/a | 0.00 (0/5) | 0.00 (0/2) | 0.00 (0/2) | 0.00 (0/2) | 3.6 | 2.6 | 6.861 |
| openrouter:openai/gpt-5.4 | react_nogate | case14 | 1 | 1.00 (5/5) | 0 | 0 | 0 | 1 | 1 | 1 | 9105 | 327.6 | 9432 | 0.02768 | 0.1384 | 1.00 (5/5) | 1 | n/a | n/a | 0.00 (0/5) | 0.00 (0/2) | 0.00 (0/2) | 0.00 (0/2) | 3.6 | 2.6 | 7.573 |
| openrouter:openai/gpt-5.4 | single_call:structured | case14 | 1 | 0.00 (0/5) | 0.004332 | 1.575 | 0.02088 | 0.9385 | 1 | 1 | 4442 | 183.8 | 4626 | 0.01386 | 0.06931 | 0.20 (1/5) | 1 | n/a | n/a | 0.00 (0/5) | n/a | n/a | n/a | 2 | 1 | 4.458 |

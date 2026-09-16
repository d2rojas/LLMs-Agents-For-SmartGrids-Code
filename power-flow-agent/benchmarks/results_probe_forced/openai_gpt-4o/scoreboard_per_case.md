# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o | llm_only_forced:cot | case14 | 1 | 0.05 (1/20) | 0.02551 | 32.02 | 54.54 | 0.4473 | 1 | 1 | 2621 | 1338 | 3959 | 0.01993 | 0.3987 | n/a | 0.04629 | n/a | n/a | 0.00 (0/20) | n/a | n/a | n/a | 1 | 0 | 10.37 |
| openrouter:openai/gpt-4o | llm_only_forced:cot | case30 | 1 | 0.00 (0/20) | 0.01379 | 16.08 | 67.9 | 0.9474 | 0 | 1 | 3925 | 2354 | 6280 | 0.03335 | 0.6671 | n/a | 0.04564 | n/a | n/a | 0.00 (0/20) | n/a | n/a | n/a | 1 | 0 | 15.71 |
| openrouter:openai/gpt-4o | llm_only_forced:structured | case14 | 1 | 0.00 (0/20) | 0.03564 | 29.35 | 38.3 | 0.4037 | 1 | 1 | 2445 | 1012 | 3457 | 0.01623 | 0.3247 | n/a | 0.03521 | n/a | n/a | 0.00 (0/20) | n/a | n/a | n/a | 1 | 0 | 6.99 |
| openrouter:openai/gpt-4o | llm_only_forced:structured | case30 | 1 | 0.00 (0/20) | 0.01418 | 22.26 | 75.47 | 0.9474 | 0.005882 | 1 | 3749 | 2027 | 5776 | 0.02964 | 0.5929 | n/a | 0.05621 | n/a | n/a | 0.00 (0/20) | n/a | n/a | n/a | 1 | 0 | 13.04 |

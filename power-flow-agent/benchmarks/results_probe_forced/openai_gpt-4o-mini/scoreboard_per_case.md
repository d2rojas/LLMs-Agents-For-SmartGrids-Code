# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only_forced:cot | case14 | 0.75 | 0.00 (0/20) | 0.3408 | 32.4 | 15.46 | 0.5343 | 1 | 1 | 2621 | 1229 | 3850 | 0.00113 | 0.02261 | n/a | 0.0462 | n/a | n/a | 0.05 (1/20) | n/a | n/a | n/a | 1 | 0 | 11.31 |
| openrouter:openai/gpt-4o-mini | llm_only_forced:cot | case30 | 1 | 0.00 (0/20) | 0.0232 | 20.46 | 49.3 | 0.9474 | 0.00303 | 1 | 3925 | 2252 | 6178 | 0.00194 | 0.0388 | n/a | 0.1248 | n/a | n/a | 0.00 (0/20) | n/a | n/a | n/a | 1 | 0 | 19.26 |
| openrouter:openai/gpt-4o-mini | llm_only_forced:structured | case14 | 0.85 | 0.00 (0/20) | 0.4538 | 31.87 | 10.53 | 0.6776 | 1 | 1 | 2445 | 879.8 | 3325 | 0.0008946 | 0.01789 | n/a | 0.0125 | n/a | n/a | 0.00 (0/20) | n/a | n/a | n/a | 1 | 0 | 8.744 |
| openrouter:openai/gpt-4o-mini | llm_only_forced:structured | case30 | 1 | 0.00 (0/20) | 0.02043 | 10.58 | 37.93 | 0.95 | 0 | 1 | 3749 | 2008 | 5758 | 0.001768 | 0.03535 | n/a | 0.1319 | n/a | n/a | 0.00 (0/20) | n/a | n/a | n/a | 1 | 0 | 19.83 |

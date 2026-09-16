# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | llm_only_forced:cot | case14 | 1 | 0.40 (2/5) | 0.02175 | 4.713 | 33.19 | 0.8605 | 1 | 1 | 2542 | 1154 | 3696 | 0.02367 | 0.1183 | n/a | 0.002817 | n/a | n/a | 0.00 (0/5) | n/a | n/a | n/a | 1 | 0 | 12.7 |
| openrouter:openai/gpt-5.4 | llm_only_forced:cot | case30 | 1 | 0.00 (0/5) | 0.01395 | 9.158 | 27.45 | 1 | 0 | 1 | 3767 | 2040 | 5807 | 0.04002 | 0.2001 | n/a | 0.04414 | n/a | n/a | 0.00 (0/5) | n/a | n/a | n/a | 1 | 0 | 14.3 |
| openrouter:openai/gpt-5.4 | llm_only_forced:structured | case14 | 1 | 0.40 (2/5) | 0.005986 | 4.582 | 30.75 | 0.8605 | 1 | 1 | 2366 | 820.6 | 3186 | 0.01822 | 0.09112 | n/a | 0.002817 | n/a | n/a | 0.00 (0/5) | n/a | n/a | n/a | 1 | 0 | 7.562 |
| openrouter:openai/gpt-5.4 | llm_only_forced:structured | case30 | 0.8 | 0.00 (0/5) | 0.01442 | 8.641 | 26.83 | 1 | 0 | 1 | 3591 | 1544 | 5135 | 0.03214 | 0.1607 | n/a | 0.03327 | n/a | n/a | 0.00 (0/5) | n/a | n/a | n/a | 1 | 0 | 11.36 |

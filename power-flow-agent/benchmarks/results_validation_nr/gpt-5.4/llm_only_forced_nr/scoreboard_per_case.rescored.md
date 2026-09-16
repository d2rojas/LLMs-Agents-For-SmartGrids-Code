# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | llm_only_forced:nr | case14 | 1 | 0.60 (3/5) | 0.01057 | 2.561 | 0.4901 | 0.8876 | 1 | 1 | 2404 | 1017 | 3421 | 0.02127 | 0.1063 | n/a | 0 | n/a | n/a | 0.00 (0/5) | n/a | n/a | n/a | 1 | 0 | 7.823 |

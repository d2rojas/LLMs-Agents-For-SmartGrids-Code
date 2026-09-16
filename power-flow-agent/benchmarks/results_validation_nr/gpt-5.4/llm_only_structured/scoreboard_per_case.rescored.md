# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | llm_only:structured | case14 | 1 | 0.20 (1/5) | 0.0006155 | 0.8829 | 0.4727 | 0.1882 | 1 | 0.2 | 2016 | 194.6 | 2210 | 0.007959 | 0.03979 | n/a | 0 | n/a | n/a | 0.40 (2/5) | n/a | n/a | n/a | 1 | 0 | 2.592 |

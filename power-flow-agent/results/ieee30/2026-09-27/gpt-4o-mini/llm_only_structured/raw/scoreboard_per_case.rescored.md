# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:structured | case30 | 1 | 0.00 (0/20) | 0.03567 | 7.753 | 64.83 | 0.9231 | 0.03175 | 1 | 4107 | 2522 | 6630 | 0.002129 | 0.04259 | 0.95 (19/20) | 0.1197 | n/a | n/a | 0.00 (0/20) | n/a | n/a | n/a | 1 | 0 | 22.11 |

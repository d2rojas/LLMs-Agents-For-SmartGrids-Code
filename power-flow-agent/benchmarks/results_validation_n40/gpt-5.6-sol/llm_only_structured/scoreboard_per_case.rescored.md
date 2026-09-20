# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.6-sol | llm_only:structured | case14 | 0.95 | 0.38 (15/40) | 0.001696 | 1.422 | 0.4943 | 0.8727 | 1 | 0.9211 | 1990 | 8280 | 1.027e+04 | 0.08678 | 3.471 | n/a | 0.02113 | n/a | n/a | 0.00 (0/40) | n/a | n/a | n/a | 1 | 0 | 165.8 |

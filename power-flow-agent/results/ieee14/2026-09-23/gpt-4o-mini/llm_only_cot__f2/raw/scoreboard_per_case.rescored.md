# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:cot | case14 | 0.925 | 0.00 (0/40) | 0.02785 | 34.57 | 0.5364 | 0.1052 | 1 | 0.1892 | 2824 | 615.5 | 3440 | 0.000793 | 0.03172 | 0.72 (29/40) | 0.1254 | n/a | n/a | 0.75 (30/40) | n/a | n/a | n/a | 1 | 0 | 8.144 |

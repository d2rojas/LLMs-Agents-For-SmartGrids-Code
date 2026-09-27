# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:cot | case118 | 1 | 0.00 (0/3) | 0.1333 | 452.9 | 445.7 | 0.02564 | 0.02881 | 1 | 1.422e+04 | 5152 | 1.937e+04 | 0.005223 | 0.01567 | 1.00 (3/3) | 0.005487 | n/a | n/a | 0.00 (0/3) | n/a | n/a | n/a | 1 | 0 | 41.22 |

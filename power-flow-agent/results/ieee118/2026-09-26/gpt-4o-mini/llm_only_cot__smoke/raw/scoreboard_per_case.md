# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:cot | case118 | 1 | 0.00 (0/3) | 0.02822 | 457.7 | 482.8 | 0 | 0.02778 | 1 | 1.422e+04 | 8318 | 2.253e+04 | 0.007123 | 0.02137 | 1.00 (3/3) | 0.07332 | n/a | n/a | 0.00 (0/3) | n/a | n/a | n/a | 1 | 0 | 70.79 |

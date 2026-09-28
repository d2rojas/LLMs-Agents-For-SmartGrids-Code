# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:cot | case57 | 1 | 0.00 (0/20) | 0.1302 | 28.24 | 116.5 | 0.547 | 0.1723 | 1 | 6858 | 3064 | 9922 | 0.002867 | 0.05734 | 1.00 (20/20) | 0.05592 | n/a | n/a | 0.00 (0/20) | n/a | n/a | n/a | 1 | 0 | 27.42 |

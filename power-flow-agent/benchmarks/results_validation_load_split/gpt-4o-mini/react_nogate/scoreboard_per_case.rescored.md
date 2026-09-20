# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | react_nogate | case14 | 1 | 0.68 (27/40) | 1.897e-07 | 0.01516 | 0.000442 | 1 | 1 | 1 | 7728 | 207.7 | 7935 | 0.001284 | 0.05135 | 0.97 (39/40) | 0.9856 | n/a | n/a | 0.00 (0/40) | 0.00 (0/15) | 0.00 (0/15) | 0.00 (0/15) | 2.6 | 2.325 | 7.53 |

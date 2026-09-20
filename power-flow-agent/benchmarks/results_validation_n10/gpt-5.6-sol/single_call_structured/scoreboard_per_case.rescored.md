# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.6-sol | single_call:structured | case14 | 1 | 0.00 (0/10) | 0.003346 | 2.597 | 0.03593 | 0.9207 | 1 | 1 | 4527 | 255.8 | 4783 | 0.01161 | 0.1161 | 0.10 (1/10) | 1 | n/a | n/a | 0.00 (0/10) | n/a | n/a | n/a | 2 | 1 | 9.207 |

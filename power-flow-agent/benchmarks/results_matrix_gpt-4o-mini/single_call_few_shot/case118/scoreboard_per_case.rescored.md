# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | single_call:few_shot | case118 | 1 | 0.68 (27/40) | 6.983e-06 | 1.436 | 0.0001207 | 0.9914 | 1 | 1 | 5.502e+04 | 222.8 | 5.524e+04 | 0.008386 | 0.3354 | 0.93 (37/40) | 1 | n/a | n/a | 0.00 (0/40) | 0.08 (2/26) | 0.00 (0/26) | 0.08 (2/26) | 2 | 2 | 6.316 |

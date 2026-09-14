# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:cot | case57 | 0.95 | 0.00 (0/40) | None | None | None | 0 | 1 | 0 | 7171 | 440 | 7611 | 0.00134 | 0.05091 | n/a | 0.1562 | 0.00 (0/2) | 0.00 (0/2) | 1.00 (38/38) | n/a | n/a | n/a | 0.95 | 0 | 3.611 |

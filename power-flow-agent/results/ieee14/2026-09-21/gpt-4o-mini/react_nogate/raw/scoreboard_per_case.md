# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | react_nogate | case14 | 1 | 0.72 (29/40) | 0 | 0 | 0 | 1 | 1 | 1 | 7213 | 210.1 | 7423 | None | None | 1.00 (40/40) | 0.9969 | n/a | n/a | 0.00 (0/40) | 0.00 (0/15) | 0.00 (0/15) | 0.00 (0/15) | 2.5 | 2.275 | 4.418 |

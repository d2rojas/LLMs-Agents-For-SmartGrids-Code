# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only_forced:structured | case14 | 0.925 | 0.00 (0/40) | 0.0286 | 34.87 | 0.5438 | 0.5577 | 1 | 1 | 2674 | 1080 | 3755 | 0.001049 | 0.04198 | 0.76 (28/37) | 0.08592 | n/a | n/a | 0.00 (0/40) | n/a | n/a | n/a | 1 | 0 | 11.43 |

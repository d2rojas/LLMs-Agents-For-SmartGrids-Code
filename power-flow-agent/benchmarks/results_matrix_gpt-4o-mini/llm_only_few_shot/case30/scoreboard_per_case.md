# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:few_shot | case30 | 1 | None | None | None | 0.975 | 0 | 0 | 4228 | 61.88 | 4290 | 0.0006713 | 0.02685 | n/a | 0.075 | 0.00 (0/40) | 1.00 (40/40) | n/a | n/a | n/a | 1 | 0 | 2.242 |

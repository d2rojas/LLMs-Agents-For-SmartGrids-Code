# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | llm_only:structured | case14 | 0.975 | 0.00 (0/40) | None | None | None | 0 | 1 | 0 | 2648 | 175.2 | 2824 | 0.0005024 | 0.0201 | 0.79 (31/39) | 0.1285 | n/a | n/a | 0.97 (39/40) | n/a | n/a | n/a | 1 | 0 | 3.131 |

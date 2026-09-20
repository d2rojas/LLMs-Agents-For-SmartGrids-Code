# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.6-sol | llm_only:structured | case14 | 1 | 0.10 (1/10) | 0.001675 | 0.4824 | 0.4805 | 0.7598 | 1 | 0.8 | 2019 | 8678 | 1.07e+04 | 0.09082 | 0.9082 | n/a | 0.001408 | n/a | n/a | 0.00 (0/10) | n/a | n/a | n/a | 1 | 0 | 175.3 |

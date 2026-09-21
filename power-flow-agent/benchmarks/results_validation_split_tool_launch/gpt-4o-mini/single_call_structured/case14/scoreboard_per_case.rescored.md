# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | single_call:structured | case14 | 1 | 0.65 (26/40) | 1.466e-05 | 0.04577 | 0.0008065 | 1 | 1 | 1 | 9944 | 187.3 | 1.013e+04 | None | None | 0.95 (38/40) | 0.9914 | n/a | n/a | 0.00 (0/40) | 0.00 (0/15) | 0.00 (0/15) | 0.00 (0/15) | 2 | 1.95 | 4.484 |

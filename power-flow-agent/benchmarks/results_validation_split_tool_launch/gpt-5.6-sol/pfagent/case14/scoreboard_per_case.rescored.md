# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.6-sol | pfagent | case14 | 1 | 0.90 (36/40) | 0 | 0 | 0 | 1 | 1 | 1 | 1.774e+04 | 472.6 | 1.821e+04 | None | None | 0.97 (39/40) | 1 | n/a | n/a | 0.10 (4/40) | 0.00 (0/16) | 0.00 (0/16) | 0.00 (0/16) | 4.075 | 3 | 13.57 |

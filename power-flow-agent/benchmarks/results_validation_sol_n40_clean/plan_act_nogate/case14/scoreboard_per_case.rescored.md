# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.6-sol | plan_act_nogate | case14 | 1 | 0.75 (30/40) | 2.121e-05 | 0.04634 | 0.0008298 | 1 | 1 | 1 | 5996 | 421.6 | 6417 | 0.01621 | 0.6483 | 0.78 (31/40) | 0.9964 | n/a | n/a | 0.00 (0/40) | 0.00 (0/26) | 0.00 (0/26) | 0.00 (0/26) | 2 | 2.9 | 11.92 |

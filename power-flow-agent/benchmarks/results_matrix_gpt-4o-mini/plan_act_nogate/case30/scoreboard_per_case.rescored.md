# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | plan_act_nogate | case30 | 1 | 0.33 (13/40) | 0.0002648 | 0.052 | 0.7164 | 1 | 0.975 | 1 | 7710 | 205.9 | 7916 | 0.00128 | 0.0512 | 0.33 (13/40) | 1 | n/a | n/a | 0.03 (1/40) | 0.08 (2/25) | 0.00 (0/25) | 0.08 (2/25) | 2 | 2.775 | 4.261 |

# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | plan_act_nogate | case14 | 1 | 0.0004362 | 0.07463 | 0.001978 | 0.9956 | 1 | 1 | 5527 | 210.8 | 5738 | 0.0009555 | 0.03822 | 0.35 (14/40) | 0.9845 | n/a | n/a | 0.04 (1/26) | 0.00 (0/26) | 0.04 (1/26) | 2 | 2.775 | 4.187 |

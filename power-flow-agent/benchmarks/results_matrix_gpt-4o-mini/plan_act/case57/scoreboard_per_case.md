# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | plan_act | case57 | 0.95 | 0.0003964 | 0.1113 | 0.005783 | 1 | 1 | 1 | 1.567e+04 | 244.1 | 1.592e+04 | 0.002498 | 0.09491 | 0.34 (13/38) | 0.9881 | n/a | n/a | 0.00 (0/24) | 0.00 (0/24) | 0.00 (0/24) | 1.9 | 2.6 | 5.324 |

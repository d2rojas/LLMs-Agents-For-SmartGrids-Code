# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | plan_act_nogate | case14 | 1 | 0.57 (23/40) | 1.897e-07 | 0.01516 | 0.000442 | 1 | 1 | 1 | 5802 | 198.1 | 6000 | 0.0009891 | 0.03956 | 0.88 (35/40) | 0.9857 | n/a | n/a | 0.00 (0/40) | 0.00 (0/15) | 0.00 (0/15) | 0.00 (0/15) | 2 | 2.775 | 8.422 |

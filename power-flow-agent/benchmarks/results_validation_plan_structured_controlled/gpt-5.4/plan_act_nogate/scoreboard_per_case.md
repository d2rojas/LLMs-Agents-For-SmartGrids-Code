# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | plan_act_nogate | case14 | 1 | 0.30 (12/40) | 0.001626 | 1.954 | 0.03211 | 0.9628 | 1 | 1 | 2902 | 282.8 | 3185 | None | None | 0.30 (12/40) | 0.9904 | n/a | n/a | 0.00 (0/40) | 0.00 (0/11) | 0.00 (0/11) | 0.00 (0/11) | 2 | 1.725 | 4.459 |

# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | plan_act_gate | case14 | 1 | 0.65 (13/20) | 1.615e-07 | 0.0002393 | 0.002891 | 1 | 1 | 1 | 1.046e+04 | 2021 | 1.248e+04 | 0.002781 | 0.05562 | 1.00 (20/20) | 1 | n/a | n/a | 0.35 (7/20) | 0.00 (0/9) | 0.00 (0/9) | 0.00 (0/9) | 2.7 | 3.65 | 26.85 |

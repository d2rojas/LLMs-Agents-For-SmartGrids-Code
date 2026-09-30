# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | plan_act_gate_notools | case14 | 1 | 0.80 (16/20) | 1.615e-07 | 0.0002393 | 0.002891 | 1 | 1 | 1 | 7879 | 1824 | 9704 | 0.002277 | 0.04553 | 1.00 (20/20) | 0.8824 | n/a | n/a | 0.20 (4/20) | 0.00 (0/9) | 0.00 (0/9) | 0.00 (0/9) | 2.5 | 3.25 | 18.48 |

# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | case30 | 1 | 1.00 (40/40) | 0 | 0 | 0 | 0.95 | 0.6 | 0.6 | 1.301e+04 | 229.4 | 1.324e+04 | 0.002089 | 0.08358 | 1.00 (40/40) | 1 | 1.00 (39/39) | 0.00 (0/39) | 0.94 (16/17) | 0.25 (10/40) | 0.00 (0/40) | 0.25 (10/40) | 2.6 | 3.825 | 4.062 |

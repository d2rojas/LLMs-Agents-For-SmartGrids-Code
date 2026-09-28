# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | case300 | 0.85 | 0.15 (3/20) | 1.919e-07 | 0.0002473 | 0.002888 | 0.9932 | 1 | 1 | 2.047e+05 | 2.641e+04 | 2.311e+05 | 0.04656 | 0.9311 | 1.00 (20/20) | 1 | n/a | n/a | 1.00 (20/20) | 0.00 (0/9) | 0.00 (0/9) | 0.00 (0/9) | 6.15 | 4 | 318.3 |

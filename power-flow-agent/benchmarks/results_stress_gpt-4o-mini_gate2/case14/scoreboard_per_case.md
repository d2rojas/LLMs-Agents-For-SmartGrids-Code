# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | case14 | 1 | 0.60 (24/40) | nan | 0 | nan | 1 | 1 | 1 | 7216 | 223.9 | 7440 | 0.001217 | 0.04867 | 1.00 (40/40) | 1 | 0.60 (24/40) | 0.40 (16/40) | 0.00 (0/16) | 0.15 (6/40) | 0.00 (0/40) | 0.15 (6/40) | 2.4 | 3.575 | 3.808 |

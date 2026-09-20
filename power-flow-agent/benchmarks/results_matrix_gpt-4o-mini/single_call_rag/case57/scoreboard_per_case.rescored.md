# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | single_call:rag | case57 | 0.95 | 0.62 (25/40) | 1.339e-05 | 0.1043 | 0.005649 | 1 | 1 | 1 | 1.965e+04 | 212.7 | 1.987e+04 | 0.003076 | 0.1169 | 0.90 (36/40) | 0.9949 | 0.00 (0/2) | 0.00 (0/2) | 0.13 (5/38) | 0.00 (0/24) | 0.00 (0/24) | 0.00 (0/24) | 1.9 | 1.675 | 5.138 |

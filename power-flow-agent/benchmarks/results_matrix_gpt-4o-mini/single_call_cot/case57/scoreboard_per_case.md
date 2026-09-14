# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | single_call:cot | case57 | 0.95 | 1.339e-05 | 0.1043 | 0.005649 | 1 | 1 | 1 | 2.932e+04 | 663.2 | 2.998e+04 | 0.004795 | 0.1822 | 0.84 (32/38) | 0.9673 | n/a | n/a | 0.12 (3/24) | 0.00 (0/24) | 0.12 (3/24) | 1.9 | 1.925 | 7.647 |

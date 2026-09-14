# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | single_call:structured | case14 | 1 | 0.85 (34/40) | 1.466e-05 | 0.04577 | 0.0008065 | 1 | 1 | 1 | 9987 | 187.5 | 1.017e+04 | 0.001611 | 0.06443 | 0.85 (34/40) | 0.9914 | n/a | n/a | 0.00 (0/40) | 0.04 (1/26) | 0.00 (0/26) | 0.04 (1/26) | 2 | 2.05 | 4.034 |

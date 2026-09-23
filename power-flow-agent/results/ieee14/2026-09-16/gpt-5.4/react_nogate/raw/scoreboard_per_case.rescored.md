# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | react_nogate | case14 | 1 | 0.60 (24/40) | 0.0001129 | 0.007444 | 0.0003393 | 0.9985 | 1 | 1 | 1.112e+04 | 350.1 | 1.147e+04 | 0.03305 | 1.322 | 0.62 (25/40) | 0.9897 | n/a | n/a | 0.00 (0/40) | 0.04 (1/26) | 0.00 (0/26) | 0.04 (1/26) | 3.725 | 2.825 | 6.487 |

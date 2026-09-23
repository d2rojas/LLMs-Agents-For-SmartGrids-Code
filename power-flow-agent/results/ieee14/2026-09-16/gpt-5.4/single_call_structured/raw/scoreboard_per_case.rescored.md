# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | single_call:structured | case14 | 1 | 0.10 (4/40) | 0.001769 | 2.747 | 0.04306 | 0.9487 | 1 | 1 | 4449 | 187.6 | 4637 | 0.01394 | 0.5575 | 0.20 (8/40) | 0.965 | n/a | n/a | 0.00 (0/40) | n/a | n/a | n/a | 2 | 1 | 3.928 |

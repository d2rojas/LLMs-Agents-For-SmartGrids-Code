# LLM Power-Flow Benchmark (Per Case)

| model | task | case_name | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.6-sol | single_call:structured | case14 | 1 | 0.12 (5/40) | 0.001769 | 2.747 | 0.04306 | 0.9487 | 1 | 1 | 4658 | 272.2 | 4930 | None | None | 0.20 (8/40) | 0.9867 | n/a | n/a | 0.00 (0/40) | n/a | n/a | n/a | 2 | 1 | 7.761 |

# LLM Power-Flow Benchmark

k=0, seeds=[0], cases=['case14'], max_rounds=8, requests=None

| model | task | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | baseline_pf | 1 | None | None | None | 0 | 1 | 0 | 2366 | 61.67 | 2428 | 0.0003919 | 0.001176 | n/a | 0 | 0.00 (0/3) | 1.00 (3/3) | n/a | n/a | n/a | 1 | 0 | 1.922 |

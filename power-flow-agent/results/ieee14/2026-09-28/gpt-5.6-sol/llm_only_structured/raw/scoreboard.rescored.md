# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 20, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.6-sol | llm_only:structured | 1 | 0.20 (4/20) | 0.0009825 | 0.3224 | 2.412 | 0.3399 | 0.65 | 0.35 | 3100 | 6073 | 9173 | 0.06693 | 1.339 | 1.00 (20/20) | 0.08157 | n/a | n/a | 0.65 (13/20) | n/a | n/a | n/a | 1 | 0 | 88.3 |

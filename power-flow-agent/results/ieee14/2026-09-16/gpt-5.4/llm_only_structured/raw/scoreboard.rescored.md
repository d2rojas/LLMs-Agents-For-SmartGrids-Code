# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | llm_only:structured | 1 | 0.17 (7/40) | 0.002046 | 3.389 | 0.4889 | 0.6358 | 1 | 0.7 | 2020 | 558.7 | 2578 | 0.01343 | 0.5372 | n/a | 0.0162 | n/a | n/a | 0.12 (5/40) | n/a | n/a | n/a | 1 | 0 | 6.02 |

# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | llm_only_forced:structured | 1 | 0.65 (26/40) | 0.00274 | 5.448 | 0.4944 | 0.9103 | 1 | 1 | 2046 | 771.4 | 2817 | 0.01668 | 0.6674 | n/a | 0.0162 | n/a | n/a | 0.00 (0/40) | n/a | n/a | n/a | 1 | 0 | 7.305 |

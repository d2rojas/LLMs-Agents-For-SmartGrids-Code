# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | react_nogate | 1 | 0.90 (36/40) | 0 | 0 | 0 | 1 | 1 | 1 | 1.115e+04 | 311.9 | 1.146e+04 | 0.03255 | 1.302 | 1.00 (40/40) | 0.9894 | n/a | n/a | 0.00 (0/40) | 0.07 (1/15) | 0.00 (0/15) | 0.07 (1/15) | 3.575 | 2.65 | 7.894 |

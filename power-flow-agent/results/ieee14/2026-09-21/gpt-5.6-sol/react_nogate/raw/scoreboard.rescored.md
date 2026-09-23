# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.6-sol | react_nogate | 1 | 0.97 (39/40) | 0 | 0 | 0 | 1 | 1 | 1 | 1.3e+04 | 389.5 | 1.338e+04 | None | None | 0.97 (39/40) | 1 | n/a | n/a | 0.00 (0/40) | 0.06 (1/16) | 0.00 (0/16) | 0.06 (1/16) | 3.75 | 2.75 | 11.49 |

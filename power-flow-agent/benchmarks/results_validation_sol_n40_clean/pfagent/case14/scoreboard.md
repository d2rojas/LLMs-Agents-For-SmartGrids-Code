# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.6-sol | pfagent | 1 | 0.62 (25/40) | 0.0001231 | 0.009145 | 0.0004535 | 0.9964 | 1 | 1 | 1.687e+04 | 581.3 | 1.745e+04 | 0.03955 | 1.582 | 0.62 (25/40) | 1 | n/a | n/a | 0.03 (1/40) | 0.00 (0/26) | 0.00 (0/26) | 0.00 (0/26) | 4.45 | 3.325 | 40.67 |

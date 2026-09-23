# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | single_call:cot | 1 | 0.65 (26/40) | 1.466e-05 | 0.04577 | 0.0008065 | 1 | 1 | 1 | 1.043e+04 | 192 | 1.063e+04 | 0.00168 | 0.06721 | 0.95 (38/40) | 0.9875 | n/a | n/a | 0.00 (0/40) | 0.00 (0/15) | 0.00 (0/15) | 0.00 (0/15) | 2 | 2.075 | 5.452 |

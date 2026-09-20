# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 5, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | single_call:cot | 1 | 0.00 (0/5) | 0.004332 | 1.575 | 0.02088 | 0.9385 | 1 | 1 | 4730 | 319.4 | 5049 | 0.01662 | 0.08308 | 0.20 (1/5) | 1 | n/a | n/a | 0.00 (0/5) | n/a | n/a | n/a | 2 | 1 | 6.907 |
| openrouter:openai/gpt-5.4 | single_call:few_shot | 1 | 0.00 (0/5) | 0.004332 | 1.575 | 0.02088 | 0.9385 | 1 | 1 | 4806 | 191 | 4997 | 0.01488 | 0.0744 | 0.20 (1/5) | 1 | n/a | n/a | 0.00 (0/5) | n/a | n/a | n/a | 2 | 1 | 5.864 |
| openrouter:openai/gpt-5.4 | single_call:rag | 1 | 0.00 (0/5) | 0.004332 | 1.575 | 0.02088 | 0.9385 | 1 | 1 | 2453 | 176.6 | 2630 | 0.008782 | 0.04391 | 0.20 (1/5) | 1 | n/a | n/a | 0.00 (0/5) | n/a | n/a | n/a | 2 | 1 | 5.398 |

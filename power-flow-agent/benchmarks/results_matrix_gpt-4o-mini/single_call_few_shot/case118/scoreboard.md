# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case118'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | single_call:few_shot | 1 | 6.983e-06 | 1.436 | 0.0001207 | 0.9914 | 1 | 1 | 5.502e+04 | 222.8 | 5.524e+04 | 0.008386 | 0.3354 | 0.82 (33/40) | 0.9875 | n/a | n/a | 0.08 (2/26) | 0.00 (0/26) | 0.08 (2/26) | 2 | 2 | 6.316 |

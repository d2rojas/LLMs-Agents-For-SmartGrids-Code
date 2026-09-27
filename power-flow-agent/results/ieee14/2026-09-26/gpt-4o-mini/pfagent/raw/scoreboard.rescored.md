# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 20, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | 1 | 0.95 (19/20) | 1.615e-07 | 0.0002393 | 0.002891 | 1 | 1 | 1 | 2.443e+04 | 4056 | 2.849e+04 | 0.006098 | 0.122 | 1.00 (20/20) | 1 | n/a | n/a | 0.10 (2/20) | 0.00 (0/9) | 0.00 (0/9) | 0.00 (0/9) | 5.65 | 3.65 | 30.95 |

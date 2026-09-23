# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | pfagent | 1 | 0.60 (24/40) | 0.0003168 | 0.05676 | 0.001378 | 0.9971 | 1 | 1 | 1.381e+04 | 386 | 1.419e+04 | 0.04031 | 1.613 | 0.62 (25/40) | 1 | n/a | n/a | 0.03 (1/40) | 0.00 (0/25) | 0.00 (0/25) | 0.00 (0/25) | 3.9 | 2.825 | 7.375 |

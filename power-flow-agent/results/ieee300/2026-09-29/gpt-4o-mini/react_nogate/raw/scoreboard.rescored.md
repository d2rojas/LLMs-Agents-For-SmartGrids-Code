# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case300'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 20, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | react_nogate | 1 | 0.65 (13/20) | 0.0001709 | 0.4433 | 0.6952 | 0.9926 | 0.9814 | 1 | 7.342e+04 | 1.488e+04 | 8.83e+04 | 0.01994 | 0.3988 | 0.95 (19/20) | 0.9684 | n/a | n/a | 0.30 (6/20) | 0.00 (0/9) | 0.00 (0/9) | 0.00 (0/9) | 4.35 | 3.15 | 136.3 |

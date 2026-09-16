# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'merged: stress s0 (n=5) + stress s1 (n=5), 5 islanded + 5 non_converged per method'}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | pfagent | 1 | 0.10 (1/10) | nan | 0.006693 | nan | 1 | 1 | 1 | 2.379e+04 | 627.6 | 2.442e+04 | 0.0689 | 0.689 | 0.50 (5/10) | None | 1.00 (5/5) | 0.00 (0/5) | 1.00 (5/5) | 0.00 (0/10) | 0.00 (0/10) | 0.00 (0/10) | 5.7 | 3.9 | 12.69 |
| openrouter:openai/gpt-5.4 | react_nogate | 1 | 0.10 (1/10) | nan | 0.006693 | nan | 1 | 1 | 1 | 1.595e+04 | 384.2 | 1.633e+04 | 0.04563 | 0.4563 | 0.50 (5/10) | 0.9656 | 1.00 (5/5) | 0.00 (0/5) | 0.00 (0/5) | 0.40 (4/10) | 0.00 (0/10) | 0.40 (4/10) | 4.6 | 3.6 | 9.531 |

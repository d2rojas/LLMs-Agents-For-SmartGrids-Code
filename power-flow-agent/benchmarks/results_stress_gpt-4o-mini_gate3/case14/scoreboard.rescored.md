# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': ['stress']}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | 1 | 1.00 (40/40) | None | None | None | 0.6 | 1 | 0.6 | 6413 | 215.7 | 6629 | 0.001091 | 0.04366 | 1.00 (40/40) | 1 | 1.00 (40/40) | 0.00 (0/40) | 1.00 (16/16) | 0.23 (9/40) | 0.00 (0/40) | 0.23 (9/40) | 2.4 | 3.575 | 3.91 |

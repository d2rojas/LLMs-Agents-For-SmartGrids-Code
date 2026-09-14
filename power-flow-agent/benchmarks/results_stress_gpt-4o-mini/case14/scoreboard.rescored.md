# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': ['stress']}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none:rule_based | rule_based | 0.45 | 0.00 (0/40) | nan | 0 | nan | 1 | 1 | 0.8889 | 0 | 0 | 0 | 0 | 0 | 0.40 (16/40) | 1 | 0.92 (22/24) | 0.08 (2/24) | 0.00 (0/16) | 0.06 (1/18) | 0.00 (0/18) | 0.06 (1/18) | 0 | 1.3 | 0.1117 |
| openrouter:openai/gpt-4o-mini | pfagent | 1 | 0.60 (24/40) | nan | 0 | nan | 1 | 1 | 1 | 7216 | 223.6 | 7440 | 0.001217 | 0.04866 | 1.00 (40/40) | 1 | 1.00 (24/24) | 0.00 (0/24) | 0.00 (0/16) | 0.20 (8/40) | 0.00 (0/40) | 0.20 (8/40) | 2.4 | 3.575 | 3.922 |
| openrouter:openai/gpt-4o-mini | react_nogate | 1 | 0.60 (24/40) | nan | 0 | nan | 1 | 1 | 1 | 7457 | 222.3 | 7679 | 0.001252 | 0.05008 | 0.97 (39/40) | 0.9943 | 1.00 (24/24) | 0.00 (0/24) | 0.00 (0/16) | 0.17 (7/40) | 0.00 (0/40) | 0.17 (7/40) | 2.45 | 3.6 | 3.913 |
| openrouter:openai/gpt-4o-mini | single_call:structured | 1 | 0.57 (23/40) | nan | 0 | nan | 1 | 1 | 1 | 1.034e+04 | 177.9 | 1.052e+04 | 0.001658 | 0.06633 | 0.97 (39/40) | 0.9825 | 1.00 (24/24) | 0.00 (0/24) | 0.00 (0/16) | 0.03 (1/40) | 0.00 (0/40) | 0.03 (1/40) | 2 | 3.1 | 3.172 |

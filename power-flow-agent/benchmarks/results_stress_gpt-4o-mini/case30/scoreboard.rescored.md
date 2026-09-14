# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case30'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': ['stress']}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none:rule_based | rule_based | 0.425 | 0.00 (0/40) | nan | 0.4416 | nan | 0.9412 | 0.9804 | 1 | 0 | 0 | 0 | 0 | 0 | 0.40 (16/40) | 1 | 1.00 (23/23) | 0.00 (0/23) | 0.00 (0/17) | 0.00 (0/17) | 0.00 (0/17) | 0.00 (0/17) | 0 | 1.225 | 0.05008 |
| openrouter:openai/gpt-4o-mini | pfagent | 1 | 0.60 (24/40) | nan | 0 | nan | 1 | 1 | 1 | 1.474e+04 | 238.6 | 1.498e+04 | 0.002354 | 0.09417 | 1.00 (40/40) | 1 | 1.00 (23/23) | 0.00 (0/23) | 0.00 (0/17) | 0.20 (8/40) | 0.00 (0/40) | 0.20 (8/40) | 2.575 | 3.825 | 4.118 |
| openrouter:openai/gpt-4o-mini | react_nogate | 1 | 0.60 (24/40) | nan | 0 | nan | 1 | 1 | 1 | 1.476e+04 | 232.6 | 1.499e+04 | 0.002354 | 0.09416 | 1.00 (40/40) | 1 | 1.00 (23/23) | 0.00 (0/23) | 0.00 (0/17) | 0.25 (10/40) | 0.00 (0/40) | 0.25 (10/40) | 2.6 | 3.825 | 4.387 |
| openrouter:openai/gpt-4o-mini | single_call:structured | 1 | 0.57 (23/40) | nan | 0 | nan | 1 | 1 | 1 | 2.086e+04 | 193 | 2.106e+04 | 0.003245 | 0.1298 | 0.97 (39/40) | 1 | 1.00 (23/23) | 0.00 (0/23) | 0.00 (0/17) | 0.03 (1/40) | 0.00 (0/40) | 0.03 (1/40) | 2 | 3.375 | 3.556 |

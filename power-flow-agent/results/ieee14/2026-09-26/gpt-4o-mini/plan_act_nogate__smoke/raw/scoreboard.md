# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 3, 'difficulties': ['parameterized', 'multistep', 'ambiguous']}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | plan_act_nogate | 1 | 1.00 (3/3) | 1.917e-07 | 0.0002136 | 0.002624 | 1 | 1 | 1 | 2919 | 566 | 3485 | 0.0007774 | 0.002332 | 1.00 (3/3) | 1 | n/a | n/a | 0.00 (0/3) | 0.00 (0/3) | 0.00 (0/3) | 0.00 (0/3) | 2 | 3 | 9.613 |

# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case118'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | plan_act | 1 | 0.33 (13/40) | 3.645e-05 | 1.438 | 0.0001208 | 0.9659 | 1 | 1 | 2.68e+04 | 240.3 | 2.704e+04 | 0.004165 | 0.1666 | 0.45 (18/40) | 1 | n/a | n/a | 0.00 (0/40) | 0.08 (2/26) | 0.00 (0/26) | 0.08 (2/26) | 2 | 2.75 | 5.27 |

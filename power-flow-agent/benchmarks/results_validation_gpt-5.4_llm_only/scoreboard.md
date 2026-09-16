# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14', 'case30'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 5, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | llm_only_forced:cot | 1 | 0.20 (2/10) | 0.01785 | 6.935 | 30.32 | 0.8838 | 0.4444 | 1 | 3154 | 1597 | 4751 | 0.03184 | 0.3184 | n/a | 0.02348 | n/a | n/a | 0.00 (0/10) | n/a | n/a | n/a | 1 | 0 | 13.5 |
| openrouter:openai/gpt-5.4 | llm_only_forced:structured | 0.9 | 0.20 (2/10) | 0.009735 | 6.386 | 29.01 | 0.9004 | 0.5 | 1 | 2978 | 1182 | 4161 | 0.02518 | 0.2518 | n/a | 0.01805 | n/a | n/a | 0.00 (0/10) | n/a | n/a | n/a | 1 | 0 | 9.462 |

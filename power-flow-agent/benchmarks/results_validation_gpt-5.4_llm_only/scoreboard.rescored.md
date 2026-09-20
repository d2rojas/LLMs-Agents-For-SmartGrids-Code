# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 5, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | llm_only:cot | 1 | 0.00 (0/5) | None | None | None | 0 | 1 | 0 | 2516 | 428 | 2944 | 0.01271 | 0.06355 | n/a | 0.03333 | n/a | n/a | 0.60 (3/5) | n/a | n/a | n/a | 1 | 0 | 5.559 |
| openrouter:openai/gpt-5.4 | llm_only:structured | 1 | 0.00 (0/5) | None | None | None | 0 | 1 | 0 | 2340 | 49.8 | 2390 | 0.006596 | 0.03298 | n/a | 0 | n/a | n/a | 0.80 (4/5) | n/a | n/a | n/a | 1 | 0 | 2.069 |
| openrouter:openai/gpt-5.4 | llm_only_forced:cot | 1 | 0.00 (0/5) | 0.02181 | 5.014 | 33.19 | 0.8595 | 1 | 1 | 2542 | 1154 | 3696 | 0.02367 | 0.1183 | n/a | 0 | n/a | n/a | 0.00 (0/5) | n/a | n/a | n/a | 1 | 0 | 12.7 |
| openrouter:openai/gpt-5.4 | llm_only_forced:structured | 1 | 0.20 (1/5) | 0.006014 | 4.796 | 30.75 | 0.8605 | 1 | 1 | 2366 | 820.6 | 3186 | 0.01822 | 0.09112 | n/a | 0 | n/a | n/a | 0.00 (0/5) | n/a | n/a | n/a | 1 | 0 | 7.562 |

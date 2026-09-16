# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14', 'case30'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 20, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o | llm_only_forced:cot | 1 | 0.03 (1/40) | 0.01965 | 24.05 | 61.22 | 0.6909 | 0.4737 | 1 | 3273 | 1846 | 5119 | 0.02664 | 1.066 | n/a | 0.04596 | n/a | n/a | 0.00 (0/40) | n/a | n/a | n/a | 1 | 0 | 13.04 |
| openrouter:openai/gpt-4o | llm_only_forced:structured | 1 | 0.00 (0/40) | 0.02491 | 25.8 | 56.88 | 0.6686 | 0.4902 | 1 | 3097 | 1520 | 4617 | 0.02294 | 0.9175 | n/a | 0.04571 | n/a | n/a | 0.00 (0/40) | n/a | n/a | n/a | 1 | 0 | 10.01 |

# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case30'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': ['stress']}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | 1 | 0.60 (24/40) | nan | 0 | nan | 1 | 1 | 1 | 1.476e+04 | 236.6 | 1.5e+04 | 0.002356 | 0.09426 | 1.00 (40/40) | 1 | 0.59 (23/39) | 0.41 (16/39) | 0.00 (0/17) | 0.28 (11/40) | 0.00 (0/40) | 0.28 (11/40) | 2.6 | 3.825 | 4.056 |

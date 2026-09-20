# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | single_call:cot | 0.95 | 0.62 (25/40) | 1.543e-05 | 0.04817 | 0.0008489 | 1 | 1 | 1 | 9430 | 200.2 | 9631 | 0.001535 | 0.06139 | 0.90 (36/40) | 0.9923 | n/a | n/a | 0.00 (0/40) | 0.00 (0/24) | 0.00 (0/24) | 0.00 (0/24) | 1.95 | 1.875 | 3.317 |

# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case57'], max_rounds=8, requests={'source': 'generated', 'n_per_case_seed': 40, 'difficulties': None}

| model | task | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | single_call:rag | 0.95 | 1.339e-05 | 0.1043 | 0.005649 | 1 | 1 | 1 | 1.965e+04 | 212.7 | 1.987e+04 | 0.003076 | 0.1169 | 0.87 (33/38) | 0.9949 | n/a | n/a | 0.00 (0/24) | 0.00 (0/24) | 0.00 (0/24) | 1.9 | 1.675 | 5.138 |

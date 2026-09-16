# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': '/private/tmp/claude-501/-Users-lzanda-Documents-REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/407316ee-3d85-41c5-8036-570b8b373279/scratchpad/multistep_022_case14.jsonl'}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-5.4 | pfagent | 1 | 0.00 (0/1) | 0.0003901 | 0.03203 | 0.001675 | 1 | 1 | 1 | 3.745e+04 | 786 | 3.824e+04 | 0.1054 | 0.1054 | 0.00 (0/1) | 1 | n/a | n/a | 0.00 (0/1) | 0.00 (0/1) | 0.00 (0/1) | 0.00 (0/1) | 6 | 5 | 29.9 |
| openrouter:openai/gpt-5.4 | react_nogate | 1 | 0.00 (0/1) | 3.015e-05 | 0.002472 | 0.0001304 | 1 | 1 | 1 | 2.771e+04 | 763 | 2.847e+04 | 0.08072 | 0.08072 | 0.00 (0/1) | 1 | n/a | n/a | 0.00 (0/1) | 0.00 (0/1) | 0.00 (0/1) | 0.00 (0/1) | 4 | 5 | 13.51 |

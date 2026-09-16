# LLM Power-Flow Benchmark

k=1, seeds=[0], cases=['case14'], max_rounds=8, requests={'source': '/private/tmp/claude-501/-Users-lzanda-Documents-REVIEW-TUTORIAL-LLMS-AND-AGENTIC-FOR-SMART-GRIDS/407316ee-3d85-41c5-8036-570b8b373279/scratchpad/figure_pair_case14.jsonl'}

| model | task | success_rate | solved | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total | formulation_exact | faithful_numbers | safe_failure | claimed_success_on_failure | abstained_on_solvable | stale_state | stale_no_rerun | stale_quoted_old | llm_calls | tool_calls | wall_s |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openrouter:openai/gpt-4o-mini | pfagent | 1 | 0.50 (1/2) | nan | 0 | nan | 1 | 1 | 1 | 5.334e+04 | 426.5 | 5.377e+04 | 0.008257 | 0.01651 | 0.50 (1/2) | 1 | 1.00 (1/1) | 0.00 (0/1) | 0.50 (1/2) | 0.00 (0/2) | 0.00 (0/2) | 0.00 (0/2) | 5.5 | 5 | 10.38 |

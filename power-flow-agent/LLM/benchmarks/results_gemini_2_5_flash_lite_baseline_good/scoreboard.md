# LLM Power-Flow Benchmark

| model | task | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gemini:gemini-2.5-flash-lite | baseline_pf | 1.0 | 0.05715910866512464 | 61.16020913874061 | 10.434076378456947 | 0.26153846153846155 | 0.8 | 1.0 | 13551.0 | 9339.6 | 22890.6 | 0.005090940000000001 | 0.07636410000000002 |
| gemini:gemini-2.5-flash-lite | blueprint_pf | 0.0 | None | None | None | None | None | None | 15207.2 | 13547.0 | 28754.2 | 0.00693952 | 0.1040928 |

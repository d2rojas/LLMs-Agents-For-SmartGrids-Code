# LLM Power-Flow Benchmark

| model | task | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gemini:gemini-2.5-flash-lite | baseline_pf | 0.8333333333333334 | 0.03281626178560635 | 18.818224755730576 | 23.005386830518027 | 0.52 | 0.6 | 1.0 | 3142.4 | 2232.6 | 5375.0 | 0.0012072800000000002 | 0.006036400000000001 |
| gemini:gemini-2.5-flash-lite | blueprint_pf | 0.6666666666666666 | 0.015419656249249996 | 18.721843162799306 | 14.444686032725349 | 0.6785714285714286 | 0.75 | 1.0 | 2953.0 | 2644.25 | 5597.25 | 0.001353 | 0.005412 |

Prompt:
```
python3 benchmarks/evaluate_llms.py \
  --model gemini:gemini-2.5-flash-lite \
  --task baseline_pf \
  --task blueprint_pf \
  --case case14 \
  --case case30 \
  --runs 3 \
  --pricing-file pricing.json \
  --out-dir benchmarks/results
```
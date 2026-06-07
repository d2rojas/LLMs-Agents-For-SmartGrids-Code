# LLM Power-Flow Benchmark

| model | task | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openai:gpt-4o-mini | baseline_pf | 1.0 | None | None | None | 0.25 | 0.75 | 0.0 | 7277.0 | 61.0 | 7338.0 | 0.00112815 | 0.0090252 |
| openai:gpt-4o-mini | blueprint_pf | 0.75 | 0.04032056263286631 | 16.534379348608194 | 18.071340124678983 | 0.6796536796536796 | 0.6666666666666666 | 1.0 | 6842.25 | 3431.875 | 10274.125 | 0.0030854624999999995 | 0.024683699999999996 |

Prompt:
```
python3 benchmarks/evaluate_llms.py \
  --model openai:gpt-4o-mini \
  --task baseline_pf \
  --task blueprint_pf \
  --case case14 \
  --case case30 \
  --case case57 \
  --case case118 \
  --runs 2 \
  --pricing-file pricing.json \
  --out-dir benchmarks/results
```

python3 benchmarks/evaluate_llms.py \
  --model openai:gpt-4o-mini \
  --task baseline_pf \
  --task blueprint_pf \
  --case case14 \
  --case case30 \
  --case case57 \
  --case case118 \
  --case case300 \
  --runs 3 \
  --pricing-file pricing.json \
  --out-dir benchmarks/results
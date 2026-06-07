# LLM Power-Flow Benchmark

| model | task | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openai:gpt-4o-mini | baseline_pf | 1.0 | None | None | None | 0.2 | 0.8 | 0.0 | 11554.6 | 61.0 | 11615.6 | 0.0017697899999999998 | 0.026546849999999997 |
| openai:gpt-4o-mini | blueprint_pf | 0.6666666666666666 | 0.0241266120346111 | 19.84170509938499 | 23.071310353872626 | 0.5837280366692131 | 0.7 | 0.7 | 12132.833333333334 | 1954.0833333333333 | 14086.916666666666 | 0.0029923750000000002 | 0.0359085 |

PROMPT:
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
```

python3 benchmarks/evaluate_llms.py \
  --model openai:gpt-4.1-mini \
  --task baseline_pf \
  --task blueprint_pf \
  --case case14 \
  --case case30 \
  --case case57 \
  --case case118 \
  --case case300 \
  --runs 3 \
  --pricing-file pricing.json \
  --out-dir benchmarks/results_gpt_4_1_mini
# LLM Power-Flow Benchmark (Per Case)

| model | task | case | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| openai:gpt-4o-mini | baseline_pf | case118 | 1.0 | None | None | None | 0.0 | 1.0 | 0.0 | 16079.0 | 61.0 | 16140.0 | 0.0024484499999999996 | 0.007345349999999999 |
| openai:gpt-4o-mini | baseline_pf | case14 | 1.0 | None | None | None | 0.0 | 1.0 | 0.0 | 2366.0 | 61.0 | 2427.0 | 0.0003915000000000001 | 0.0011745000000000002 |
| openai:gpt-4o-mini | baseline_pf | case30 | 1.0 | None | None | None | 1.0 | 0.0 | 0.0 | 3652.0 | 61.0 | 3713.0 | 0.0005844 | 0.0017532 |
| openai:gpt-4o-mini | baseline_pf | case300 | 1.0 | None | None | None | 0.0 | 1.0 | 0.0 | 28797.0 | 61.0 | 28858.0 | 0.0043561500000000005 | 0.013068450000000002 |
| openai:gpt-4o-mini | baseline_pf | case57 | 1.0 | None | None | None | 0.0 | 1.0 | 0.0 | 6879.0 | 61.0 | 6940.0 | 0.0010684499999999999 | 0.0032053499999999996 |
| openai:gpt-4o-mini | blueprint_pf | case118 | 0.6666666666666666 | 0.0005602664162090714 | None | None | 0.8571428571428571 | 1.0 | 1.0 | 15781.0 | 3281.0 | 19062.0 | 0.004335749999999999 | 0.008671499999999999 |
| openai:gpt-4o-mini | blueprint_pf | case14 | 0.3333333333333333 | 0.0002509443406611332 | 26.102372018667573 | 2.131298947881895 | 0.9411764705882353 | 1.0 | 1.0 | 2130.0 | 1525.0 | 3655.0 | 0.0012345 | 0.0037034999999999998 |
| openai:gpt-4o-mini | blueprint_pf | case30 | 1.0 | 0.02172335946007094 | 8.164678215521766 | 37.503426598618645 | 1.0 | 0.0 | 1.0 | 3162.0 | 3049.3333333333335 | 6211.333333333333 | 0.0023039 | 0.0069117 |
| openai:gpt-4o-mini | blueprint_pf | case300 | 1.0 | None | None | None | 0.0 | 1.0 | 0.0 | 30620.0 | 102.33333333333333 | 30722.333333333332 | 0.0046543999999999995 | 0.013963199999999999 |
| openai:gpt-4o-mini | blueprint_pf | case57 | 0.3333333333333333 | 0.10234472868898557 | 48.61211883169208 | 0.7149730256252798 | 0.18181818181818182 | 1.0 | 1.0 | 6296.0 | 2857.0 | 9153.0 | 0.0026586 | 0.0026586 |

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
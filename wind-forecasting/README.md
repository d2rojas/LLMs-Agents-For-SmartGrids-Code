# Wind Power Forecasting (§VI-A)

The LLM is the **prediction engine** (no external solver). We compare three
prompting strategies across three frontier LLMs and a GRU baseline.

## Task
Given a 14-day history `X = {Wspd, Wdir, Etmp, Patv}` (W = 2,016 steps at 10-min
resolution) and an optional 48-h meteorological forecast (ERA5 100 m wind speed),
predict the next 48 h of active power (H = 288 steps). Output: strict JSON
`{"forecast": [f1, ..., f288]}`.

## Methods
1. **Naive** — raw 14-day data + minimal instruction. No constraints, no weather, no schema.
2. **Advanced** — naive + injected physical priors (power ∝ wind speed³ at low speed;
   saturation ≈ 1500 kW; ≈0 below 3 m/s) + strict JSON schema with retry (≤3 attempts).
3. **APBF** — Advanced + **Binning** (wind/power discretized to 16 ordinal levels,
   ~50% fewer tokens) + **Forecast** (48-h 100 m wind from Open-Meteo ERA5, interpolated
   to 10-min, appended to the prompt).

## Models / baseline
- Gemini 3 Flash, GPT-5.4, Claude Sonnet 4.6.
- GRU baseline (KDD Cup 2022 Wind Power Forecasting Challenge baseline on SDWPF).

## Data
- **SDWPF** (134 turbines, 10-min, 245 days). `TODO(authors): download link + path`.
- ERA5 100 m wind via Open-Meteo API. `TODO(authors): API usage / caching`.

## Metrics
MAE and RMSE (kW) at 3 h / 6 h / 48 h horizons; "Overall" = mean(MAE, RMSE).
Reproduces **Table (wind results)** in §VI-A.

## Run
```bash
# TODO(authors): exact commands, e.g.
# python run_wind.py --model gemini-3-flash --strategy apbf --horizon 48 --turbines held_out
```

## Verification (output-level, no solver)
JSON schema check + value clipping to `[0, 1500]` kW with retry.

## Files (to be added)
- `TODO(authors)`: data loader, prompt templates (naive/advanced/APBF), binning,
  Open-Meteo client, GRU baseline, evaluation harness, seeds.

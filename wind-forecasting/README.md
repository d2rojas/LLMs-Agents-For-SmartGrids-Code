# Wind Power Forecasting

LLM-based wind power forecasting: the LLM acts as the **prediction engine** (no
external solver) and is compared across three prompting strategies and a GRU
baseline. Because there is no solver, verification reduces to output-level checks
(JSON schema validity and clipping to the physical power range).

## Strategies
- **Naive** — raw history + minimal instruction.
- **Advanced** — physics-informed prompt (power ∝ wind speed³, saturation, cut-in) + strict JSON schema with retries.
- **APBF** — Advanced + **Binning** (16 ordinal levels, ~50% fewer tokens) + **Forecast** (48-h ERA5 100 m wind from Open-Meteo appended to the prompt).

## Data
- **SDWPF** turbine dataset (Zhou et al., *Scientific Data* 2024). Download it and place the SCADA file as `wtbdata_245days.csv` in this folder (it is large and is **not** committed).
- **ERA5** 100 m wind forecasts are fetched at run time from the free Open-Meteo API (no key required).

## Setup
```bash
cd wind-forecasting/replication_code
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# API keys for the LLMs you want to run:
export GEMINI_API_KEY=...        # Gemini 3 Flash
export ANTHROPIC_API_KEY=...     # Claude
```

## How to run
```bash
# Reproduce the full model × strategy × horizon table:
python run_full_table_experiments.py

# Run/replicate a single configuration:
python replicate_experiments.py

# Re-run only experiments that failed (e.g., API rate limits):
python retry_failed_experiments.py
```
A step-by-step walkthrough is in [`replication_code/REPLICATION_GUIDE.md`](replication_code/REPLICATION_GUIDE.md); notebooks (`replicate_results.ipynb`, `wind_forecasting_evaluation.ipynb`) reproduce the analysis interactively.

## Results (this replication)
- **Best:** Gemini 3 Flash + APBF at 3 h → **144.89 kW**, 54% better than the GRU baseline (315.82 kW).
- APBF excels at short horizons (3 h, 6 h); at 48 h the LLM struggles to emit exactly 288 values (schema-validation failures), which the output-level verification catches.

| Strategy | 3 h | 6 h | 48 h |
|---|---|---|---|
| Naive    | 336.68 | 582.23 | 686.56 |
| Advanced | 298.92 | 280.28 | 686.56 |
| APBF     | **144.89** | 211.87 | validation failure |

(Overall = mean of MAE and RMSE, kW; lower is better.)

## Files
```
wind-forecasting/
├── README.md                 # this file
├── replication_code/         # scripts + notebooks + REPLICATION_GUIDE.md
│   ├── replicate_experiments.py
│   ├── run_full_table_experiments.py
│   ├── retry_failed_experiments.py
│   ├── replicate_results.ipynb
│   └── requirements.txt
├── results/                  # experiment outputs (CSV) and result tables (.tex)
└── students_original/        # the original implementation (reference)
```
Large artifacts (the SDWPF CSV and the original report PDF) are not committed; see
**Data** above for how to obtain the dataset.

## Notes
The 48-h horizon is the hardest setting for an LLM predictor: it must return exactly
288 numbers, and small counting errors trip the schema check. This is the expected
failure mode for the no-solver case and motivates the output-level verification used
throughout the paper.

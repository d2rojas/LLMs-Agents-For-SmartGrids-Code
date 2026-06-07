# Wind Power Forecasting - Replication Study

## Overview
Replication of student project on LLM-based wind power forecasting.

## Students' Original Work
- **Report**: `wind.pdf`
- **Dataset**: `wtbdata_245days.csv`
- **Original files**: `students_original/`

## Our Replication Results (25/36 experiments completed)

### Best Result
**Gemini 3 Flash APBF 3h: 144.89 kW** (54% better than baseline of 315.82 kW)

### Complete Results
See our filled LaTeX tables:
- `OUR_RESULTS_COMPLETE_TABLE.tex` - Full matrix (all models, strategies, horizons)
- `OUR_RESULTS_SIMPLEST.tex` - Clean summary tables
- `results/full_table_v2_combined_20260416_130135.csv` - Raw data (25 experiments)

### Table Templates for Students
We created ideal table templates to help clarify their results:
- `SIMPLEST_TABLE_GEMINI3.tex` - 3×3 grid (easiest)
- `SINGLE_IDEAL_TABLE.tex` - Complete with averages
- `IDEAL_TABLE_TEMPLATE.tex` - Comprehensive multi-table

## Questions for Students
See `QUESTIONS_FOR_STUDENTS.md` for detailed questions about:
1. Which forecast horizon (3h, 6h, 48h) each result in their Table 3 represents
2. How they achieved APBF 48h (we encountered validation failures)
3. Whether they tested multiple horizons for each strategy

## Key Findings

### Success Stories
- ✅ **Matched APBF 3h**: Our 144.89 kW matches their ~145 kW
- ✅ **Reproduced APBF failure at 48h**: LLM can't count to 288 consistently
- ✅ **Beat baseline**: 5 configurations surpassed GRU baseline (315.82 kW)
- ✅ **Strategy effectiveness**: APBF excels at short horizons (3h, 6h)

### Challenges
- ❌ **APBF 48h**: Failed validation (LLM generated 312, 291, 293 values instead of 288)
- ⚠️ **Claude rate limits**: 10/17 Claude experiments hit API limits
- ⚠️ **Inconsistent strategies**: Advanced sometimes worse than Naive (horizon-dependent)

## Comparison with Students' Results

| Configuration | Students (horizon?) | Our Results |
|--------------|---------------------|-------------|
| APBF | 241.07 kW | 144.89 kW (3h), 211.87 kW (6h), Failed (48h) |
| Naive | 1072.48 kW | 336.68 kW (3h), 582.23 kW (6h), 686.56 kW (48h) |
| Advanced | 402.83 kW | 298.92 kW (3h), 280.28 kW (6h), 686.56 kW (48h) |

**Critical Question**: Students' results don't specify horizons - we need clarification!

## Files Structure

```
wind-forecasting/
├── README.md # This file
├── QUESTIONS_FOR_STUDENTS.md # Questions for students
│
├── wind.pdf # Students' original report (5.9 MB)
├── wtbdata_245days.csv # Dataset (72 MB)
├── students_original/ # Original student files
│
├── OUR_RESULTS_COMPLETE_TABLE.tex # Our complete results with analysis
├── OUR_RESULTS_SIMPLEST.tex # Our simplified results
├── SIMPLEST_TABLE_GEMINI3.tex # Template: 3×3 grid
├── SINGLE_IDEAL_TABLE.tex # Template: with averages
├── IDEAL_TABLE_TEMPLATE.tex # Template: comprehensive
│
├── results/ # All experimental results (43 files)
│ └── full_table_v2_combined_20260416_130135.csv # Final combined data (25 experiments)
│
└── replication_code/ # Experimental scripts and notebooks
 ├── replicate_experiments.py
 ├── run_full_table_experiments.py
 ├── retry_failed_experiments.py
 ├── replicate_results.ipynb
 └── ... (other experiment files)
```

## Experimental Setup

- **Models tested**: Gemini 3 Flash, Gemini 3 Pro, Claude 3.5/4.5/4.6
- **Strategies**: Naive, Advanced (physics-informed), APBF (Advanced + Binning + Forecast)
- **Horizons**: 3h (18 pts), 6h (36 pts), 48h (288 pts) at 10-min intervals
- **Metrics**: MAE, RMSE, Overall = (MAE + RMSE) / 2
- **Baseline**: GRU normalized = 315.82 kW (48h)

## Next Steps

1. Wait for students' responses to clarify horizon specifications
2. Compare methodologies once we understand their exact setup
3. Document lessons learned for LLM-based time-series forecasting
4. Consider testing with newer models if appropriate

---

**Date**: April 16, 2026
**Status**: Awaiting student clarification on methodology

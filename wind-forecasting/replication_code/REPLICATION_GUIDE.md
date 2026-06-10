# Wind Power Forecasting LLM - Replication Guide

This guide helps you replicate the results from the Case Study: "LLMs for Wind Power Forecasting"

## Quick Start

### 1. Install Dependencies

```bash
cd wind-forecasting
pip install -r requirements.txt
```

### 2. Set Up API Keys

#### Option A: Environment Variables (Recommended)
```bash
# For Gemini
export GEMINI_API_KEY="your_gemini_api_key_here"

# For Claude
export ANTHROPIC_API_KEY="your_claude_api_key_here"
```

#### Option B: Direct in Code
Edit the notebook/script and paste your API key directly (not recommended for production).

**Get API Keys:**
- Gemini: https://aistudio.google.com/app/apikey
- Claude: https://console.anthropic.com/

### 3. Run Experiments

#### Option 1: Jupyter Notebook (Interactive)
```bash
jupyter notebook replicate_results.ipynb
```

Then run cells sequentially. The notebook includes:
- Configuration options
- Test runs
- Full experiment suite
- Visualization
- LaTeX table generation

#### Option 2: Python Script (Command Line)
```bash
# Quick test with Gemini
python replicate_experiments.py --provider gemini --api-key YOUR_KEY

# Full experiment suite
python replicate_experiments.py \
 --provider gemini \
 --horizons 3 6 48 \
 --strategies naive advanced apbf \
 --output-dir results

# Using Claude
python replicate_experiments.py --provider claude --api-key YOUR_KEY

# Without weather API (faster, less accurate)
python replicate_experiments.py --provider gemini --api-key YOUR_KEY --no-weather
```

## Expected Results

Reference results for Gemini 3 Flash on turbine 1 (see the project `README.md` for the full strategy × horizon table):

| Model/Variant | MAE (kW) | RMSE (kW) | Overall (kW) |
|---------------|----------|-----------|--------------|
| **Gemini 3-flash (APBF)** | **189.79** | **292.34** | **241.07** |
| Gemini 3-flash (Advanced) | 366.22 | 439.44 | 402.83 |
| Gemini 3-flash (Naive) | 1030.67 | 1114.29 | 1072.48 |
| GRU Baseline | 351.34 | 280.28 | 315.82 |

**Key Finding:** APBF (Advanced Prompt + Binning + Forecast) significantly outperformed naive prompting (~77% improvement).

## Experimental Setup

- **Task**: 48-hour ahead wind power forecasting at 10-minute resolution
- **Dataset**: SDWPF (Baidu KDD Cup 2022) - Gansu Guazhou wind farm, China
- **Test Window**: 14-day rolling history for in-context learning
- **Tools Used**: Gemini 3-flash, GPT 5.2, Open-Meteo Historical Archive API
- **Budget**: ~1 LLM call per forecast; ~90k tokens/call; 2-3 min runtime

## Files Overview

```
wind-forecasting/
├── replicate_results.ipynb # Interactive notebook
├── replicate_experiments.py # Command-line script
├── REPLICATION_GUIDE.md # This file
├── requirements.txt # Python dependencies
├── wtbdata_245days.csv # Main dataset (72 MB, downloaded separately)
└── results/ # Output directory (created automatically)
 ├── results_YYYYMMDD_HHMMSS.csv
 └── ...
```

## Understanding the Strategies

### 1. Naive Baseline
- Simple prompt with raw SCADA data
- No preprocessing or domain knowledge
- Minimal instructions

### 2. Advanced Prompt
- Physics-informed constraints (Power ∝ Wind³)
- Explicit JSON output format
- Domain knowledge injection

### 3. APBF (Best Performance)
- **Binning**: Reduces tokens by ~40% (16 equal-width bins)
- **ERA5 Forecasts**: 100m wind speed from Open-Meteo API
- **Advanced Prompting**: Physics constraints + structured output

## Troubleshooting

### API Rate Limits
**Problem:** "Too many requests" or "Quota exceeded"

**Solutions:**
- **Gemini Free Tier**: 20 requests/day limit
 - Run fewer experiments at a time
 - Wait 24 hours between runs
 - Upgrade to paid tier
- **Claude**: Higher limits, but still rate-limited
 - Add pauses between calls (already included in script)

### Weather API Errors
**Problem:** Open-Meteo API fails

**Solutions:**
```bash
# Install weather libraries
pip install openmeteo-requests requests-cache retry-requests

# Or disable weather API
python replicate_experiments.py --no-weather
```

### Missing Data File
**Problem:** `FileNotFoundError: wtbdata_245days.csv`

**Solution:**
```bash
# Ensure you're in the correct directory
cd wind-forecasting

# Check if file exists
ls -lh wtbdata_245days.csv

# If missing, it should be in the project root
```

### JSON Parsing Errors
**Problem:** LLM returns invalid JSON

**Solution:**
- Already handled by retry logic (up to 3 attempts)
- Some LLMs are more reliable than others
- Advanced/APBF strategies work better than Naive

## Customization

### Test Different Turbines
```python
# In notebook
TURBINE_ID = 5 # Try turbines 1-134

# In script
python replicate_experiments.py --turbine 5
```

### Different Time Windows
```python
# In notebook
BASE_DAY = 50 # Valid range: 1-231

# In script
python replicate_experiments.py --base-day 50
```

### Custom Horizons
```bash
# Test only short-term forecasts
python replicate_experiments.py --horizons 3 6
```

## Understanding the Output

### CSV Results
```csv
Strategy,Horizon (h),Model,TurbID,BaseDay,MAE,RMSE,Overall,Points,Runtime (s)
apbf,3,gemini-3-flash,1,1,189.79,292.34,241.07,18,45.2
advanced,3,gemini-3-flash,1,1,366.22,439.44,402.83,18,38.1
...
```

### Metrics Explained
- **MAE (Mean Absolute Error)**: Average magnitude of errors (lower is better)
- **RMSE (Root Mean Squared Error)**: Penalizes large errors more (lower is better)
- **Overall Score**: (MAE + RMSE) / 2 - Combined metric used in KDD Cup
- **Points**: Number of valid forecast points used (should be 18 for 3h, 36 for 6h, 288 for 48h)

## Run-to-Run Variability

Your results may differ slightly due to:
1. **LLM Non-Determinism**: Different runs produce different outputs
2. **API Model Updates**: Providers update models over time
3. **Weather Data**: ERA5 reanalysis (not true forecasts from 2020)
4. **Sampling Parameters**: Decoding temperature affects output stability

Expect variations of ±10-20% in MAE/RMSE.

## Advanced Usage

### Config File
Create `config.json`:
```json
{
 "provider": "gemini",
 "api_key": "your_key_here",
 "turbine_id": 1,
 "base_day": 1,
 "horizons": [3, 6, 48],
 "strategies": ["naive", "advanced", "apbf"],
 "use_weather": true,
 "max_retries": 3,
 "data_path": "wtbdata_245days.csv",
 "output_dir": "results"
}
```

Then run:
```bash
python replicate_experiments.py --config config.json
```

### Batch Processing
```bash
# Test multiple turbines
for turb in 1 2 3 4 5; do
 python replicate_experiments.py --turbine $turb --output-dir results/turb_$turb
done
```

## Timeline Estimate

- **Single 3h experiment**: ~1-2 minutes
- **Single 48h experiment**: ~2-4 minutes
- **Full Table 2 replication** (3 strategies × 3 horizons): ~30-60 minutes
- **Full Table 3 replication** (multiple models): Several hours (due to rate limits)

Good luck with your replication! 🌬️⚡

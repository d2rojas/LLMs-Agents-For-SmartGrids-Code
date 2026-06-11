#!/usr/bin/env python3
"""
Wind Power Forecasting with LLMs - Results Replication Script

This script replicates the experiments from the Case Study Report.
It runs different prompting strategies (Naive, Advanced, APBF) across
multiple forecast horizons (3h, 6h, 48h) and saves results to CSV.

Usage:
    python replicate_experiments.py --provider gemini --api-key YOUR_KEY
    python replicate_experiments.py --provider claude --api-key YOUR_KEY --horizons 3 6 48
    python replicate_experiments.py --config config.json

Authors: Based on work by Abdulwahab Albassam, Aidan Leung, Jett Ngo
"""

import os
import sys
import json
import time
import re
import argparse
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error


# ============================================================================
# Configuration
# ============================================================================

class Config:
    """Experiment configuration"""
    def __init__(self):
        self.provider = "gemini"
        self.model_name = None
        self.api_key = None
        self.turbine_id = 1
        self.base_day = 1
        self.horizons = [3, 6, 48]
        self.strategies = ['naive', 'advanced', 'apbf']
        self.use_weather = True
        self.max_retries = 3
        self.data_path = "wtbdata_245days.csv"
        self.output_dir = "results"

    @classmethod
    def from_json(cls, path):
        """Load config from JSON file"""
        config = cls()
        with open(path) as f:
            data = json.load(f)
        for key, value in data.items():
            setattr(config, key, value)
        return config

    def to_json(self, path):
        """Save config to JSON file"""
        data = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)


# ============================================================================
# LLM Client Setup
# ============================================================================

def setup_llm_client(provider, api_key):
    """Initialize LLM client based on provider"""
    if provider == "claude":
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        model_name = "claude-3-haiku-20240307"
        print(f"✅ Using Claude: {model_name}")
        return client, model_name

    elif provider == "openai":
        import openai
        client = openai.OpenAI(api_key=api_key)
        model_name = "gpt-5.4"
        print(f"✅ Using OpenAI: {model_name}")
        return client, model_name

    elif provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        client = genai.GenerativeModel('models/gemini-3-flash-preview')
        model_name = "gemini-3-flash"
        print(f"✅ Using Gemini: {model_name}")
        print("   ⚠️  Note: Free tier has rate limits")
        return client, model_name
    else:
        raise ValueError(f"Unknown provider: {provider}")


# ============================================================================
# Helper Functions
# ============================================================================

def bin_turbine_data(df, n_bins=16, bin_cols=None):
    """Bins numeric columns into equal-width integer IDs [0, n_bins-1]"""
    hist = df.copy()
    if bin_cols is None:
        excluded = {"TurbID", "Day", "Tmstamp"}
        bin_cols = [
            c for c in hist.columns
            if (c not in excluded) and pd.api.types.is_numeric_dtype(hist[c])
        ]

    for c in bin_cols:
        x = pd.to_numeric(hist[c], errors="coerce")
        valid = x.dropna()
        if valid.empty:
            continue

        lo, hi = float(valid.min()), float(valid.max())

        if np.isclose(lo, hi):
            hist[c] = 0
            continue

        edges = np.linspace(lo, hi, n_bins + 1)
        binned = pd.cut(x, bins=edges, labels=False, include_lowest=True, duplicates="drop")
        hist[c] = binned.astype("Int64")

    return hist, bin_cols


def get_openmeteo_wind_data(lat, lon, start_date, end_date, max_retries=3):
    """Fetches 100m wind speed data from Open-Meteo Archive API"""
    try:
        import openmeteo_requests
        import requests_cache
        from retry_requests import retry
    except ImportError:
        print("⚠️ Weather API libraries not installed")
        print("   Install with: pip install openmeteo-requests requests-cache retry-requests")
        return None

    cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
    retry_session = retry(cache_session, retries=max_retries, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "wind_speed_100m",
        "timezone": "auto",
        "wind_speed_unit": "ms",
    }

    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]

    hourly = response.Hourly()
    hourly_wind_speed_100m = hourly.Variables(0).ValuesAsNumpy()

    hourly_data = {
        "timestamp": pd.date_range(
            start=pd.to_datetime(hourly.Time() + response.UtcOffsetSeconds(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd() + response.UtcOffsetSeconds(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left"
        ),
        "wind_speed_100m": hourly_wind_speed_100m
    }

    return pd.DataFrame(data=hourly_data)


def evaluate_forecast(df, turb_id, base_day, output, horizon_hours=48):
    """Evaluates LLM forecast against ground truth"""
    expected_points = horizon_hours * 6

    target_start = base_day + 14
    target_days = int(np.ceil(horizon_hours / 24))
    target_end = target_start + target_days - 1

    # Extract ground truth
    actual_data = df[
        (df['TurbID'] == turb_id) &
        (df['Day'] >= target_start) &
        (df['Day'] <= target_end)
    ]

    actual_values = (
        actual_data
        .sort_values(['Day', 'Tmstamp'])
        ['Patv']
        .dropna()
        .tolist()
    )[:expected_points]

    # Parse LLM output
    try:
        clean_json = output.replace('```json', '').replace('```', '').strip()
        data = json.loads(clean_json)
        predicted_values = data.get('forecast', [])
    except:
        predicted_values = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", output)]

    predicted_values = predicted_values[:expected_points]

    # Validation
    if len(predicted_values) != expected_points:
        print(f"⚠️ Expected {expected_points} predictions, got {len(predicted_values)}")

    if len(actual_values) != expected_points:
        print(f"⚠️ Expected {expected_points} actual points, got {len(actual_values)}")

    min_len = min(len(actual_values), len(predicted_values))

    if min_len == 0:
        print("❌ Error: No overlapping forecast points")
        return None

    y_true = actual_values[:min_len]
    y_pred = predicted_values[:min_len]

    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    score = (mae + rmse) / 2

    print(f"\n--- {horizon_hours}h Evaluation (Days {target_start}-{target_end}) ---")
    print(f"Points used: {min_len}/{expected_points}")
    print(f"MAE:  {mae:.2f} kW")
    print(f"RMSE: {rmse:.2f} kW")
    print(f"Overall Score: {score:.2f} kW")

    return {
        "MAE": mae,
        "RMSE": rmse,
        "Score": score,
        "points_used": min_len,
        "horizon_hours": horizon_hours
    }


# ============================================================================
# Prompting Strategies
# ============================================================================

def call_llm_naive(client, provider, model_name, df, turb_id, base_day, horizon_hours=48):
    """Naive baseline strategy"""
    turbine_data = df[df['TurbID'] == turb_id]
    turbine_data = turbine_data.dropna(subset=['Wspd'])

    end_day = base_day + 13
    window_data = turbine_data[
        (turbine_data['Day'] >= base_day) &
        (turbine_data['Day'] <= end_day)
    ].drop(columns=['TurbID'])

    data_str = window_data.to_csv(index=False, sep=',')
    expected_points = horizon_hours * 6

    prompt = f"""You are given the past 14 days of 10-minute SCADA data.
Columns: Day, Tmstamp, Wspd, Etmp, Itmp, Patv

Forecast Patv (kW) for Day {end_day + 1} to Day {end_day + int(np.ceil(horizon_hours/24))} at 10-minute resolution.
Return a csv file with one column only.

Data:
{data_str}
"""

    if provider == "claude":
        response = client.messages.create(
            model=model_name,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    elif provider == "openai":
        response = client.chat.completions.create(
            model=model_name,
            max_completion_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    else:
        response = client.generate_content(prompt)
        return response.text


def call_llm_advanced(client, provider, model_name, df, turb_id, base_day, horizon_hours=48):
    """Advanced prompting strategy"""
    turbine_data = df[df['TurbID'] == turb_id]
    turbine_data = turbine_data.dropna(subset=['Wspd'])

    end_day = base_day + 13
    window_data = turbine_data[
        (turbine_data['Day'] >= base_day) &
        (turbine_data['Day'] <= end_day)
    ].copy()

    data_str = window_data.to_csv(index=False, sep=',')
    expected_points = horizon_hours * 6

    prompt = f"""Context: You are an expert wind turbine power forecasting model.

You are given 14 days of historical SCADA data for ONE turbine.
The data is sampled every 10 minutes (144 rows per day).
Columns: {', '.join(window_data.columns.tolist())}

Input Data:
{data_str}

Your task:
Predict the Active Power (Patv, in kW) for the NEXT {horizon_hours} HOURS
({expected_points} time steps at 10-minute resolution).

Instructions:

Learn the wind-speed to power relationship from the historical data.
Power is roughly proportional to wind speed cubed at low speeds.
Power saturates near rated power (~1500 kW).
Power is near zero at very low wind speeds.

Capture daily cyclic patterns.
Do NOT copy the last day.
Do NOT output negative values.
Clip values to the realistic range [0, 1500].

OUTPUT FORMAT REQUIREMENTS (VERY IMPORTANT):

Return valid JSON in the following format:

{{
  "forecast": [f1, f2, f3, ..., f{expected_points}]
}}

The list MUST contain exactly {expected_points} numbers.

No text outside the JSON.
No explanations.
No markdown formatting.
Only raw JSON.
"""

    if provider == "claude":
        response = client.messages.create(
            model=model_name,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    elif provider == "openai":
        response = client.chat.completions.create(
            model=model_name,
            max_completion_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    else:
        response = client.generate_content(prompt)
        return response.text


def call_llm_apbf(client, provider, model_name, df, turb_id, base_day,
                   horizon_hours=48, use_weather=True, max_retries=3):
    """APBF strategy (Advanced + Binning + Forecast)"""
    turbine_data = df[df['TurbID'] == turb_id]
    turbine_data = turbine_data.dropna(subset=['Wspd'])

    end_day = base_day + 13
    window_data = turbine_data[
        (turbine_data['Day'] >= base_day) &
        (turbine_data['Day'] <= end_day)
    ].copy()

    # Apply binning
    print(f"📊 Binning data into 16 levels...")
    window_data, binned_list = bin_turbine_data(window_data, n_bins=16, bin_cols=["Wspd", "Patv"])
    bin_msg = f"Note: Columns ({', '.join(binned_list)}) binned into 16 levels (0-15)."

    data_str = window_data.to_csv(index=False, sep=',')
    expected_points = horizon_hours * 6

    # Weather forecast section
    forecast_section = "No external meteorological forecast provided."

    if use_weather:
        latitude = 40.6306
        longitude = 96.9498
        anchor_date = datetime(2020, 5, 1)
        forecast_start_date = anchor_date + timedelta(days=int(base_day + 13))
        forecast_end_date = forecast_start_date + timedelta(days=int(np.ceil(horizon_hours/24)))

        start_str = forecast_start_date.strftime('%Y-%m-%d')
        end_str = forecast_end_date.strftime('%Y-%m-%d')

        for attempt in range(1, max_retries + 1):
            try:
                print(f"🌐 Fetching weather ({start_str} to {end_str})...")
                weather_df = get_openmeteo_wind_data(latitude, longitude, start_str, end_str)

                if weather_df is not None:
                    hourly_points = horizon_hours
                    w_speeds = weather_df['wind_speed_100m'].values[:hourly_points]
                    xp = np.arange(len(w_speeds))
                    x_new = np.linspace(0, len(w_speeds)-1, expected_points)
                    interp_w_speeds = np.interp(x_new, xp, w_speeds)

                    forecast_str = ", ".join([f"{v:.2f}" for v in interp_w_speeds])
                    forecast_section = f"""Input 2: {horizon_hours}-Hour Meteorological Forecast (100m)
Predicted wind speeds (m/s) at 10-minute intervals:
[{forecast_str}]"""
                    print(f"✅ Retrieved {len(interp_w_speeds)} forecast points")
                    break
            except Exception as e:
                print(f"⚠️ Weather API failed: {e}")
                if attempt < max_retries:
                    time.sleep(5)

    prompt = f"""Context: You are an expert wind turbine power forecasting model.

{bin_msg}

Input 1: 14 days of historical SCADA data (10-minute sampling, 144 rows/day).
Columns: {', '.join(window_data.columns.tolist())}
{data_str}

{forecast_section}

Task:
Predict Active Power (Patv, in kW) for NEXT {horizon_hours} HOURS ({expected_points} timesteps).

Instructions:
- Learn wind-speed to power relationship (P ∝ W³ at low speeds)
- Power saturates near 1500 kW
- Capture daily patterns
- Do NOT copy last day
- Clip to [0, 1500] range

OUTPUT FORMAT (CRITICAL):
{{
"forecast": [f1, f2, ..., f{expected_points}]
}}

Must have EXACTLY {expected_points} numbers.
No text outside JSON. No explanations. Raw JSON only.
"""

    # LLM call with retry
    for llm_attempt in range(1, max_retries + 1):
        print(f"🤖 LLM inference (attempt {llm_attempt})...")

        try:
            if provider == "claude":
                response = client.messages.create(
                    model=model_name,
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}]
                )
                raw_text = response.content[0].text
            elif provider == "openai":
                response = client.chat.completions.create(
                    model=model_name,
                    max_completion_tokens=4096,
                    messages=[{"role": "user", "content": prompt}]
                )
                raw_text = response.choices[0].message.content
            else:
                response = client.generate_content(prompt)
                raw_text = response.text

            # Validate
            clean_json = raw_text.replace('```json', '').replace('```', '').strip()
            data = json.loads(clean_json)

            if "forecast" in data and len(data["forecast"]) == expected_points:
                print(f"✅ Success: {expected_points} values")
                return raw_text
            else:
                print(f"⚠️ Validation failed: {len(data.get('forecast', []))} values")

        except Exception as e:
            print(f"⚠️ Error: {e}")

        if llm_attempt < max_retries:
            time.sleep(2)

    print("❌ All attempts failed")
    return None


# ============================================================================
# Main Experiment Runner
# ============================================================================

def run_experiments(config):
    """Run full experiment suite"""

    # Setup
    client, model_name = setup_llm_client(config.provider, config.api_key)

    # Load data
    print(f"\nLoading dataset: {config.data_path}")
    df = pd.read_csv(config.data_path)
    print(f"✅ Loaded {len(df)} rows, {df['TurbID'].nunique()} turbines, {df['Day'].nunique()} days")

    # Create output directory
    Path(config.output_dir).mkdir(exist_ok=True)

    # Run experiments
    results = []

    for strategy in config.strategies:
        for horizon in config.horizons:
            print("\n" + "=" * 80)
            print(f"Running: {strategy.upper()} | {horizon}h | Turbine {config.turbine_id}")
            print("=" * 80)

            start_time = time.time()

            try:
                # Call strategy
                if strategy == 'naive':
                    output = call_llm_naive(client, config.provider, model_name,
                                           df, config.turbine_id, config.base_day, horizon)
                elif strategy == 'advanced':
                    output = call_llm_advanced(client, config.provider, model_name,
                                              df, config.turbine_id, config.base_day, horizon)
                elif strategy == 'apbf':
                    output = call_llm_apbf(client, config.provider, model_name,
                                          df, config.turbine_id, config.base_day,
                                          horizon, config.use_weather, config.max_retries)

                # Evaluate
                if output:
                    eval_result = evaluate_forecast(df, config.turbine_id,
                                                    config.base_day, output, horizon)

                    if eval_result:
                        results.append({
                            'Strategy': strategy,
                            'Horizon (h)': horizon,
                            'Model': model_name,
                            'TurbID': config.turbine_id,
                            'BaseDay': config.base_day,
                            'MAE': eval_result['MAE'],
                            'RMSE': eval_result['RMSE'],
                            'Overall': eval_result['Score'],
                            'Points': eval_result['points_used'],
                            'Runtime (s)': time.time() - start_time
                        })
                        print(f"✅ Completed in {time.time() - start_time:.1f}s")

            except Exception as e:
                print(f"❌ Error: {e}")

            # Rate limiting
            print("\n⏸️  Pausing 10s...")
            time.sleep(10)

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_df = pd.DataFrame(results)
    output_file = Path(config.output_dir) / f"results_{timestamp}.csv"
    results_df.to_csv(output_file, index=False)

    print("\n" + "=" * 80)
    print("EXPERIMENT COMPLETED")
    print("=" * 80)
    print(f"💾 Results saved to: {output_file}")
    print("\nFinal Results:")
    print(results_df.to_string(index=False))

    return results_df


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Replicate Wind Power Forecasting LLM Experiments"
    )
    parser.add_argument('--provider', choices=['gemini', 'claude', 'openai'],
                       default='gemini', help='LLM provider')
    parser.add_argument('--api-key', help='API key (or set via env var)')
    parser.add_argument('--config', help='Load config from JSON file')
    parser.add_argument('--horizons', nargs='+', type=int,
                       default=[3, 6, 48], help='Forecast horizons in hours')
    parser.add_argument('--strategies', nargs='+',
                       default=['naive', 'advanced', 'apbf'],
                       help='Prompting strategies to test')
    parser.add_argument('--turbine', type=int, default=1, help='Turbine ID')
    parser.add_argument('--base-day', type=int, default=1, help='Starting day')
    parser.add_argument('--no-weather', action='store_true',
                       help='Disable weather API calls')
    parser.add_argument('--output-dir', default='results',
                       help='Output directory')

    args = parser.parse_args()

    # Load or create config
    if args.config:
        config = Config.from_json(args.config)
    else:
        config = Config()
        config.provider = args.provider
        config.horizons = args.horizons
        config.strategies = args.strategies
        config.turbine_id = args.turbine
        config.base_day = args.base_day
        config.use_weather = not args.no_weather
        config.output_dir = args.output_dir

        # Get API key
        if args.api_key:
            config.api_key = args.api_key
        elif config.provider == 'claude':
            config.api_key = os.environ.get('ANTHROPIC_API_KEY')
        elif config.provider == 'openai':
            config.api_key = os.environ.get('OPENAI_API_KEY')
        elif config.provider == 'gemini':
            config.api_key = os.environ.get('GEMINI_API_KEY')

        if not config.api_key:
            print(f"❌ Error: No API key provided")
            print(f"   Set {config.provider.upper()}_API_KEY environment variable or use --api-key")
            sys.exit(1)

    # Run experiments
    run_experiments(config)


if __name__ == "__main__":
    main()

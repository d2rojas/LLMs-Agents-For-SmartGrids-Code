#!/usr/bin/env python3
"""
Comprehensive experiment runner for Table V replication
Runs all model/strategy/horizon combinations
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from replicate_experiments import *
import pandas as pd
from datetime import datetime

# Configuration for all experiments
EXPERIMENTS = [
    # Gemini 3 Flash (same as students used)
    {'provider': 'gemini', 'model': 'gemini-3-flash-preview', 'model_name': 'Gemini 3 Flash'},
    # Gemini 3 Pro
    {'provider': 'gemini', 'model': 'gemini-3-pro-preview', 'model_name': 'Gemini 3 Pro'},
    # Claude 3.5 Haiku
    {'provider': 'claude', 'model': 'claude-3-5-haiku-20241022', 'model_name': 'Claude 3.5 Haiku'},
    # Claude 3.5 Sonnet
    {'provider': 'claude', 'model': 'claude-3-5-sonnet-20241022', 'model_name': 'Claude 3.5 Sonnet'},
]

STRATEGIES = ['naive', 'advanced', 'apbf']
HORIZONS = [3, 6, 48]

def setup_model_client(provider, model_id, api_key):
    """Setup client for specific model"""
    if provider == 'claude':
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        return client, model_id
    elif provider == 'gemini':
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        client = genai.GenerativeModel(f'models/{model_id}')
        return client, model_id
    else:
        raise ValueError(f"Unknown provider: {provider}")

def main():
    # API Keys
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '***REMOVED***')
    CLAUDE_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

    if not CLAUDE_API_KEY:
        print("⚠️  Warning: No Claude API key found. Claude experiments will be skipped.")
        print("   Set ANTHROPIC_API_KEY environment variable to enable.")

    # Load data
    print("Loading dataset...")
    df = pd.read_csv('wtbdata_245days.csv')
    print(f"✅ Loaded {len(df)} rows\n")

    # Experiment configuration
    TURBINE_ID = 1
    BASE_DAY = 1

    # Results storage
    all_results = []

    # Run all experiments
    total_experiments = len(EXPERIMENTS) * len(STRATEGIES) * len(HORIZONS)
    current_exp = 0

    for exp_config in EXPERIMENTS:
        provider = exp_config['provider']
        model_id = exp_config['model']
        model_name = exp_config['model_name']

        # Check API key availability
        if provider == 'claude' and not CLAUDE_API_KEY:
            print(f"⏭️  Skipping {model_name} (no API key)")
            continue

        api_key = CLAUDE_API_KEY if provider == 'claude' else GEMINI_API_KEY

        print("=" * 80)
        print(f"MODEL: {model_name} ({provider})")
        print("=" * 80)

        # Setup client
        try:
            client, model_full_name = setup_model_client(provider, model_id, api_key)
        except Exception as e:
            print(f"❌ Failed to setup {model_name}: {e}")
            continue

        for strategy in STRATEGIES:
            for horizon in HORIZONS:
                current_exp += 1

                print(f"\n[{current_exp}/{total_experiments}] Running: {model_name} | {strategy.upper()} | {horizon}h")
                print("-" * 80)

                start_time = time.time()

                try:
                    # Call appropriate strategy
                    if strategy == 'naive':
                        output = call_llm_naive(client, provider, model_full_name,
                                               df, TURBINE_ID, BASE_DAY, horizon)
                    elif strategy == 'apbf':
                        output = call_llm_apbf(client, provider, model_full_name,
                                              df, TURBINE_ID, BASE_DAY, horizon,
                                              use_weather=True, max_retries=3)

                    # Evaluate
                    if output:
                        eval_result = evaluate_forecast(df, TURBINE_ID, BASE_DAY, output, horizon)

                        if eval_result:
                            all_results.append({
                                'Model': model_name,
                                'Provider': provider,
                                'ModelID': model_id,
                                'Strategy': strategy,
                                'Horizon (h)': horizon,
                                'TurbID': TURBINE_ID,
                                'BaseDay': BASE_DAY,
                                'MAE': eval_result['MAE'],
                                'RMSE': eval_result['RMSE'],
                                'Overall': eval_result['Score'],
                                'Points': eval_result['points_used'],
                                'Runtime (s)': time.time() - start_time,
                                'Timestamp': datetime.now().isoformat()
                            })
                            print(f"✅ Completed in {time.time() - start_time:.1f}s")
                        else:
                            print("❌ Evaluation failed")
                    else:
                        print("❌ LLM call failed")

                except Exception as e:
                    print(f"❌ Error: {e}")

                # Save intermediate results
                if len(all_results) > 0:
                    results_df = pd.DataFrame(all_results)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    results_df.to_csv(f'results/full_table_v2_progress_{timestamp}.csv', index=False)

                # Rate limiting pause
                print("⏸️  Pausing 15s...")
                time.sleep(15)

    # Save final results
    if len(all_results) > 0:
        results_df = pd.DataFrame(all_results)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_file = f'results/full_table_v2_final_{timestamp}.csv'
        results_df.to_csv(final_file, index=False)

        print("\n" + "=" * 80)
        print("EXPERIMENTS COMPLETED")
        print("=" * 80)
        print(f"Total experiments: {len(all_results)}")
        print(f"Results saved to: {final_file}")
        print("\nSummary:")
        print(results_df[['Model', 'Strategy', 'Horizon (h)', 'MAE', 'RMSE', 'Overall']].to_string(index=False))
    else:
        print("\n❌ No results generated")

if __name__ == "__main__":
    main()

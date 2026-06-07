#!/usr/bin/env python3
"""
Retry only the failed experiments from the first run
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from replicate_experiments import *
import pandas as pd
from datetime import datetime

# Load existing results
existing_results = pd.read_csv('results/full_table_v2_final_20260416_114610.csv')
print(f"✅ Loaded {len(existing_results)} existing results\n")

# Configuration for failed experiments only
RETRY_EXPERIMENTS = [
    # Gemini failures
    {'provider': 'gemini', 'model': 'gemini-3-flash-preview', 'model_name': 'Gemini 3 Flash',
     'strategy': 'apbf', 'horizon': 48},
    {'provider': 'gemini', 'model': 'gemini-3-pro-preview', 'model_name': 'Gemini 3 Pro',
     'strategy': 'naive', 'horizon': 3},

    # Claude 4.5 Haiku (all NAIVE)
    {'provider': 'claude', 'model': 'claude-haiku-4-5', 'model_name': 'Claude 4.5 Haiku',
     'strategy': 'naive', 'horizon': 3},
    {'provider': 'claude', 'model': 'claude-haiku-4-5', 'model_name': 'Claude 4.5 Haiku',
     'strategy': 'naive', 'horizon': 6},
    {'provider': 'claude', 'model': 'claude-haiku-4-5', 'model_name': 'Claude 4.5 Haiku',
     'strategy': 'naive', 'horizon': 48},

    # Claude 4.5 Haiku (all APBF)
    {'provider': 'claude', 'model': 'claude-haiku-4-5', 'model_name': 'Claude 4.5 Haiku',
     'strategy': 'apbf', 'horizon': 3},
    {'provider': 'claude', 'model': 'claude-haiku-4-5', 'model_name': 'Claude 4.5 Haiku',
     'strategy': 'apbf', 'horizon': 6},
    {'provider': 'claude', 'model': 'claude-haiku-4-5', 'model_name': 'Claude 4.5 Haiku',
     'strategy': 'apbf', 'horizon': 48},

    # Claude 4.6 Sonnet (all strategies)
    {'provider': 'claude', 'model': 'claude-sonnet-4-6', 'model_name': 'Claude 4.6 Sonnet',
     'strategy': 'naive', 'horizon': 3},
    {'provider': 'claude', 'model': 'claude-sonnet-4-6', 'model_name': 'Claude 4.6 Sonnet',
     'strategy': 'naive', 'horizon': 6},
    {'provider': 'claude', 'model': 'claude-sonnet-4-6', 'model_name': 'Claude 4.6 Sonnet',
     'strategy': 'naive', 'horizon': 48},
    {'provider': 'claude', 'model': 'claude-sonnet-4-6', 'model_name': 'Claude 4.6 Sonnet',
     'strategy': 'advanced', 'horizon': 3},
    {'provider': 'claude', 'model': 'claude-sonnet-4-6', 'model_name': 'Claude 4.6 Sonnet',
     'strategy': 'advanced', 'horizon': 6},
    {'provider': 'claude', 'model': 'claude-sonnet-4-6', 'model_name': 'Claude 4.6 Sonnet',
     'strategy': 'advanced', 'horizon': 48},
    {'provider': 'claude', 'model': 'claude-sonnet-4-6', 'model_name': 'Claude 4.6 Sonnet',
     'strategy': 'apbf', 'horizon': 3},
    {'provider': 'claude', 'model': 'claude-sonnet-4-6', 'model_name': 'Claude 4.6 Sonnet',
     'strategy': 'apbf', 'horizon': 6},
    {'provider': 'claude', 'model': 'claude-sonnet-4-6', 'model_name': 'Claude 4.6 Sonnet',
     'strategy': 'apbf', 'horizon': 48},
]

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
        print("❌ Error: No Claude API key found.")
        return

    # Load data
    print("Loading dataset...")
    df = pd.read_csv('wtbdata_245days.csv')
    print(f"✅ Loaded {len(df)} rows\n")

    # Experiment configuration
    TURBINE_ID = 1
    BASE_DAY = 1

    # Results storage
    retry_results = []

    # Run retry experiments
    total_experiments = len(RETRY_EXPERIMENTS)

    for idx, exp in enumerate(RETRY_EXPERIMENTS):
        provider = exp['provider']
        model_id = exp['model']
        model_name = exp['model_name']
        strategy = exp['strategy']
        horizon = exp['horizon']

        current_exp = idx + 1
        print(f"\n[{current_exp}/{total_experiments}] Running: {model_name} | {strategy.upper()} | {horizon}h")
        print("-" * 80)

        # Get API key
        api_key = CLAUDE_API_KEY if provider == 'claude' else GEMINI_API_KEY

        # Setup client
        try:
            client, model_full_name = setup_model_client(provider, model_id, api_key)
        except Exception as e:
            print(f"❌ Failed to setup {model_name}: {e}")
            continue

        start_time = time.time()

        try:
            # Call appropriate strategy
            if strategy == 'naive':
                output = call_llm_naive(client, provider, model_full_name,
                                       df, TURBINE_ID, BASE_DAY, horizon)
            elif strategy == 'advanced':
                output = call_llm_advanced(client, provider, model_full_name,
                                          df, TURBINE_ID, BASE_DAY, horizon)
            elif strategy == 'apbf':
                output = call_llm_apbf(client, provider, model_full_name,
                                      df, TURBINE_ID, BASE_DAY, horizon,
                                      use_weather=True, max_retries=3)

            # Evaluate
            if output:
                eval_result = evaluate_forecast(df, TURBINE_ID, BASE_DAY, output, horizon)

                if eval_result:
                    retry_results.append({
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

        # Rate limiting pause
        if current_exp < total_experiments:
            print("⏸️  Pausing 15s...")
            time.sleep(15)

    # Save retry results
    if len(retry_results) > 0:
        retry_df = pd.DataFrame(retry_results)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        retry_file = f'results/retry_results_{timestamp}.csv'
        retry_df.to_csv(retry_file, index=False)

        # Merge with existing results
        combined_df = pd.concat([existing_results, retry_df], ignore_index=True)
        combined_file = f'results/full_table_v2_combined_{timestamp}.csv'
        combined_df.to_csv(combined_file, index=False)

        print("\n" + "=" * 80)
        print("RETRY COMPLETED")
        print("=" * 80)
        print(f"Retry experiments: {len(retry_results)}")
        print(f"Total experiments: {len(combined_df)}")
        print(f"Retry results saved to: {retry_file}")
        print(f"Combined results saved to: {combined_file}")
        print("\nNew results:")
        print(retry_df[['Model', 'Strategy', 'Horizon (h)', 'MAE', 'RMSE', 'Overall']].to_string(index=False))
    else:
        print("\n❌ No retry results generated")

if __name__ == "__main__":
    main()

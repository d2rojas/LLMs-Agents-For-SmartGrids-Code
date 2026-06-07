#!/usr/bin/env python3
"""List available Gemini models"""

import os
import google.generativeai as genai

# Configure API
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '***REMOVED***')
genai.configure(api_key=GEMINI_API_KEY)

print("Available Gemini models:")
print("=" * 80)

for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(f"\nModel: {model.name}")
        print(f"  Display name: {model.display_name}")
        print(f"  Description: {model.description}")
        print(f"  Supported methods: {model.supported_generation_methods}")

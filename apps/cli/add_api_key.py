#!/usr/bin/env python3
"""
Helper script to add API key to wikihub_config.json
Usage: python3 add_api_key.py <provider> <api_key>
Example: python3 add_api_key.py openrouter sk-or-v1-xxxxx
"""

import json
import sys
import os

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'wikihub_config.json')

def add_api_key(provider: str, api_key: str):
    """Add or update API key for a provider."""
    
    # Load existing config
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    else:
        config = {
            "providers": {},
            "system": {
                "defaultModel": "",
                "tokenBudget": 100000
            }
        }
    
    # Ensure providers section exists
    if 'providers' not in config:
        config['providers'] = {}
    
    # Update provider
    if provider not in config['providers']:
        config['providers'][provider] = {}
    
    config['providers'][provider]['apiKey'] = api_key
    config['providers'][provider]['status'] = 'configured'
    
    # Set default model for openrouter if not set
    if provider == 'openrouter' and 'defaultModel' not in config['providers'][provider]:
        config['providers'][provider]['defaultModel'] = 'openrouter/auto'
    
    # Save config
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ API key added for {provider}")
    print(f"   Config file: {CONFIG_FILE}")
    print(f"   Status: {config['providers'][provider]['status']}")
    
    # Mask key for display
    masked_key = api_key[:10] + '...' + api_key[-4:] if len(api_key) > 14 else '***'
    print(f"   API Key: {masked_key}")


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python3 add_api_key.py <provider> <api_key>")
        print("\nSupported providers:")
        print("  - openrouter")
        print("  - gemini")
        print("  - deepseek")
        print("  - qwen")
        print("  - custom")
        print("\nExample:")
        print("  python3 add_api_key.py openrouter sk-or-v1-xxxxx")
        sys.exit(1)
    
    provider = sys.argv[1].lower()
    api_key = sys.argv[2]
    
    valid_providers = ['openrouter', 'gemini', 'deepseek', 'qwen', 'custom']
    if provider not in valid_providers:
        print(f"❌ Invalid provider: {provider}")
        print(f"   Valid providers: {', '.join(valid_providers)}")
        sys.exit(1)
    
    add_api_key(provider, api_key)

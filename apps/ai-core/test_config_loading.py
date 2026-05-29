#!/usr/bin/env python3
"""
Test script to verify provider configuration loading from multiple sources.
Tests the updated ProviderConfig class that supports:
1. ~/.config/wikihub/providers.json.enc (encrypted)
2. ~/.config/wikihub/providers.json (plaintext)
3. apps/cli/wikihub_config.json (dashboard config)
"""

import os
import sys
import json

# Add project root to path
current_file = os.path.abspath(__file__)
if 'apps' in current_file and 'ai-core' in current_file:
    apps_idx = current_file.find('apps')
    project_root = current_file[:apps_idx].rstrip('/')
else:
    project_root = os.path.dirname(os.path.dirname(current_file))
sys.path.insert(0, project_root)

from infrastructure.encryption.provider_config import ProviderConfig

def test_config_loading():
    """Test provider configuration loading from all sources."""
    print("\n" + "=" * 70, file=sys.stderr)
    print("Testing Provider Configuration Loading", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    
    # Initialize ProviderConfig
    db_path = os.path.join(project_root, 'apps', 'cli', 'hub.db')
    config = ProviderConfig(db_path=db_path)
    
    print("\nConfiguration paths:", file=sys.stderr)
    print(f"  Encrypted: {config.encrypted_path}", file=sys.stderr)
    print(f"  Plaintext: {config.plaintext_path}", file=sys.stderr)
    print(f"  Dashboard: {config.dashboard_config_path}", file=sys.stderr)
    
    # Check which files exist
    print("\nFile existence:", file=sys.stderr)
    print(f"  Encrypted: {os.path.exists(config.encrypted_path)}", file=sys.stderr)
    print(f"  Plaintext: {os.path.exists(config.plaintext_path)}", file=sys.stderr)
    print(f"  Dashboard: {os.path.exists(config.dashboard_config_path) if config.dashboard_config_path else False}", file=sys.stderr)
    
    # Load providers
    print("\nLoading providers...", file=sys.stderr)
    providers = config.load_providers()
    
    if not providers:
        print("\n❌ No providers loaded!", file=sys.stderr)
        return False
    
    print(f"\n✅ Loaded {len(providers)} provider(s):", file=sys.stderr)
    for provider_name, provider_config in providers.items():
        api_key = provider_config.get('api_key', '')
        base_url = provider_config.get('base_url', '')
        models = provider_config.get('models', [])
        
        # Mask API key for security
        masked_key = api_key[:10] + '...' + api_key[-4:] if len(api_key) > 14 else '***'
        
        print(f"\n  Provider: {provider_name}", file=sys.stderr)
        print(f"    API Key: {masked_key}", file=sys.stderr)
        print(f"    Base URL: {base_url}", file=sys.stderr)
        print(f"    Models: {models}", file=sys.stderr)
    
    # Test validation
    print("\nValidating configuration...", file=sys.stderr)
    is_valid = config.validate_config()
    
    if is_valid:
        print("✅ Configuration is valid", file=sys.stderr)
    else:
        print("❌ Configuration validation failed", file=sys.stderr)
    
    return is_valid


def test_llm_router():
    """Test LLMRouter initialization with loaded config."""
    print("\n" + "=" * 70, file=sys.stderr)
    print("Testing LLMRouter Initialization", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    
    try:
        from llm.llm_router import LLMRouter
        
        db_path = os.path.join(project_root, 'apps', 'cli', 'hub.db')
        config = ProviderConfig(db_path=db_path)
        
        router = LLMRouter(config=config)
        success = router.initialize()
        
        if success:
            print("\n✅ LLMRouter initialized successfully", file=sys.stderr)
            print(f"   Available providers: {list(router.adapters.keys())}", file=sys.stderr)
            return True
        else:
            print("\n❌ LLMRouter initialization failed", file=sys.stderr)
            return False
    except Exception as e:
        print(f"\n❌ Error initializing LLMRouter: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


def show_dashboard_config():
    """Display current dashboard configuration."""
    print("\n" + "=" * 70, file=sys.stderr)
    print("Current Dashboard Configuration", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    
    dashboard_config_path = os.path.join(project_root, 'apps', 'cli', 'wikihub_config.json')
    
    if not os.path.exists(dashboard_config_path):
        print(f"\n❌ Dashboard config not found at: {dashboard_config_path}", file=sys.stderr)
        return
    
    try:
        with open(dashboard_config_path, 'r') as f:
            config = json.load(f)
        
        print(f"\nConfiguration file: {dashboard_config_path}", file=sys.stderr)
        print("\nProviders:", file=sys.stderr)
        
        for provider_name, provider_data in config.get('providers', {}).items():
            api_key = provider_data.get('apiKey', '')
            status = provider_data.get('status', 'unknown')
            default_model = provider_data.get('defaultModel', '')
            
            # Mask API key
            if api_key:
                masked_key = api_key[:10] + '...' + api_key[-4:] if len(api_key) > 14 else '***'
            else:
                masked_key = '(empty)'
            
            print(f"\n  {provider_name}:", file=sys.stderr)
            print(f"    Status: {status}", file=sys.stderr)
            print(f"    API Key: {masked_key}", file=sys.stderr)
            if default_model:
                print(f"    Default Model: {default_model}", file=sys.stderr)
        
        print("\nSystem:", file=sys.stderr)
        system = config.get('system', {})
        print(f"  Default Model: {system.get('defaultModel', '(not set)')}", file=sys.stderr)
        print(f"  Token Budget: {system.get('tokenBudget', 0)}", file=sys.stderr)
        
    except Exception as e:
        print(f"\n❌ Error reading dashboard config: {e}", file=sys.stderr)


if __name__ == '__main__':
    print("\n🔍 WikiHub Provider Configuration Test", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    
    # Show current dashboard config
    show_dashboard_config()
    
    # Test config loading
    config_ok = test_config_loading()
    
    # Test LLM router
    router_ok = test_llm_router()
    
    # Summary
    print("\n" + "=" * 70, file=sys.stderr)
    print("Test Summary", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(f"  Config Loading: {'✅ PASS' if config_ok else '❌ FAIL'}", file=sys.stderr)
    print(f"  LLM Router:     {'✅ PASS' if router_ok else '❌ FAIL'}", file=sys.stderr)
    
    if config_ok and router_ok:
        print("\n✅ All tests passed! System is ready to use.", file=sys.stderr)
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Check configuration.", file=sys.stderr)
        sys.exit(1)

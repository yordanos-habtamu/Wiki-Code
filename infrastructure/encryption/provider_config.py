"""
Secure provider configuration manager.
Handles loading, parsing, and decrypting provider credentials from:
1. ~/.config/wikihub/ (file-based config)
2. apps/cli/wikihub_config.json (dashboard config)
3. SQLite database (future: per-project API keys)
"""

import os
import sys
import json
import sqlite3
from typing import Dict, Any, Optional
from infrastructure.encryption.credential_encryptor import CredentialEncryptor


class ProviderConfig:
    """
    Manages provider configuration with encrypted credential storage.
    Supports: gemini, deepseek, qwen, openrouter, custom
    
    Configuration sources (in priority order):
    1. ~/.config/wikihub/providers.json.enc (encrypted, highest priority)
    2. ~/.config/wikihub/providers.json (plaintext)
    3. apps/cli/wikihub_config.json (dashboard config)
    4. SQLite database wiki_projects.target_model (model selection only)
    """
    
    DEFAULT_CONFIG_DIR = os.path.expanduser("~/.config/wikihub")
    ENCRYPTED_FILE = "providers.json.enc"
    PLAINTEXT_FILE = "providers.json"
    DASHBOARD_CONFIG_FILE = "wikihub_config.json"
    
    # Base URLs for each provider
    PROVIDER_BASE_URLS = {
        "gemini": "https://generativelanguage.googleapis.com/v1beta",
        "deepseek": "https://api.deepseek.com/v1",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "custom": "http://localhost:11434/v1"
    }
    
    def __init__(self, config_dir: Optional[str] = None, db_path: Optional[str] = None):
        """
        Initialize provider config manager.
        
        Args:
            config_dir: Directory for encrypted config files (default: ~/.config/wikihub)
            db_path: Path to SQLite database (default: apps/cli/hub.db)
        """
        self.config_dir = config_dir or self.DEFAULT_CONFIG_DIR
        self.encrypted_path = os.path.join(self.config_dir, self.ENCRYPTED_FILE)
        self.plaintext_path = os.path.join(self.config_dir, self.PLAINTEXT_FILE)
        
        # Determine dashboard config path
        if db_path:
            # If db_path is provided, assume dashboard config is in same directory
            db_dir = os.path.dirname(os.path.abspath(db_path))
            self.dashboard_config_path = os.path.join(db_dir, self.DASHBOARD_CONFIG_FILE)
        else:
            # Default to apps/cli/wikihub_config.json
            current_file = os.path.abspath(__file__)
            if 'infrastructure' in current_file:
                infra_idx = current_file.find('infrastructure')
                project_root = current_file[:infra_idx].rstrip('/')
                self.dashboard_config_path = os.path.join(project_root, 'apps', 'cli', self.DASHBOARD_CONFIG_FILE)
            else:
                self.dashboard_config_path = None
        
        self.db_path = db_path
        self.encryptor = CredentialEncryptor()
        self.providers: Dict[str, Any] = {}
        
        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)

    def load_providers(self) -> Dict[str, Any]:
        """
        Load provider configurations from multiple sources (priority order):
        1. Encrypted file (~/.config/wikihub/providers.json.enc)
        2. Plaintext file (~/.config/wikihub/providers.json)
        3. Dashboard config (apps/cli/wikihub_config.json)
        
        Returns:
            Dictionary of provider configurations with api_key, base_url, models
        """
        # Try encrypted file first (highest priority)
        if os.path.exists(self.encrypted_path):
            print(f"Loading encrypted provider config from {self.encrypted_path}", file=sys.stderr)
            plaintext = self.encryptor.decrypt_file(self.encrypted_path)
            if plaintext:
                self.providers = json.loads(plaintext)
                return self.providers
        
        # Try plaintext file second
        if os.path.exists(self.plaintext_path):
            print(f"Loading plaintext provider config from {self.plaintext_path}", file=sys.stderr)
            with open(self.plaintext_path, 'r') as f:
                self.providers = json.load(f)
            return self.providers
        
        # Try dashboard config third
        if self.dashboard_config_path and os.path.exists(self.dashboard_config_path):
            print(f"Loading dashboard provider config from {self.dashboard_config_path}", file=sys.stderr)
            try:
                with open(self.dashboard_config_path, 'r') as f:
                    dashboard_config = json.load(f)
                
                # Transform dashboard config format to provider config format
                self.providers = self._transform_dashboard_config(dashboard_config)
                
                if self.providers:
                    print(f"Loaded {len(self.providers)} provider(s) from dashboard config", file=sys.stderr)
                    return self.providers
            except Exception as e:
                print(f"Warning: Failed to load dashboard config: {e}", file=sys.stderr)
        
        print("Warning: No provider configuration found. Create providers.json in ~/.config/wikihub/ or configure via dashboard", file=sys.stderr)
        return {}
    
    def _transform_dashboard_config(self, dashboard_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform dashboard config format to provider config format.
        
        Dashboard format:
        {
          "providers": {
            "openrouter": {"apiKey": "...", "defaultModel": "...", "status": "configured"}
          }
        }
        
        Provider format:
        {
          "openrouter": {"api_key": "...", "base_url": "...", "models": [...]}
        }
        """
        providers = {}
        dashboard_providers = dashboard_config.get('providers', {})
        
        for provider_name, provider_data in dashboard_providers.items():
            api_key = provider_data.get('apiKey', '').strip()
            
            # Skip if no API key or status is not_configured
            if not api_key or provider_data.get('status') == 'not_configured':
                continue
            
            # Get base URL from defaults
            base_url = self.PROVIDER_BASE_URLS.get(provider_name, '')
            
            # Get default model if specified
            default_model = provider_data.get('defaultModel', '')
            models = [default_model] if default_model else []
            
            providers[provider_name] = {
                'api_key': api_key,
                'base_url': base_url,
                'models': models
            }
        
        return providers

    def save_providers(self, providers: Dict[str, Any], encrypt: bool = True) -> bool:
        """
        Save provider configurations with optional encryption.
        """
        self.providers = providers
        plaintext = json.dumps(providers, indent=2)
        
        if encrypt:
            # Write to temporary plaintext file first
            with open(self.plaintext_path, 'w') as f:
                f.write(plaintext)
            
            # Encrypt it
            success = self.encryptor.encrypt_file(self.plaintext_path, self.encrypted_path)
            
            # Remove plaintext file after encryption
            if success and os.path.exists(self.plaintext_path):
                os.remove(self.plaintext_path)
                print(f"Encrypted config saved to {self.encrypted_path}", file=sys.stderr)
            
            return success
        else:
            with open(self.plaintext_path, 'w') as f:
                f.write(plaintext)
            print(f"Plaintext config saved to {self.plaintext_path}", file=sys.stderr)
            return True

    def get_provider(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """
        Get configuration for a specific provider.
        """
        if not self.providers:
            self.load_providers()
        
        return self.providers.get(provider_name)

    def get_api_key(self, provider_name: str) -> Optional[str]:
        """
        Safely retrieve API key for a provider.
        Never logs or exposes the key value.
        """
        provider = self.get_provider(provider_name)
        if provider and "api_key" in provider:
            return provider["api_key"]
        return None

    def validate_config(self) -> bool:
        """
        Validate that at least one provider is configured.
        """
        if not self.providers:
            self.load_providers()
        
        if not self.providers:
            print("Error: No providers configured in providers.json", file=sys.stderr)
            return False
        
        # Check that each provider has required fields
        for name, config in self.providers.items():
            if "api_key" not in config:
                print(f"Warning: Provider '{name}' missing api_key", file=sys.stderr)
                return False
        
        print(f"Validated {len(self.providers)} provider(s) successfully", file=sys.stderr)
        return True

    def create_sample_config(self) -> Dict[str, Any]:
        """
        Create a sample configuration template.
        """
        sample = {
            "gemini": {
                "api_key": "YOUR_GEMINI_API_KEY",
                "base_url": "https://generativelanguage.googleapis.com/v1beta",
                "models": ["gemini-pro", "gemini-1.5-flash", "gemini-1.5-pro"]
            },
            "deepseek": {
                "api_key": "YOUR_DEEPSEEK_API_KEY",
                "base_url": "https://api.deepseek.com/v1",
                "models": ["deepseek-chat", "deepseek-coder"]
            },
            "qwen": {
                "api_key": "YOUR_QWEN_API_KEY",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "models": ["qwen-turbo", "qwen-plus", "qwen-max"]
            },
            "openrouter": {
                "api_key": "YOUR_OPENROUTER_API_KEY",
                "base_url": "https://openrouter.ai/api/v1",
                "models": ["openrouter/auto"]
            },
            "custom": {
                "api_key": "YOUR_CUSTOM_API_KEY",
                "base_url": "http://localhost:11434/v1",
                "models": ["llama3", "mistral", "custom-model"]
            }
        }
        
        return sample

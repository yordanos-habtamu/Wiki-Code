"""
Secure provider configuration manager.
Handles loading, parsing, and decrypting provider credentials from ~/.config/wikihub/
"""

import os
import sys
import json
from typing import Dict, Any, Optional
from infrastructure.encryption.credential_encryptor import CredentialEncryptor


class ProviderConfig:
    """
    Manages provider configuration with encrypted credential storage.
    Supports: gemini, deepseek, qwen, openrouter, custom
    """
    
    DEFAULT_CONFIG_DIR = os.path.expanduser("~/.config/wikihub")
    ENCRYPTED_FILE = "providers.json.enc"
    PLAINTEXT_FILE = "providers.json"
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize provider config manager.
        """
        self.config_dir = config_dir or self.DEFAULT_CONFIG_DIR
        self.encrypted_path = os.path.join(self.config_dir, self.ENCRYPTED_FILE)
        self.plaintext_path = os.path.join(self.config_dir, self.PLAINTEXT_FILE)
        self.encryptor = CredentialEncryptor()
        self.providers: Dict[str, Any] = {}
        
        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)

    def load_providers(self) -> Dict[str, Any]:
        """
        Load provider configurations from encrypted or plaintext file.
        Prefers encrypted file if available.
        """
        if os.path.exists(self.encrypted_path):
            print(f"Loading encrypted provider config from {self.encrypted_path}", file=sys.stderr)
            plaintext = self.encryptor.decrypt_file(self.encrypted_path)
            if plaintext:
                self.providers = json.loads(plaintext)
                return self.providers
        
        if os.path.exists(self.plaintext_path):
            print(f"Loading plaintext provider config from {self.plaintext_path}", file=sys.stderr)
            with open(self.plaintext_path, 'r') as f:
                self.providers = json.load(f)
            return self.providers
        
        print("Warning: No provider configuration found. Create providers.json in ~/.config/wikihub/", file=sys.stderr)
        return {}

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

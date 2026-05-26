"""
Test harness for LLMRouter and encrypted provider configuration.
Validates credential encryption, provider loading, and routing logic.
"""

import os
import sys
import json
import tempfile
import shutil

# Redirect stdout to stderr to enforce zero stdout pollution
sys.stdout = sys.stderr

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from infrastructure.encryption.credential_encryptor import CredentialEncryptor
from infrastructure.encryption.provider_config import ProviderConfig
import importlib.util

# Load llm_router module directly
llm_router_path = os.path.join(os.path.dirname(__file__), "llm", "llm_router.py")
spec = importlib.util.spec_from_file_location("llm_router", llm_router_path)
llm_router_module = importlib.util.module_from_spec(spec)
sys.modules["llm_router"] = llm_router_module
spec.loader.exec_module(llm_router_module)
LLMRouter = llm_router_module.LLMRouter
NormalizedResponse = llm_router_module.NormalizedResponse


def test_encryption():
    """Test credential encryption/decryption cycle."""
    print("\n=== Testing Credential Encryption ===", file=sys.stderr)
    
    # Create temporary directory for test
    test_dir = tempfile.mkdtemp()
    
    try:
        encryptor = CredentialEncryptor()
        
        # Test data encryption
        original = "test-api-key-12345"
        encrypted = encryptor.encrypt_data(original)
        decrypted = encryptor.decrypt_data(encrypted)
        
        assert decrypted == original, f"Decryption failed: {decrypted} != {original}"
        print(f"✓ Data encryption/decryption successful", file=sys.stderr)
        
        # Test file encryption
        plaintext_file = os.path.join(test_dir, "test_providers.json")
        encrypted_file = os.path.join(test_dir, "test_providers.json.enc")
        
        test_data = {
            "gemini": {
                "api_key": "test-gemini-key",
                "base_url": "https://test.api/v1"
            }
        }
        
        with open(plaintext_file, 'w') as f:
            json.dump(test_data, f)
        
        success = encryptor.encrypt_file(plaintext_file, encrypted_file)
        assert success, "File encryption failed"
        print(f"✓ File encryption successful", file=sys.stderr)
        
        # Verify decryption
        decrypted_text = encryptor.decrypt_file(encrypted_file)
        assert decrypted_text is not None, "File decryption returned None"
        
        decrypted_data = json.loads(decrypted_text)
        assert decrypted_data["gemini"]["api_key"] == "test-gemini-key"
        print(f"✓ File decryption successful", file=sys.stderr)
        
        print("✓ All encryption tests passed", file=sys.stderr)
        
    finally:
        # Cleanup
        shutil.rmtree(test_dir)


def test_provider_config():
    """Test provider configuration management."""
    print("\n=== Testing Provider Configuration ===", file=sys.stderr)
    
    # Create temporary config directory
    test_config_dir = tempfile.mkdtemp()
    
    try:
        config = ProviderConfig(config_dir=test_config_dir)
        
        # Test sample config creation
        sample = config.create_sample_config()
        assert "gemini" in sample
        assert "deepseek" in sample
        assert "qwen" in sample
        assert "openrouter" in sample
        assert "custom" in sample
        print(f"✓ Sample config contains all 5 providers", file=sys.stderr)
        
        # Test plaintext save/load
        config.save_providers(sample, encrypt=False)
        loaded = config.load_providers()
        assert len(loaded) == 5, f"Expected 5 providers, got {len(loaded)}"
        print(f"✓ Plaintext save/load successful", file=sys.stderr)
        
        # Test encrypted save/load
        config2 = ProviderConfig(config_dir=test_config_dir)
        config2.save_providers(sample, encrypt=True)
        
        # Verify encrypted file exists
        encrypted_path = os.path.join(test_config_dir, "providers.json.enc")
        assert os.path.exists(encrypted_path), "Encrypted file not created"
        print(f"✓ Encrypted file created", file=sys.stderr)
        
        # Load from encrypted file
        config3 = ProviderConfig(config_dir=test_config_dir)
        loaded_encrypted = config3.load_providers()
        assert len(loaded_encrypted) == 5, f"Expected 5 providers from encrypted, got {len(loaded_encrypted)}"
        print(f"✓ Encrypted save/load successful", file=sys.stderr)
        
        # Test provider retrieval
        gemini_config = config3.get_provider("gemini")
        assert gemini_config is not None
        assert "api_key" in gemini_config
        print(f"✓ Provider retrieval successful", file=sys.stderr)
        
        # Test validation
        config3.validate_config()
        print(f"✓ Config validation successful", file=sys.stderr)
        
        print("✓ All provider config tests passed", file=sys.stderr)
        
    finally:
        # Cleanup
        shutil.rmtree(test_config_dir)


def test_llm_router_initialization():
    """Test LLMRouter initialization without making actual API calls."""
    print("\n=== Testing LLMRouter Initialization ===", file=sys.stderr)
    
    # Create temporary config directory
    test_config_dir = tempfile.mkdtemp()
    
    try:
        # Create test provider config
        config = ProviderConfig(config_dir=test_config_dir)
        sample = config.create_sample_config()
        config.save_providers(sample, encrypt=False)
        
        # Initialize router with test config
        router = LLMRouter(config=config)
        success = router.initialize()
        
        assert success, "Router initialization failed"
        assert len(router.adapters) == 5, f"Expected 5 adapters, got {len(router.adapters)}"
        print(f"✓ Router initialized with {len(router.adapters)} providers", file=sys.stderr)
        
        # Test provider resolution
        provider, model = router._resolve_provider_and_model("gemini/gemini-pro")
        assert provider == "gemini"
        assert model == "gemini-pro"
        print(f"✓ Provider/model resolution: gemini/gemini-pro", file=sys.stderr)
        
        provider, model = router._resolve_provider_and_model("deepseek-chat")
        assert provider in ["deepseek", "gemini", "qwen", "openrouter", "custom"]
        print(f"✓ Model-only resolution: {provider}", file=sys.stderr)
        
        # Test error handling for invalid provider
        try:
            router._resolve_provider_and_model("invalid/model")
            print(f"✗ Should have raised error for invalid provider", file=sys.stderr)
        except:
            print(f"✓ Invalid provider correctly rejected", file=sys.stderr)
        
        print("✓ All LLMRouter initialization tests passed", file=sys.stderr)
        
    finally:
        # Cleanup
        shutil.rmtree(test_config_dir)


def test_normalized_response():
    """Test NormalizedResponse data structure."""
    print("\n=== Testing NormalizedResponse ===", file=sys.stderr)
    
    response = NormalizedResponse(
        content="Test response content",
        model_used="test-model",
        provider="test-provider",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        latency_ms=234.5,
        finish_reason="stop"
    )
    
    assert response.content == "Test response content"
    assert response.prompt_tokens == 100
    assert response.completion_tokens == 50
    assert response.total_tokens == 150
    assert response.latency_ms == 234.5
    assert response.provider == "test-provider"
    print(f"✓ NormalizedResponse structure validated", file=sys.stderr)
    
    # Test serialization
    response_dict = {
        "content": response.content,
        "model_used": response.model_used,
        "provider": response.provider,
        "prompt_tokens": response.prompt_tokens,
        "completion_tokens": response.completion_tokens,
        "total_tokens": response.total_tokens,
        "latency_ms": response.latency_ms,
        "finish_reason": response.finish_reason
    }
    
    assert response_dict["total_tokens"] == 150
    print(f"✓ NormalizedResponse serialization works", file=sys.stderr)
    
    print("✓ All NormalizedResponse tests passed", file=sys.stderr)


def main():
    print("=" * 70, file=sys.stderr)
    print("LLMRouter & Encrypted BYOK Configuration Test Suite", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    
    tests_passed = 0
    tests_failed = 0
    
    try:
        test_encryption()
        tests_passed += 1
    except Exception as e:
        print(f"✗ Encryption test failed: {e}", file=sys.stderr)
        tests_failed += 1
    
    try:
        test_provider_config()
        tests_passed += 1
    except Exception as e:
        print(f"✗ Provider config test failed: {e}", file=sys.stderr)
        tests_failed += 1
    
    try:
        test_llm_router_initialization()
        tests_passed += 1
    except Exception as e:
        print(f"✗ LLMRouter initialization test failed: {e}", file=sys.stderr)
        tests_failed += 1
    
    try:
        test_normalized_response()
        tests_passed += 1
    except Exception as e:
        print(f"✗ NormalizedResponse test failed: {e}", file=sys.stderr)
        tests_failed += 1
    
    print("\n" + "=" * 70, file=sys.stderr)
    print(f"Test Results: {tests_passed} passed, {tests_failed} failed", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    
    if tests_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

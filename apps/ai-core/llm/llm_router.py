"""
LLM Router - Unified provider abstraction layer.
Routes completion requests through standardized interface with provider decoupling.
"""

import os
import sys
import time
import json
import requests
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from infrastructure.encryption.provider_config import ProviderConfig


@dataclass
class NormalizedResponse:
    """
    Standardized response structure for all LLM provider completions.
    Ensures downstream agents work with a consistent contract regardless of provider.
    """
    content: str
    model_used: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    finish_reason: str = "stop"
    raw_response: Dict[str, Any] = field(default_factory=dict)


class ProviderAdapter:
    """
    Base adapter class for LLM providers.
    Each provider implements its own request/response transformation.
    """
    
    def __init__(self, provider_name: str, config: Dict[str, Any]):
        self.provider_name = provider_name
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "")
        self.models = config.get("models", [])

    def build_request(self, prompt: str, model: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        """Build provider-specific request payload."""
        raise NotImplementedError

    def parse_response(self, response: requests.Response, latency_ms: float) -> NormalizedResponse:
        """Parse provider-specific response into normalized format."""
        raise NotImplementedError


class GeminiAdapter(ProviderAdapter):
    """Google Gemini adapter."""
    
    def build_request(self, prompt: str, model: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }
        
        body = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": options.get("temperature", 0.7) if options else 0.7,
                "maxOutputTokens": options.get("max_tokens", 4096) if options else 4096
            }
        }
        
        return {"headers": headers, "body": body}

    def parse_response(self, response: requests.Response, latency_ms: float) -> NormalizedResponse:
        data = response.json()
        
        # Extract text from Gemini response format
        content = ""
        if "candidates" in data and len(data["candidates"]) > 0:
            candidate = data["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                content = candidate["content"]["parts"][0].get("text", "")
        
        # Extract token usage if available
        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)
        total_tokens = usage.get("totalTokenCount", 0)
        
        return NormalizedResponse(
            content=content,
            model_used="gemini",
            provider="gemini",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            finish_reason="stop",
            raw_response=data
        )


class OpenAICompatibleAdapter(ProviderAdapter):
    """
    Adapter for OpenAI-compatible APIs (DeepSeek, Qwen, OpenRouter, Custom).
    Uses the standard OpenAI chat completions format.
    """
    
    def build_request(self, prompt: str, model: str, options: Optional[Dict] = None) -> Dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": options.get("temperature", 0.7) if options else 0.7,
            "max_tokens": options.get("max_tokens", 4096) if options else 4096
        }
        
        return {"headers": headers, "body": body}

    def parse_response(self, response: requests.Response, latency_ms: float) -> NormalizedResponse:
        data = response.json()
        
        # Extract text from OpenAI-compatible response format
        content = ""
        finish_reason = "stop"
        if "choices" in data and len(data["choices"]) > 0:
            choice = data["choices"][0]
            if "message" in choice:
                content = choice["message"].get("content", "")
            finish_reason = choice.get("finish_reason", "stop")
        
        # Extract token usage if available
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)
        
        return NormalizedResponse(
            content=content,
            model_used=data.get("model", "unknown"),
            provider=self.provider_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            finish_reason=finish_reason,
            raw_response=data
        )


class LLMRouter:
    """
    Unified LLM routing layer.
    Agents must use this interface - never import provider SDKs directly.
    """
    
    PROVIDER_ADAPTERS = {
        "gemini": GeminiAdapter,
        "deepseek": OpenAICompatibleAdapter,
        "qwen": OpenAICompatibleAdapter,
        "openrouter": OpenAICompatibleAdapter,
        "custom": OpenAICompatibleAdapter
    }
    
    def __init__(self, config: Optional[ProviderConfig] = None):
        """
        Initialize the LLM router with provider configuration.
        """
        self.config = config or ProviderConfig()
        self.adapters: Dict[str, ProviderAdapter] = {}
        self._initialized = False

    def initialize(self) -> bool:
        """
        Load provider configurations and initialize adapters.
        Must be called before making completion requests.
        """
        if self._initialized:
            return True
        
        providers = self.config.load_providers()
        if not providers:
            print("Error: No providers configured. Cannot initialize LLMRouter.", file=sys.stderr)
            return False
        
        for provider_name, provider_config in providers.items():
            if provider_name in self.PROVIDER_ADAPTERS:
                adapter_class = self.PROVIDER_ADAPTERS[provider_name]
                self.adapters[provider_name] = adapter_class(provider_name, provider_config)
                print(f"Initialized provider adapter: {provider_name}", file=sys.stderr)
            else:
                print(f"Warning: Unknown provider '{provider_name}', skipping", file=sys.stderr)
        
        self._initialized = True
        print(f"LLMRouter initialized with {len(self.adapters)} provider(s)", file=sys.stderr)
        return True

    def _resolve_provider_and_model(self, model_id: str) -> tuple:
        """
        Parse model_id string to extract provider and model name.
        Format: "provider/model" or just "model" (uses first available provider)
        """
        if "/" in model_id:
            parts = model_id.split("/", 1)
            provider = parts[0]
            model = parts[1]
            return provider, model
        
        # Try to infer provider from available adapters
        for provider_name, adapter in self.adapters.items():
            if model_id in adapter.models or not adapter.models:
                return provider_name, model_id
        
        # Default to first available provider
        if self.adapters:
            first_provider = list(self.adapters.keys())[0]
            return first_provider, model_id
        
        return None, model_id

    def complete(self, prompt: str, model_id: str, options: Optional[Dict] = None) -> NormalizedResponse:
        """
        Main completion interface.
        
        Args:
            prompt: The text prompt to send to the LLM
            model_id: Model identifier (format: "provider/model" or just "model")
            options: Optional parameters (temperature, max_tokens, etc.)
        
        Returns:
            NormalizedResponse with standardized structure
        """
        if not self._initialized:
            if not self.initialize():
                raise RuntimeError("LLMRouter not initialized and no providers configured")
        
        # Resolve provider and model
        provider_name, model = self._resolve_provider_and_model(model_id)
        
        if provider_name not in self.adapters:
            raise ValueError(
                f"Provider '{provider_name}' not available. "
                f"Available: {list(self.adapters.keys())}"
            )
        
        adapter = self.adapters[provider_name]
        
        # Build request
        request_data = adapter.build_request(prompt, model, options)
        
        # Determine endpoint URL
        if provider_name == "gemini":
            url = f"{adapter.base_url}/models/{model}:generateContent"
        else:
            url = f"{adapter.base_url}/chat/completions"
        
        # Execute request with timing
        start_time = time.time()
        try:
            response = requests.post(
                url,
                headers=request_data["headers"],
                json=request_data["body"],
                timeout=60
            )
            latency_ms = (time.time() - start_time) * 1000
            
            # Check for errors
            if response.status_code != 200:
                error_msg = f"Provider {provider_name} returned error {response.status_code}: {response.text}"
                print(f"Error in LLMRouter.complete: {error_msg}", file=sys.stderr)
                raise RuntimeError(error_msg)
            
            # Parse response
            normalized = adapter.parse_response(response, latency_ms)
            
            print(
                f"LLMRouter.complete [{provider_name}/{model}] "
                f"latency={latency_ms:.0f}ms tokens={normalized.total_tokens}",
                file=sys.stderr
            )
            
            return normalized
            
        except requests.exceptions.RequestException as e:
            latency_ms = (time.time() - start_time) * 1000
            print(f"Error in LLMRouter.complete: Request failed - {e}", file=sys.stderr)
            raise
        except Exception as e:
            print(f"Error in LLMRouter.complete: {e}", file=sys.stderr)
            raise

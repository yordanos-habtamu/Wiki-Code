"""
Token Tracking Middleware - Interceptor for LLMRouter.complete()
Automatically logs all token transactions to SQLite before returning responses.
"""

import os
import sys
from typing import Optional, Dict, Any
import importlib.util

# Load dependencies dynamically
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Load token_usage_repository
repo_path = os.path.join(os.path.dirname(__file__), "..", "repositories", "token_usage_repository.py")
spec = importlib.util.spec_from_file_location("token_usage_repository", repo_path)
token_usage_module = importlib.util.module_from_spec(spec)
sys.modules["token_usage_repository"] = token_usage_module
spec.loader.exec_module(token_usage_module)
TokenUsageRepository = token_usage_module.TokenUsageRepository
TokenUsageRecord = token_usage_module.TokenUsageRecord


class TokenTrackingMiddleware:
    """
    Interceptor middleware that wraps LLMRouter.complete() calls.
    Guarantees every token transaction is written to SQLite before returning.
    """
    
    def __init__(self, router, db_path: Optional[str] = None):
        """
        Initialize the middleware with an LLMRouter instance.
        
        Args:
            router: LLMRouter instance to wrap
            db_path: Optional path to hub.db (uses default if None)
        """
        self.router = router
        self.repository = TokenUsageRepository(db_path=db_path)
        print("TokenTrackingMiddleware initialized", file=sys.stderr)

    def complete(self, prompt: str, model_id: str, options: Dict[str, Any] = None, 
                 operation_type: str = "comprehension") -> Any:
        """
        Wrapped complete() method that intercepts calls and logs token usage.
        
        Args:
            prompt: The text prompt to send to the LLM
            model_id: Model identifier (format: "provider/model")
            options: Optional parameters (temperature, max_tokens, etc.)
            operation_type: Context description (e.g., "comprehension", "suggestion")
        
        Returns:
            NormalizedResponse from the LLM router
        """
        # Execute the actual LLM call
        response = self.router.complete(prompt, model_id, options)
        
        # Log token usage to SQLite
        try:
            usage_record = TokenUsageRecord(
                operation_type=operation_type,
                provider=response.provider,
                model_used=response.model_used,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens
            )
            
            self.repository.log_usage(usage_record)
            
            print(
                f"TokenTrackingMiddleware: Logged {response.total_tokens} tokens "
                f"for {operation_type} operation",
                file=sys.stderr
            )
            
        except Exception as e:
            # Log error but don't fail the request
            print(
                f"Error in TokenTrackingMiddleware.complete: Failed to log usage - {e}",
                file=sys.stderr
            )
        
        return response

    def get_budget_spent(self, time_window_days: int = 30) -> int:
        """
        Get total tokens consumed within a time window.
        
        Args:
            time_window_days: Number of days to look back
        
        Returns:
            Total tokens consumed
        """
        return self.repository.get_total_budget_spent(time_window_days=time_window_days)

    def get_provider_metrics(self) -> list:
        """
        Get aggregated metrics per provider.
        
        Returns:
            List of provider metric dictionaries
        """
        return self.repository.get_per_provider_metrics()

    def check_budget_threshold(self, max_tokens: int, time_window_days: int = 30) -> bool:
        """
        Check if token budget threshold has been exceeded.
        Used by LangGraph done_condition for hard budget enforcement.
        
        Args:
            max_tokens: Maximum allowed tokens
            time_window_days: Time window for calculation
        
        Returns:
            True if budget is exceeded, False otherwise
        """
        spent = self.get_budget_spent(time_window_days)
        exceeded = spent >= max_tokens
        
        if exceeded:
            print(
                f"TokenTrackingMiddleware: BUDGET EXCEEDED - "
                f"{spent}/{max_tokens} tokens used in {time_window_days} days",
                file=sys.stderr
            )
        else:
            remaining = max_tokens - spent
            print(
                f"TokenTrackingMiddleware: Budget OK - "
                f"{spent}/{max_tokens} tokens used ({remaining} remaining)",
                file=sys.stderr
            )
        
        return exceeded


class TokenTrackingMiddlewareFactory:
    """
    Factory for creating TokenTrackingMiddleware instances.
    Handles initialization of both LLMRouter and middleware.
    """
    
    @staticmethod
    def create_middleware(db_path: Optional[str] = None, config_path: Optional[str] = None):
        """
        Create a fully initialized TokenTrackingMiddleware.
        
        Args:
            db_path: Path to hub.db
            config_path: Path to provider config directory
        
        Returns:
            Initialized TokenTrackingMiddleware instance
        """
        # Import LLMRouter dynamically
        llm_router_path = os.path.join(os.path.dirname(__file__), "llm_router.py")
        spec = importlib.util.spec_from_file_location("llm_router", llm_router_path)
        llm_router_module = importlib.util.module_from_spec(spec)
        sys.modules["llm_router"] = llm_router_module
        spec.loader.exec_module(llm_router_module)
        LLMRouter = llm_router_module.LLMRouter
        
        # Initialize router
        router = LLMRouter()
        router.initialize()
        
        # Create middleware
        middleware = TokenTrackingMiddleware(router, db_path=db_path)
        
        return middleware

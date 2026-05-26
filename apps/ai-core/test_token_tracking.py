"""
Test harness for Token Tracking Middleware and Repository.
Validates token usage logging, budget tracking, and provider metrics.
"""

import os
import sys
import json
import tempfile
import shutil
import sqlite3
from datetime import datetime, timedelta

# Redirect stdout to stderr to enforce zero stdout pollution
sys.stdout = sys.stderr

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load modules dynamically
import importlib.util

# Load token_usage_repository
repo_path = os.path.join(os.path.dirname(__file__), "repositories", "token_usage_repository.py")
spec = importlib.util.spec_from_file_location("token_usage_repository", repo_path)
token_usage_module = importlib.util.module_from_spec(spec)
sys.modules["token_usage_repository"] = token_usage_module
spec.loader.exec_module(token_usage_module)
TokenUsageRepository = token_usage_module.TokenUsageRepository
TokenUsageRecord = token_usage_module.TokenUsageRecord

# Load token tracking middleware
middleware_path = os.path.join(os.path.dirname(__file__), "services", "token_tracking_middleware.py")
spec2 = importlib.util.spec_from_file_location("token_tracking_middleware", middleware_path)
middleware_module = importlib.util.module_from_spec(spec2)
sys.modules["token_tracking_middleware"] = middleware_module
spec2.loader.exec_module(middleware_module)
TokenTrackingMiddleware = middleware_module.TokenTrackingMiddleware


def create_test_database(db_path: str):
    """Create a test SQLite database with required schema."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create files table (required by ProjectRepository)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            relative_path TEXT PRIMARY KEY,
            language TEXT NOT NULL,
            last_sync TEXT NOT NULL,
            entity_count INTEGER DEFAULT 0,
            file_hash TEXT NOT NULL,
            file_size INTEGER NOT NULL
        )
    """)
    
    # Create symbols table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            start_line INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            signature TEXT,
            FOREIGN KEY (file_path) REFERENCES files(relative_path)
        )
    """)
    
    # Create dependencies table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dependencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL,
            import_path TEXT NOT NULL,
            FOREIGN KEY (source_file) REFERENCES files(relative_path)
        )
    """)
    
    conn.commit()
    conn.close()


def test_token_usage_repository():
    """Test TokenUsageRepository CRUD operations."""
    print("\n=== Testing TokenUsageRepository ===", file=sys.stderr)
    
    # Create temporary database
    test_dir = tempfile.mkdtemp()
    db_path = os.path.join(test_dir, "test_hub.db")
    
    try:
        # Initialize database
        create_test_database(db_path)
        
        # Initialize repository
        repo = TokenUsageRepository(db_path=db_path)
        
        # Test 1: Log single usage record
        record1 = TokenUsageRecord(
            operation_type="comprehension",
            provider="gemini",
            model_used="gemini-pro",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        repo.log_usage(record1)
        print("✓ Logged single usage record", file=sys.stderr)
        
        # Test 2: Log multiple records
        records = [
            TokenUsageRecord("suggestion", "deepseek", "deepseek-chat", 200, 100, 300),
            TokenUsageRecord("comprehension", "gemini", "gemini-1.5-flash", 150, 75, 225),
            TokenUsageRecord("test_ping", "qwen", "qwen-turbo", 50, 25, 75),
        ]
        
        for record in records:
            repo.log_usage(record)
        
        print("✓ Logged multiple usage records", file=sys.stderr)
        
        # Test 3: Get total budget spent
        total = repo.get_total_budget_spent(time_window_days=30)
        assert total == 750, f"Expected 750 tokens, got {total}"
        print(f"✓ Total budget spent: {total} tokens", file=sys.stderr)
        
        # Test 4: Get per-provider metrics
        metrics = repo.get_per_provider_metrics()
        assert len(metrics) == 3, f"Expected 3 providers, got {len(metrics)}"
        
        # Verify gemini metrics
        gemini_metrics = next((m for m in metrics if m["provider"] == "gemini"), None)
        assert gemini_metrics is not None
        assert gemini_metrics["request_count"] == 2
        assert gemini_metrics["total_tokens"] == 375
        print(f"✓ Provider metrics: {len(metrics)} providers tracked", file=sys.stderr)
        
        # Test 5: Get recent usage
        recent = repo.get_recent_usage(limit=2)
        assert len(recent) == 2, f"Expected 2 recent records, got {len(recent)}"
        print(f"✓ Recent usage retrieval works", file=sys.stderr)
        
        # Test 6: Clear old data
        # Insert an old record
        old_record = TokenUsageRecord(
            operation_type="old_test",
            provider="custom",
            model_used="old-model",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            timestamp=(datetime.utcnow() - timedelta(days=60)).isoformat()
        )
        repo.log_usage(old_record)
        
        # Clear records older than 30 days
        deleted = repo.clear_usage_data(older_than_days=30)
        assert deleted == 1, f"Expected 1 deleted record, got {deleted}"
        print(f"✓ Cleared {deleted} old record(s)", file=sys.stderr)
        
        # Verify remaining records
        remaining = repo.get_recent_usage(limit=100)
        assert len(remaining) == 4, f"Expected 4 remaining records, got {len(remaining)}"
        print(f"✓ {len(remaining)} records remaining after cleanup", file=sys.stderr)
        
        print("✓ All TokenUsageRepository tests passed", file=sys.stderr)
        
    finally:
        shutil.rmtree(test_dir)


class MockRouter:
    """Mock LLMRouter for testing middleware without actual API calls."""
    
    def __init__(self):
        self.call_count = 0
    
    def complete(self, prompt: str, model_id: str, options: dict = None):
        """Mock complete method that returns a fake NormalizedResponse."""
        self.call_count += 1
        
        # Create a mock response object
        class MockResponse:
            def __init__(self):
                self.content = "Mock response content"
                self.model_used = "mock-model"
                self.provider = "mock-provider"
                self.prompt_tokens = 100
                self.completion_tokens = 50
                self.total_tokens = 150
                self.latency_ms = 123.4
                self.finish_reason = "stop"
                self.raw_response = {}
        
        return MockResponse()


def test_token_tracking_middleware():
    """Test TokenTrackingMiddleware interception and logging."""
    print("\n=== Testing TokenTrackingMiddleware ===", file=sys.stderr)
    
    # Create temporary database
    test_dir = tempfile.mkdtemp()
    db_path = os.path.join(test_dir, "test_hub.db")
    
    try:
        # Initialize database
        create_test_database(db_path)
        
        # Create mock router
        mock_router = MockRouter()
        
        # Initialize middleware
        middleware = TokenTrackingMiddleware(mock_router, db_path=db_path)
        
        # Test 1: Intercept complete() call
        response = middleware.complete(
            prompt="Test prompt",
            model_id="mock/test-model",
            operation_type="comprehension"
        )
        
        assert response.total_tokens == 150
        assert mock_router.call_count == 1
        print("✓ Middleware intercepted complete() call", file=sys.stderr)
        
        # Test 2: Verify usage was logged
        repo = TokenUsageRepository(db_path=db_path)
        recent = repo.get_recent_usage(limit=1)
        assert len(recent) == 1
        assert recent[0]["operation_type"] == "comprehension"
        assert recent[0]["provider"] == "mock-provider"
        assert recent[0]["total_tokens"] == 150
        print("✓ Usage automatically logged to SQLite", file=sys.stderr)
        
        # Test 3: Multiple operations with different types
        middleware.complete("Prompt 2", "mock/model", operation_type="suggestion")
        middleware.complete("Prompt 3", "mock/model", operation_type="test_ping")
        
        total = repo.get_total_budget_spent(time_window_days=30)
        assert total == 450, f"Expected 450 tokens, got {total}"
        print(f"✓ Multiple operations tracked: {total} total tokens", file=sys.stderr)
        
        # Test 4: Budget threshold check
        exceeded = middleware.check_budget_threshold(max_tokens=1000, time_window_days=30)
        assert not exceeded, "Budget should not be exceeded"
        print("✓ Budget threshold check (under limit)", file=sys.stderr)
        
        # Test 5: Budget exceeded scenario
        exceeded = middleware.check_budget_threshold(max_tokens=400, time_window_days=30)
        assert exceeded, "Budget should be exceeded"
        print("✓ Budget threshold check (over limit)", file=sys.stderr)
        
        # Test 6: Provider metrics aggregation
        metrics = middleware.get_provider_metrics()
        assert len(metrics) == 1
        assert metrics[0]["provider"] == "mock-provider"
        assert metrics[0]["request_count"] == 3
        assert metrics[0]["total_tokens"] == 450
        print(f"✓ Provider metrics aggregation works", file=sys.stderr)
        
        print("✓ All TokenTrackingMiddleware tests passed", file=sys.stderr)
        
    finally:
        shutil.rmtree(test_dir)


def test_token_usage_record():
    """Test TokenUsageRecord data structure."""
    print("\n=== Testing TokenUsageRecord ===", file=sys.stderr)
    
    # Test 1: Auto-generated timestamp
    record1 = TokenUsageRecord(
        operation_type="test",
        provider="test-provider",
        model_used="test-model",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150
    )
    assert record1.timestamp is not None
    print(f"✓ Auto-generated timestamp: {record1.timestamp}", file=sys.stderr)
    
    # Test 2: Custom timestamp
    custom_time = "2026-05-20T12:00:00"
    record2 = TokenUsageRecord(
        operation_type="test",
        provider="test-provider",
        model_used="test-model",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        timestamp=custom_time
    )
    assert record2.timestamp == custom_time
    print(f"✓ Custom timestamp accepted", file=sys.stderr)
    
    # Test 3: Data integrity
    assert record1.prompt_tokens == 100
    assert record1.completion_tokens == 50
    assert record1.total_tokens == 150
    print("✓ Data structure integrity validated", file=sys.stderr)
    
    print("✓ All TokenUsageRecord tests passed", file=sys.stderr)


def main():
    print("=" * 70, file=sys.stderr)
    print("Token Tracking Middleware & Repository Test Suite", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    
    tests_passed = 0
    tests_failed = 0
    
    try:
        test_token_usage_record()
        tests_passed += 1
    except Exception as e:
        print(f"✗ TokenUsageRecord test failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        tests_failed += 1
    
    try:
        test_token_usage_repository()
        tests_passed += 1
    except Exception as e:
        print(f"✗ TokenUsageRepository test failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        tests_failed += 1
    
    try:
        test_token_tracking_middleware()
        tests_passed += 1
    except Exception as e:
        print(f"✗ TokenTrackingMiddleware test failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        tests_failed += 1
    
    print("\n" + "=" * 70, file=sys.stderr)
    print(f"Test Results: {tests_passed} passed, {tests_failed} failed", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    
    if tests_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

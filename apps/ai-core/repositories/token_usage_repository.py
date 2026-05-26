"""
Token Usage Repository - Encapsulated SQLite persistence layer for token tracking.
Provides safe database writes for token consumption metrics.
"""

import sqlite3
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class TokenUsageRecord:
    """
    Normalized token usage record for database insertion.
    """
    operation_type: str  # e.g., "comprehension", "suggestion", "test_ping"
    provider: str        # e.g., "gemini", "deepseek"
    model_used: str      # e.g., "gemini-pro"
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    timestamp: Optional[str] = None  # ISO-8601 format
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()


class TokenUsageRepository:
    """
    Repository pattern implementation for token usage tracking.
    All SQL operations encapsulated here - no direct SQL in agents/services.
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize repository connection.
        Falls back to default hub.db location if not specified.
        """
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(base_dir, "cli", "hub.db")
        
        self.db_path = db_path
        
        # Verify database exists
        if not os.path.exists(self.db_path):
            print(f"Warning from TokenUsageRepository: Database file '{self.db_path}' does not exist yet.", file=sys.stderr)
        
        # Ensure token_usage table exists
        self._ensure_table()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a fresh thread-safe connection to the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self):
        """Create token_usage table if it doesn't exist."""
        if not os.path.exists(self.db_path):
            print("Warning: Cannot create token_usage table - database file doesn't exist", file=sys.stderr)
            return
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_type TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model_used TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.commit()
            print("TokenUsageRepository: token_usage table verified/created", file=sys.stderr)
        except Exception as e:
            print(f"Error in TokenUsageRepository._ensure_table: {e}", file=sys.stderr)
            raise
        finally:
            conn.close()

    def log_usage(self, usage_record: TokenUsageRecord) -> None:
        """
        Inserts a normalized token record directly into SQLite.
        
        Args:
            usage_record: TokenUsageRecord with all required fields
        """
        if not os.path.exists(self.db_path):
            print(f"Error: Cannot log usage - database file '{self.db_path}' doesn't exist", file=sys.stderr)
            return
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO token_usage 
                (operation_type, provider, model_used, prompt_tokens, completion_tokens, total_tokens, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                usage_record.operation_type,
                usage_record.provider,
                usage_record.model_used,
                usage_record.prompt_tokens,
                usage_record.completion_tokens,
                usage_record.total_tokens,
                usage_record.timestamp
            ))
            conn.commit()
            print(
                f"TokenUsageRepository: Logged {usage_record.total_tokens} tokens "
                f"({usage_record.provider}/{usage_record.model_used})",
                file=sys.stderr
            )
        except Exception as e:
            print(f"Error in TokenUsageRepository.log_usage: {e}", file=sys.stderr)
            raise
        finally:
            conn.close()

    def get_total_budget_spent(self, project_id: str = None, time_window_days: int = 30) -> int:
        """
        Aggregates cumulative token spend for budget threshold verification.
        
        Args:
            project_id: Optional project identifier (not used in v1, reserved for future)
            time_window_days: Number of days to look back (default: 30)
        
        Returns:
            Total tokens consumed within the time window
        """
        if not os.path.exists(self.db_path):
            return 0
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Calculate cutoff timestamp
            cutoff_time = (datetime.utcnow() - timedelta(days=time_window_days)).isoformat()
            
            cursor.execute("""
                SELECT COALESCE(SUM(total_tokens), 0) as total_spent
                FROM token_usage
                WHERE timestamp >= ?
            """, (cutoff_time,))
            
            result = cursor.fetchone()
            total_spent = result["total_spent"] if result else 0
            
            print(
                f"TokenUsageRepository: Total budget spent in {time_window_days} days: {total_spent} tokens",
                file=sys.stderr
            )
            
            return total_spent
            
        except Exception as e:
            print(f"Error in TokenUsageRepository.get_total_budget_spent: {e}", file=sys.stderr)
            return 0
        finally:
            conn.close()

    def get_per_provider_metrics(self) -> List[Dict[str, Any]]:
        """
        Aggregates metrics grouped by provider for dashboard delivery.
        
        Returns:
            List of dictionaries with provider-level aggregations
        """
        if not os.path.exists(self.db_path):
            return []
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    provider,
                    COUNT(*) as request_count,
                    SUM(prompt_tokens) as total_prompt_tokens,
                    SUM(completion_tokens) as total_completion_tokens,
                    SUM(total_tokens) as total_tokens,
                    AVG(total_tokens) as avg_tokens_per_request,
                    MIN(timestamp) as first_usage,
                    MAX(timestamp) as last_usage
                FROM token_usage
                GROUP BY provider
                ORDER BY total_tokens DESC
            """)
            
            rows = cursor.fetchall()
            metrics = [dict(row) for row in rows]
            
            print(
                f"TokenUsageRepository: Retrieved metrics for {len(metrics)} provider(s)",
                file=sys.stderr
            )
            
            return metrics
            
        except Exception as e:
            print(f"Error in TokenUsageRepository.get_per_provider_metrics: {e}", file=sys.stderr)
            return []
        finally:
            conn.close()

    def get_recent_usage(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieve recent token usage records for auditing/debugging.
        
        Args:
            limit: Maximum number of records to return
        
        Returns:
            List of recent usage records
        """
        if not os.path.exists(self.db_path):
            return []
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT *
                FROM token_usage
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
            
        except Exception as e:
            print(f"Error in TokenUsageRepository.get_recent_usage: {e}", file=sys.stderr)
            return []
        finally:
            conn.close()

    def clear_usage_data(self, older_than_days: int = None) -> int:
        """
        Clear usage data, optionally only records older than specified days.
        
        Args:
            older_than_days: If provided, only delete records older than this
        
        Returns:
            Number of records deleted
        """
        if not os.path.exists(self.db_path):
            return 0
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            if older_than_days:
                cutoff_time = (datetime.utcnow() - timedelta(days=older_than_days)).isoformat()
                cursor.execute("DELETE FROM token_usage WHERE timestamp < ?", (cutoff_time,))
            else:
                cursor.execute("DELETE FROM token_usage")
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            print(
                f"TokenUsageRepository: Cleared {deleted_count} usage records",
                file=sys.stderr
            )
            
            return deleted_count
            
        except Exception as e:
            print(f"Error in TokenUsageRepository.clear_usage_data: {e}", file=sys.stderr)
            return 0
        finally:
            conn.close()

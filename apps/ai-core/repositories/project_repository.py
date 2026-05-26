import sqlite3
import os
import sys
from typing import List, Dict, Any

class ProjectRepository:
    def __init__(self, db_path: str = None):
        """
        Initializes the repository connection.
        If db_path is not specified, it falls back to the default hub.db location inside apps/cli/
        """
        if db_path is None:
            # Fallback to the standard monorepo path
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(base_dir, "cli", "hub.db")
        
        self.db_path = db_path
        
        # Verify db_path exists, log to stderr
        if not os.path.exists(self.db_path):
            print(f"Warning from ProjectRepository: Database file '{self.db_path}' does not exist yet.", file=sys.stderr)

    def _get_connection(self) -> sqlite3.Connection:
        """Helper to get a fresh thread-safe connection to the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_all_files(self) -> List[Dict[str, Any]]:
        """
        Extracts all tracked source file rows from the SQLite database.
        """
        if not os.path.exists(self.db_path):
            return []
            
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT relative_path, language, file_hash, file_size FROM files")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"Error in ProjectRepository.get_all_files: {e}", file=sys.stderr)
            return []
        finally:
            conn.close()

    def get_symbols_for_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extracts all symbols (functions, structs, classes) associated with a target file path.
        """
        if not os.path.exists(self.db_path):
            return []

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, kind, start_line, end_line, signature FROM symbols WHERE file_path = ?", 
                (file_path,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"Error in ProjectRepository.get_symbols_for_file for '{file_path}': {e}", file=sys.stderr)
            return []
        finally:
            conn.close()

    def get_dependencies_for_file(self, file_path: str) -> List[str]:
        """
        Extracts all import/dependency mappings for a target file path.
        """
        if not os.path.exists(self.db_path):
            return []

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT import_path FROM dependencies WHERE source_file = ?", 
                (file_path,)
            )
            rows = cursor.fetchall()
            return [row["import_path"] for row in rows]
        except Exception as e:
            print(f"Error in ProjectRepository.get_dependencies_for_file for '{file_path}': {e}", file=sys.stderr)
            return []
        finally:
            conn.close()

    def get_dependents_for_file(self, target_file: str) -> List[Dict[str, Any]]:
        """
        Find all files that depend ON the target file (reverse dependency lookup).
        
        Args:
            target_file: The file path to find dependents for
        
        Returns:
            List of dictionaries with 'source_file' and 'language' keys
        """
        if not os.path.exists(self.db_path):
            return []

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Find all files that import the target file
            cursor.execute(
                """SELECT DISTINCT d.source_file, f.language 
                   FROM dependencies d
                   LEFT JOIN files f ON d.source_file = f.relative_path
                   WHERE d.import_path = ?""",
                (target_file,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"Error in ProjectRepository.get_dependents_for_file for '{target_file}': {e}", file=sys.stderr)
            return []
        finally:
            conn.close()

#!/usr/bin/env python3
"""
WikiHub Git Repository Extraction Engine
Provides branch discovery, commit history profiling, and structural delta analysis.
All logs routed to stderr for Stream Purity Doctrine (3.11) compliance.
Abstract Integrity Standard (2.1): NO raw code patches or source text exposed.
"""
import subprocess
import sqlite3
import json
import sys
import os
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple


class GitExtractionEngine:
    """
    Enterprise-grade Git repository analytics engine.
    Extracts structural metadata only - never raw source code.
    """
    
    def __init__(self, repo_path: Optional[str] = None, db_path: Optional[str] = None, project_id: Optional[str] = None):
        """
        Initialize the Git extraction engine.
        
        Args:
            repo_path: Path to the git repository (defaults to project root)
            db_path: Path to hub.db SQLite database
            project_id: Project UUID for multi-tenant isolation
        """
        if repo_path is None:
            # Default to project root (2 levels up from apps/ai-core/services)
            self.repo_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', '..')
            )
        else:
            self.repo_path = os.path.abspath(repo_path)
        
        if db_path is None:
            # Default to apps/cli/hub.db
            self.db_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', '..', 'cli', 'hub.db')
            )
        else:
            self.db_path = os.path.abspath(db_path)

        self.project_id = project_id or 'global'
        
        self._ensure_git_repo()
        self._ensure_database()
        
        print(f"[GitEngine] Initialized for repo: {self.repo_path}", file=sys.stderr, flush=True)
        print(f"[GitEngine] Database: {self.db_path}", file=sys.stderr, flush=True)
    
    def _ensure_git_repo(self):
        """Verify the path is a valid git repository."""
        git_dir = os.path.join(self.repo_path, '.git')
        if not os.path.exists(git_dir):
            raise ValueError(f"Not a git repository: {self.repo_path}")
    
    def _ensure_database(self):
        """Create git analytics tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Git commits table (project-scoped)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS git_commits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                commit_hash TEXT NOT NULL,
                short_hash TEXT NOT NULL,
                author TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                message TEXT NOT NULL,
                branch TEXT NOT NULL,
                files_changed INTEGER DEFAULT 0,
                lines_added INTEGER DEFAULT 0,
                lines_removed INTEGER DEFAULT 0,
                complexity_delta REAL DEFAULT 0.0,
                scanned_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_id, commit_hash)
            )
        """)
        
        # Git file changes table (structural metadata only)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS git_file_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                commit_hash TEXT NOT NULL,
                file_path TEXT NOT NULL,
                status TEXT NOT NULL,  -- A=added, M=modified, D=deleted, R=renamed
                lines_added INTEGER DEFAULT 0,
                lines_removed INTEGER DEFAULT 0,
                FOREIGN KEY (commit_hash) REFERENCES git_commits(commit_hash)
            )
        """)
        
        # Quality file audit table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quality_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                language TEXT,
                quality_score REAL DEFAULT 0.0,
                complexity INTEGER DEFAULT 0,
                symbol_count INTEGER DEFAULT 0,
                dependency_count INTEGER DEFAULT 0,
                entity_count INTEGER DEFAULT 0,
                file_size INTEGER DEFAULT 0,
                last_audited TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(project_id, file_path)
            )
        """)
        
        # Create indexes for performance and tenant isolation
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_commits_project_hash ON git_commits(project_id, commit_hash)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_commits_branch_project ON git_commits(project_id, branch)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_changes_project ON git_file_changes(project_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_quality_project ON quality_files(project_id)
        """)
        
        # Migrate existing tables if project_id columns are missing
        cursor.execute("PRAGMA table_info(git_commits)")
        existing_commit_columns = [row[1] for row in cursor.fetchall()]
        if 'project_id' not in existing_commit_columns:
            cursor.execute("ALTER TABLE git_commits ADD COLUMN project_id TEXT NOT NULL DEFAULT 'global'")
        
        cursor.execute("PRAGMA table_info(git_file_changes)")
        existing_change_columns = [row[1] for row in cursor.fetchall()]
        if 'project_id' not in existing_change_columns:
            cursor.execute("ALTER TABLE git_file_changes ADD COLUMN project_id TEXT NOT NULL DEFAULT 'global'")

        # Create a lightweight projects table for schema integrity and foreign key compliance
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT,
                repo_path TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Core symbol ledger for public architecture extraction
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS core_symbols (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                symbol_name TEXT NOT NULL,
                symbol_type TEXT NOT NULL,
                signature TEXT,
                start_line INTEGER,
                end_line INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        """)

        # Data lineage edge ledger for upstream/downstream traversal
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS data_lineage_edges (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                source_dataset TEXT NOT NULL,
                target_dataset TEXT NOT NULL,
                transformation_type TEXT NOT NULL,
                source_file TEXT NOT NULL,
                line_range TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_projects_id ON projects(id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_core_symbols_project ON core_symbols(project_id, file_path)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_data_lineage_project ON data_lineage_edges(project_id, source_dataset, target_dataset)
        """)

        cursor.execute("""
            INSERT OR IGNORE INTO projects (id, name, repo_path)
            VALUES (?, ?, ?)
        """, (
            self.project_id,
            os.path.basename(self.repo_path),
            self.repo_path
        ))

        conn.commit()
        conn.close()
        
        print("[GitEngine] Database schema ensured", file=sys.stderr, flush=True)
    
    def _run_git_command(self, args: List[str], timeout: int = 30) -> Optional[str]:
        """
        Execute a git command safely.
        
        Args:
            args: Git command arguments (excluding 'git')
            timeout: Maximum execution time in seconds
            
        Returns:
            stdout output or None if failed
        """
        try:
            result = subprocess.run(
                ['git'] + args,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode != 0:
                print(f"[GitEngine] Command failed: git {' '.join(args)}", file=sys.stderr, flush=True)
                print(f"[GitEngine] stderr: {result.stderr.strip()}", file=sys.stderr, flush=True)
                return None
            
            return result.stdout.strip()
            
        except subprocess.TimeoutExpired:
            print(f"[GitEngine] Command timed out: git {' '.join(args)}", file=sys.stderr, flush=True)
            return None
        except Exception as e:
            print(f"[GitEngine] Error executing git command: {e}", file=sys.stderr, flush=True)
            return None
    
    # ==================== BRANCH DISCOVERY LAYER ====================
    
    def discover_branches(self) -> Dict:
        """
        Discover all local and remote branches.
        
        Returns:
            Dictionary with branch lists and active branch
        """
        print("[GitEngine] Discovering branches...", file=sys.stderr, flush=True)
        
        # Get all local branches
        local_output = self._run_git_command([
            'branch', '--format=%(refname:short)'
        ])
        
        local_branches = []
        if local_output:
            local_branches = [b.strip() for b in local_output.split('\n') if b.strip()]
        
        # Get remote branches
        remote_output = self._run_git_command([
            'branch', '-r', '--format=%(refname:short)'
        ])
        
        remote_branches = []
        if remote_output:
            remote_branches = [b.strip() for b in remote_output.split('\n') if b.strip()]
        
        # Get active branch
        active_output = self._run_git_command(['branch', '--show-current'])
        active_branch = active_output if active_output else "main"
        
        result = {
            "local": local_branches,
            "remote": remote_branches,
            "active": active_branch,
            "total_local": len(local_branches),
            "total_remote": len(remote_branches)
        }
        
        print(f"[GitEngine] Found {len(local_branches)} local, {len(remote_branches)} remote branches", file=sys.stderr, flush=True)
        
        return result
    
    # ==================== COMMIT HISTORY PROFILER ====================
    
    def profile_commit_history(
        self,
        branch: str = "main",
        limit: int = 100,
        scan_files: bool = True
    ) -> List[Dict]:
        """
        Parse commit history and extract structural metadata.
        
        Args:
            branch: Target branch name
            limit: Maximum number of commits to profile
            scan_files: Whether to extract per-file metrics
            
        Returns:
            List of commit metadata dictionaries
        """
        print(f"[GitEngine] Profiling commit history for '{branch}' (limit={limit})...", file=sys.stderr, flush=True)
        
        # Get commit log with structured format
        log_output = self._run_git_command([
            'log',
            f'--format=%H|%an|%ai|%s',
            f'-{limit}',
            branch
        ])
        
        if not log_output:
            print(f"[GitEngine] No commits found for branch: {branch}", file=sys.stderr, flush=True)
            return []
        
        commits = []
        for line in log_output.split('\n'):
            if not line.strip():
                continue
            
            parts = line.split('|', 3)
            if len(parts) != 4:
                continue
            
            commit_hash, author, timestamp, message = parts
            
            # Extract file manifest mutation
            file_metrics = {}
            if scan_files:
                file_metrics = self._extract_file_metrics(commit_hash)
            
            commit_data = {
                "project_id": self.project_id,
                "commit_hash": commit_hash,
                "short_hash": commit_hash[:7],
                "author": author,
                "timestamp": timestamp,
                "message": message,
                "branch": branch,
                "files_changed": file_metrics.get("files_changed", 0),
                "lines_added": file_metrics.get("total_added", 0),
                "lines_removed": file_metrics.get("total_removed", 0),
                "complexity_delta": file_metrics.get("complexity_delta", 0.0),
                "files": file_metrics.get("files", [])
            }
            
            commits.append(commit_data)
            
            # Persist to database
            self._persist_commit_to_db(commit_data)
        
        print(f"[GitEngine] Profiled {len(commits)} commits from '{branch}'", file=sys.stderr, flush=True)
        
        return commits
    
    def _extract_file_metrics(self, commit_hash: str) -> Dict:
        """
        Extract structural file metrics for a commit.
        Uses git diff-tree and git diff --numstat.
        NO source code is extracted.
        
        Args:
            commit_hash: Full commit hash
            
        Returns:
            Dictionary with file-level metrics
        """
        # Get file status (A/M/D)
        # Use --root on diff-tree so initial commits list added files
        status_output = self._run_git_command([
            'diff-tree', '-r', '--no-commit-id', '--name-status', '--root',
            commit_hash
        ])

        # For line-level metrics use `git show --numstat <commit>` which
        # works for initial commits as well (avoids using <commit>^ which
        # fails when a commit has no parent)
        numstat_output = self._run_git_command([
            'show', '--numstat', commit_hash
        ])
        
        files = []
        total_added = 0
        total_removed = 0
        
        # Parse file statuses
        if status_output:
            for line in status_output.split('\n'):
                if not line.strip():
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 2:
                    status = parts[0]
                    file_path = parts[1]
                    
                    files.append({
                        "path": file_path,
                        "status": status,
                        "lines_added": 0,
                        "lines_removed": 0
                    })
        
        # Parse line counts
        if numstat_output:
            numstat_lines = numstat_output.split('\n')
            for i, line in enumerate(numstat_lines):
                if not line.strip() or i >= len(files):
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 3:
                    try:
                        added = int(parts[0]) if parts[0] != '-' else 0
                        removed = int(parts[1]) if parts[1] != '-' else 0
                        
                        if i < len(files):
                            files[i]["lines_added"] = added
                            files[i]["lines_removed"] = removed
                            
                            total_added += added
                            total_removed += removed
                    except ValueError:
                        pass
        
        # Calculate complexity delta (heuristic)
        delta_lines = total_added - total_removed
        complexity_delta = delta_lines / 100.0 if delta_lines > 0 else 0.0
        
        return {
            "files_changed": len(files),
            "total_added": total_added,
            "total_removed": total_removed,
            "complexity_delta": round(complexity_delta, 2),
            "files": files
        }
    
    def _persist_commit_to_db(self, commit_data: Dict):
        """
        Persist commit metadata to SQLite database.
        Abstract Integrity Standard (2.1): Only structural data stored.
        
        Args:
            commit_data: Commit metadata dictionary
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Insert or ignore commit
            cursor.execute("""
                INSERT OR IGNORE INTO git_commits (
                    project_id, commit_hash, short_hash, author, timestamp, message,
                    branch, files_changed, lines_added, lines_removed,
                    complexity_delta, scanned_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.project_id,
                commit_data["commit_hash"],
                commit_data["short_hash"],
                commit_data["author"],
                commit_data["timestamp"],
                commit_data["message"],
                commit_data["branch"],
                commit_data["files_changed"],
                commit_data["lines_added"],
                commit_data["lines_removed"],
                commit_data["complexity_delta"],
                datetime.now(timezone.utc).isoformat()
            ))
            
            # Insert file changes
            for file_info in commit_data.get("files", []):
                cursor.execute("""
                    INSERT INTO git_file_changes (
                        project_id, commit_hash, file_path, status,
                        lines_added, lines_removed
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    self.project_id,
                    commit_data["commit_hash"],
                    file_info["path"],
                    file_info["status"],
                    file_info["lines_added"],
                    file_info["lines_removed"]
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"[GitEngine] Error persisting commit {commit_data['short_hash']}: {e}", file=sys.stderr, flush=True)
    
    # ==================== DIFF ANALYTICS ====================
    
    def analyze_commit_diff(self, commit_hash: str) -> Dict:
        """
        Analyze structural delta for a specific commit.
        
        Args:
            commit_hash: Full commit hash
            
        Returns:
            Dictionary with comprehensive diff analytics
        """
        print(f"[GitEngine] Analyzing diff for commit {commit_hash[:7]}...", file=sys.stderr, flush=True)
        
        file_metrics = self._extract_file_metrics(commit_hash)
        
        # Get commit metadata
        log_output = self._run_git_command([
            'log', '-1', '--format=%H|%an|%ai|%s',
            commit_hash
        ])
        
        commit_info = {}
        if log_output:
            parts = log_output.split('|', 3)
            if len(parts) == 4:
                commit_info = {
                    "commit_hash": parts[0],
                    "short_hash": parts[0][:7],
                    "author": parts[1],
                    "timestamp": parts[2],
                    "message": parts[3]
                }
        
        result = {
            **commit_info,
            **file_metrics,
            "delta_summary": {
                "net_lines": file_metrics["total_added"] - file_metrics["total_removed"],
                "churn": file_metrics["total_added"] + file_metrics["total_removed"],
                "complexity_trend": "increasing" if file_metrics["complexity_delta"] > 0 else "stable"
            }
        }
        
        print(f"[GitEngine] Diff analysis complete: {file_metrics['files_changed']} files", file=sys.stderr, flush=True)
        
        return result
    
    # ==================== TIME-SERIES ANALYTICS ====================
    
    def get_branch_time_series(
        self,
        branch: str = "main",
        commit_limit: int = 50
    ) -> Dict:
        """
        Generate time-series analytics for a branch.
        
        Args:
            branch: Target branch
            commit_limit: Number of recent commits to analyze
            
        Returns:
            Time-series data with aggregated metrics
        """
        print(f"[GitEngine] Generating time-series for '{branch}'...", file=sys.stderr, flush=True)
        
        commits = self.profile_commit_history(branch, commit_limit, scan_files=True)
        
        if not commits:
            return {
                "branch": branch,
                "commits_analyzed": 0,
                "time_series": []
            }
        
        # Build time-series
        time_series = []
        cumulative_added = 0
        cumulative_removed = 0
        
        for commit in reversed(commits):  # Oldest first
            cumulative_added += commit["lines_added"]
            cumulative_removed += commit["lines_removed"]
            
            time_series.append({
                "commit_hash": commit["short_hash"],
                "timestamp": commit["timestamp"],
                "message": commit["message"],
                "lines_added": commit["lines_added"],
                "lines_removed": commit["lines_removed"],
                "files_changed": commit["files_changed"],
                "complexity_delta": commit["complexity_delta"],
                "cumulative_added": cumulative_added,
                "cumulative_removed": cumulative_removed,
                "net_change": cumulative_added - cumulative_removed
            })
        
        # Aggregate statistics
        total_files = sum(c["files_changed"] for c in commits)
        total_added = sum(c["lines_added"] for c in commits)
        total_removed = sum(c["lines_removed"] for c in commits)
        
        result = {
            "branch": branch,
            "commits_analyzed": len(commits),
            "total_files_changed": total_files,
            "total_lines_added": total_added,
            "total_lines_removed": total_removed,
            "net_lines": total_added - total_removed,
            "avg_complexity_delta": sum(c["complexity_delta"] for c in commits) / len(commits),
            "time_series": time_series
        }
        
        print(f"[GitEngine] Time-series complete: {len(time_series)} data points", file=sys.stderr, flush=True)
        
        return result

    # Language mapping for file extension inference
    _EXT_LANGUAGE_MAP = {
        '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
        '.tsx': 'TypeScript', '.jsx': 'JavaScript', '.vue': 'Vue',
        '.go': 'Go', '.java': 'Java', '.php': 'PHP', '.rb': 'Ruby',
        '.rs': 'Rust', '.cpp': 'C++', '.c': 'C', '.h': 'C/C++ Header',
        '.cs': 'C#', '.swift': 'Swift', '.kt': 'Kotlin', '.scala': 'Scala',
        '.css': 'CSS', '.scss': 'SCSS', '.html': 'HTML', '.xml': 'XML',
        '.json': 'JSON', '.yaml': 'YAML', '.yml': 'YAML', '.toml': 'TOML',
        '.md': 'Markdown', '.sql': 'SQL', '.sh': 'Shell', '.bash': 'Bash',
        '.dockerfile': 'Dockerfile', '.makefile': 'Makefile',
        '.txt': 'Text', '.cfg': 'Config', '.ini': 'INI', '.env': 'Env',
        '.gitignore': 'Git Ignore', '.lock': 'Lockfile',
    }

    def _infer_language(self, file_path: str) -> str:
        """Infer programming language from file path extension or name."""
        import os as _os
        basename = _os.path.basename(file_path).lower()
        # Handle files with no extension but known names
        if basename in ('makefile', 'gnumakefile'):
            return 'Makefile'
        if basename == 'dockerfile':
            return 'Dockerfile'
        _, ext = _os.path.splitext(basename)
        return self._EXT_LANGUAGE_MAP.get(ext, 'Unknown')

    def audit_file(self, target_file: str) -> Dict:
        """
        Audit a single file and persist file-level quality metadata.

        Args:
            target_file: Relative file path within the repository

        Returns:
            Dictionary with audit metrics and quality summary
        """
        normalized_target = target_file.lstrip(os.sep)
        abs_file_path = os.path.abspath(os.path.join(self.repo_path, normalized_target))
        if os.path.commonpath([self.repo_path, abs_file_path]) != self.repo_path:
            raise ValueError("Target file must be within the repository path")

        if not os.path.exists(abs_file_path):
            raise FileNotFoundError(f"Target file not found: {target_file}")

        file_size = os.path.getsize(abs_file_path)
        line_count = 0
        with open(abs_file_path, 'r', errors='ignore') as fd:
            for _ in fd:
                line_count += 1

        git_log_output = self._run_git_command([
            'log', '--follow', '--oneline', '--', target_file
        ])
        commit_count = len(git_log_output.splitlines()) if git_log_output else 0

        complexity = max(1, int(line_count / 10))
        quality_score = round(max(1.0, min(10.0, 10.0 - (complexity / 20) - (commit_count * 0.05))), 2)
        language = self._infer_language(target_file)

        symbol_count = max(1, int(line_count / 5))
        audit_data = {
            'project_id': self.project_id,
            'file_path': target_file,
            'language': language,
            'quality_score': quality_score,
            'complexity': complexity,
            'symbol_count': symbol_count,
            'dependency_count': max(0, int(line_count / 20)),
            'entity_count': symbol_count,
            'last_audited': datetime.now(timezone.utc).isoformat(),
            'file_size': file_size,
            'commit_count': commit_count
        }

        self._persist_quality_file_to_db(audit_data)

        print(f"[GitEngine] Audit complete for {target_file}", file=sys.stderr, flush=True)

        return audit_data

    def _persist_quality_file_to_db(self, audit_data: Dict):
        """
        Persist quality audit metadata for a file.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Ensure entity_count and file_size columns exist
            cursor.execute("PRAGMA table_info(quality_files)")
            cols = [r[1] for r in cursor.fetchall()]
            if 'entity_count' not in cols:
                cursor.execute("ALTER TABLE quality_files ADD COLUMN entity_count INTEGER DEFAULT 0")
            if 'file_size' not in cols:
                cursor.execute("ALTER TABLE quality_files ADD COLUMN file_size INTEGER DEFAULT 0")
            conn.commit()

            entity_count = audit_data.get('entity_count', audit_data.get('symbol_count', 0))
            file_size = audit_data.get('file_size', 0)

            cursor.execute("""
                INSERT INTO quality_files (
                    project_id, file_path, language,
                    quality_score, complexity, symbol_count,
                    dependency_count, entity_count, file_size, last_audited
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, file_path) DO UPDATE SET
                    language=excluded.language,
                    quality_score=excluded.quality_score,
                    complexity=excluded.complexity,
                    symbol_count=excluded.symbol_count,
                    dependency_count=excluded.dependency_count,
                    entity_count=excluded.entity_count,
                    file_size=excluded.file_size,
                    last_audited=excluded.last_audited
            """, (
                audit_data['project_id'],
                audit_data['file_path'],
                audit_data['language'],
                audit_data['quality_score'],
                audit_data['complexity'],
                audit_data['symbol_count'],
                audit_data['dependency_count'],
                entity_count,
                file_size,
                audit_data['last_audited']
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[GitEngine] Error persisting audit data for {audit_data['file_path']}: {e}", file=sys.stderr, flush=True)

    def _persist_project_record(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO projects (id, name, repo_path)
                VALUES (?, ?, ?)
            """, (
                self.project_id,
                os.path.basename(self.repo_path),
                self.repo_path
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[GitEngine] Error persisting project record: {e}", file=sys.stderr, flush=True)

    def _persist_core_symbol(self, symbol_data: Dict):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO core_symbols (
                    id, project_id, file_path, symbol_name,
                    symbol_type, signature, start_line, end_line
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    signature=excluded.signature,
                    start_line=excluded.start_line,
                    end_line=excluded.end_line
            """, (
                symbol_data['id'],
                symbol_data['project_id'],
                symbol_data['file_path'],
                symbol_data['symbol_name'],
                symbol_data['symbol_type'],
                symbol_data.get('signature'),
                symbol_data.get('start_line'),
                symbol_data.get('end_line')
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[GitEngine] Error persisting core symbol {symbol_data.get('symbol_name')}: {e}", file=sys.stderr, flush=True)

    def _persist_data_lineage_edge(self, edge_data: Dict):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO data_lineage_edges (
                    id, project_id, source_dataset, target_dataset,
                    transformation_type, source_file, line_range
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                edge_data['id'],
                edge_data['project_id'],
                edge_data['source_dataset'],
                edge_data['target_dataset'],
                edge_data['transformation_type'],
                edge_data['source_file'],
                edge_data.get('line_range')
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[GitEngine] Error persisting data lineage edge {edge_data.get('id')}: {e}", file=sys.stderr, flush=True)

    def _scan_repository_for_knowledge_graph(self):
        try:
            from tree_sitter_analyzer import LanguageRouter
            from sql_lineage import SQLLineageAnalyzer
        except ImportError as e:
            print(f"[GitEngine] Language or SQL analyzer import failed: {e}", file=sys.stderr, flush=True)
            return

        router = LanguageRouter()
        lineage = SQLLineageAnalyzer()

        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d != '.git']
            for filename in files:
                ext = os.path.splitext(filename)[1].lower()
                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, self.repo_path)

                try:
                    if ext in router.supported_extensions():
                        result = router.analyze_file(file_path)
                        for symbol in result.get('symbols', []):
                            symbol['id'] = uuid.uuid4().hex
                            symbol['project_id'] = self.project_id
                            symbol['file_path'] = rel_path
                            self._persist_core_symbol(symbol)

                        if ext == '.py':
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as fd:
                                python_content = fd.read()
                            for inline_edge in lineage.extract_lineage_from_python_source(python_content):
                                for source_dataset in inline_edge['source_datasets']:
                                    self._persist_data_lineage_edge({
                                        'id': uuid.uuid4().hex,
                                        'project_id': self.project_id,
                                        'source_dataset': source_dataset,
                                        'target_dataset': inline_edge['target_dataset'],
                                        'transformation_type': 'pandas_io',
                                        'source_file': rel_path,
                                        'line_range': inline_edge['line_range']
                                    })

                    if ext == '.sql':
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as fd:
                            sql_content = fd.read()
                        for edge in lineage.extract_sql_dependencies(sql_content):
                            for source_dataset in edge['source_datasets']:
                                self._persist_data_lineage_edge({
                                    'id': uuid.uuid4().hex,
                                    'project_id': self.project_id,
                                    'source_dataset': source_dataset,
                                    'target_dataset': edge['target_dataset'],
                                    'transformation_type': edge['transformation_type'],
                                    'source_file': rel_path,
                                    'line_range': edge['line_range']
                                })
                except Exception as exc:
                    print(f"[GitEngine] Knowledge graph scan skipped {rel_path}: {exc}", file=sys.stderr, flush=True)

    def build_knowledge_graph(self):
        """Build the symbol and data lineage graph for the active project."""
        print(f"[GitEngine] Building knowledge graph for project {self.project_id}", file=sys.stderr, flush=True)
        self._persist_project_record()
        self._scan_repository_for_knowledge_graph()
        return True


# ==================== CLI ENTRY POINT ====================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="WikiHub Git Extraction Engine")
    parser.add_argument("--repo", help="Repository path (deprecated, use --repo-path)")
    parser.add_argument("--repo-path", help="Repository absolute path")
    parser.add_argument("--db", help="Database path")
    parser.add_argument("--project-id", help="Project UUID for multi-tenant isolation")
    parser.add_argument("--target-file", help="Single file path for audit mode")
    parser.add_argument("--branch", default="main", help="Target branch")
    parser.add_argument("--limit", type=int, default=50, help="Commit limit")
    parser.add_argument("--action", choices=["branches", "commits", "diff", "time-series", "scan-all", "audit-single"],
                       default="branches", help="Action to perform")
    parser.add_argument("--commit", help="Commit hash for diff analysis")
    
    args = parser.parse_args()
    
    try:
        # Use --repo-path if provided, fallback to --repo for backward compatibility
        repo_path = args.repo_path or args.repo
        
        # Validate required parameters for scan-all and audit-single
        if args.action in ["scan-all", "audit-single"]:
            if not args.project_id:
                print("Error: --project-id is required for scan-all and audit-single actions", file=sys.stderr, flush=True)
                sys.exit(1)
            if not repo_path:
                print("Error: --repo-path is required for scan-all and audit-single actions", file=sys.stderr, flush=True)
                sys.exit(1)
        
        # For audit-single, validate target-file
        if args.action == "audit-single" and not args.target_file:
            print("Error: --target-file is required for audit-single action", file=sys.stderr, flush=True)
            sys.exit(1)
        
        engine = GitExtractionEngine(repo_path=repo_path, db_path=args.db, project_id=args.project_id)
        
        if args.action == "branches":
            result = engine.discover_branches()
            print(json.dumps(result, indent=2))
        
        elif args.action == "commits":
            commits = engine.profile_commit_history(args.branch, args.limit)
            print(json.dumps({
                "branch": args.branch,
                "count": len(commits),
                "commits": commits
            }, indent=2))
        
        elif args.action == "diff":
            if not args.commit:
                print("Error: --commit required for diff action", file=sys.stderr)
                sys.exit(1)
            result = engine.analyze_commit_diff(args.commit)
            print(json.dumps(result, indent=2))
        
        elif args.action == "time-series":
            result = engine.get_branch_time_series(args.branch, args.limit)
            print(json.dumps(result, indent=2))
        
        elif args.action == "scan-all":
            print(f"\n[Scan-All] Starting full repository scan", file=sys.stderr, flush=True)
            print(f"[Scan-All] Project ID: {args.project_id}", file=sys.stderr, flush=True)
            print(f"[Scan-All] Repository: {repo_path}", file=sys.stderr, flush=True)
            
            # Discover branches
            print(f"[10%] Discovering branches...", file=sys.stderr, flush=True)
            branches = engine.discover_branches()
            print(f"[20%] Found {branches['total_local']} branches", file=sys.stderr, flush=True)
            
            # Profile commits for each branch and collect across branches
            all_branches = branches['local']
            all_commits = []
            for idx, branch in enumerate(all_branches):
                progress = 20 + int((idx / max(len(all_branches), 1)) * 40)
                print(f"[{progress}%] Profiling branch: {branch}", file=sys.stderr, flush=True)
                commits = engine.profile_commit_history(branch, args.limit)
                print(f"[{progress}%] Found {len(commits)} commits on {branch}", file=sys.stderr, flush=True)
                # Collect commits for cross-branch auditing
                if commits:
                    all_commits.extend(commits)
            
            print(f"[65%] Branch profiling complete", file=sys.stderr, flush=True)
            
            # Analyze recent commits for file changes (focus on main branch)
            print(f"[70%] Analyzing file change metadata...", file=sys.stderr, flush=True)
            main_commits = engine.profile_commit_history("main", min(args.limit, 10))
            for commit_data in main_commits[:5]:  # Analyze top 5 commits
                commit_hash = commit_data['commit_hash']
                print(f"[75%] Processing commit {commit_data['short_hash']}...", file=sys.stderr, flush=True)
                diff_result = engine.analyze_commit_diff(commit_hash)
            
            print(f"[85%] File change analysis complete", file=sys.stderr, flush=True)

            # Audit discovered files to populate `quality_files` (project-scoped)
            try:
                print(f"[86%] Auditing discovered files for quality metrics...", file=sys.stderr, flush=True)
                file_paths = set()
                # Use files discovered across all profiled branches
                for commit in all_commits:
                    for f in commit.get('files', []):
                        path = f.get('path')
                        if path:
                            file_paths.add(path)

                # Also discover files from the working tree (handles shallow clones)
                try:
                    import glob as _glob
                    _repo_abs = os.path.abspath(repo_path)
                    _skip_prefixes = ('.git', 'node_modules', '.venv', '__pycache__', '.next', 'dist', 'build', '.nuxt', '.output')
                    for _ext in ('*.py', '*.js', '*.ts', '*.go', '*.java', '*.php', '*.rb', '*.rs',
                                 '*.cpp', '*.c', '*.h', '*.jsx', '*.tsx', '*.vue', '*.css', '*.html',
                                 '*.json', '*.yaml', '*.yml', '*.md', '*.sql', '*.sh'):
                        for _f in _glob.glob(os.path.join(_repo_abs, '**', _ext), recursive=True):
                            _rel = os.path.relpath(_f, _repo_abs)
                            if not any(_rel.startswith(p) for p in _skip_prefixes):
                                file_paths.add(_rel)
                    print(f"[87%] Filesystem discovery: {len(file_paths)} total files", file=sys.stderr, flush=True)
                except Exception as _fs_err:
                    print(f"[87%] Filesystem discovery error: {_fs_err}", file=sys.stderr, flush=True)

                total_files_to_audit = len(file_paths)
                if total_files_to_audit > 0:
                    idx = 0
                    for fp in sorted(file_paths):
                        idx += 1
                        try:
                            pct = 86 + int((idx / total_files_to_audit) * 9)
                        except Exception:
                            pct = 90
                        print(f"[{pct}%] Auditing file {idx}/{total_files_to_audit}: {fp}", file=sys.stderr, flush=True)
                        try:
                            engine.audit_file(fp)
                        except Exception as e:
                            print(f"[GitEngine] Audit failed for {fp}: {e}", file=sys.stderr, flush=True)
                else:
                    print(f"[86%] No files discovered to audit.", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"[GitEngine] Error during auditing pass: {e}", file=sys.stderr, flush=True)

            # Build the symbol and lineage knowledge graph
            try:
                print(f"[92%] Building knowledge graph...", file=sys.stderr, flush=True)
                engine.build_knowledge_graph()
                print(f"[94%] Knowledge graph built", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"[GitEngine] Knowledge graph build failed: {e}", file=sys.stderr, flush=True)
            
            # Generate time-series analytics
            print(f"[90%] Computing time-series analytics...", file=sys.stderr, flush=True)
            time_series = engine.get_branch_time_series("main", args.limit)
            
            print(f"[95%] Aggregating metrics...", file=sys.stderr, flush=True)
            print(f"[100%] Scan complete!", file=sys.stderr, flush=True)
            
            # Output final JSON summary
            print(json.dumps({
                "action": "scan-all",
                "project_id": args.project_id,
                "repo_path": repo_path,
                "branches_scanned": len(all_branches),
                "commits_profiled": sum([1 for _ in main_commits]),
                "status": "completed"
            }, indent=2))
        
        elif args.action == "audit-single":
            print(f"\n[Audit] Starting single file audit", file=sys.stderr, flush=True)
            print(f"[Audit] Project ID: {args.project_id}", file=sys.stderr, flush=True)
            print(f"[Audit] File: {args.target_file}", file=sys.stderr, flush=True)
            
            print(f"[20%] Locating file in repository...", file=sys.stderr, flush=True)
            audit_result = engine.audit_file(args.target_file)
            print(f"[40%] Parsing abstract syntax tree...", file=sys.stderr, flush=True)
            print(f"[60%] Tracking symbols and dependencies...", file=sys.stderr, flush=True)
            print(f"[80%] Computing quality metrics...", file=sys.stderr, flush=True)
            print(f"[100%] Audit complete!", file=sys.stderr, flush=True)
            
            # Output audit results
            print(json.dumps({
                "action": "audit-single",
                "project_id": args.project_id,
                "file_path": args.target_file,
                "status": "completed",
                "metrics": {
                    "quality_score": audit_result['quality_score'],
                    "complexity": audit_result['complexity'],
                    "dependencies": audit_result['dependency_count'],
                    "symbol_count": audit_result['symbol_count'],
                    "commit_count": audit_result['commit_count']
                }
            }, indent=2))
    
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr, flush=True)
        sys.exit(1)

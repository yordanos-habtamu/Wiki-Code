"""
SemanticistAgent - High-speed purpose synthesis and documentation drift detection.
Generates semantic module overviews and detects inline docstring drift against those summaries.
"""

import os
import sys
import re
import json
import sqlite3
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional
import importlib.util

# Project root discovery
current_file = os.path.abspath(__file__)
if 'apps' in current_file and 'ai-core' in current_file:
    apps_idx = current_file.find('apps')
    project_root = current_file[:apps_idx].rstrip('/')
else:
    project_root = os.path.dirname(os.path.dirname(current_file))
sys.path.insert(0, project_root)

# Dynamic import of LLMRouter to avoid hard dependency resolution issues
llm_router = None
LLMRouter = None
try:
    llm_path = os.path.join(project_root, 'apps', 'ai-core', 'llm', 'llm_router.py')
    spec = importlib.util.spec_from_file_location('llm_router', llm_path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules['llm_router'] = module
        spec.loader.exec_module(module)
        llm_router = module
        LLMRouter = getattr(module, 'LLMRouter', None)
except Exception as exc:
    print(f"[SemanticistAgent] Failed to import LLMRouter: {exc}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)


class BudgetExceeded(Exception):
    pass


class ContextWindowBudget:
    def __init__(self, token_limit: int = 1500):
        self.token_limit = token_limit
        self.tokens_used = 0

    def estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // 4)

    def consume(self, text: str) -> int:
        tokens = self.estimate_tokens(text)
        if self.tokens_used + tokens > self.token_limit:
            raise BudgetExceeded(
                f"Context window budget exceeded: {self.tokens_used + tokens} > {self.token_limit}"
            )
        self.tokens_used += tokens
        return tokens

    def remaining(self) -> int:
        return max(0, self.token_limit - self.tokens_used)


class SemanticistAgent:
    """High-speed Gemini Flash purpose and drift analytics loop."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        project_id: Optional[str] = None,
        token_limit: int = 1500
    ):
        self.project_id = project_id or 'global'
        self.db_path = db_path or os.path.join(project_root, 'apps', 'cli', 'hub.db')
        self.budget = ContextWindowBudget(token_limit=token_limit)
        self.llm_router = None
        self.llm_available = False

        if LLMRouter is not None:
            try:
                self.llm_router = LLMRouter()
                self.llm_available = self.llm_router.initialize()
            except Exception as exc:
                print(f"[SemanticistAgent] LLM router unavailable: {exc}", file=sys.stderr)
                self.llm_available = False
        # Resolve target model for this project (may be absent in older DBs)
        self.target_model = self._get_target_model()

        self._ensure_schema()

        print(f"SemanticistAgent initialized for project {self.project_id}", file=sys.stderr)
        print(f"Database file: {self.db_path}", file=sys.stderr)
        print(f"LLM available: {self.llm_available}", file=sys.stderr)
        print(f"Token budget: {self.budget.token_limit}", file=sys.stderr)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS semantic_artifacts (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                purpose_summary TEXT,
                docstring_summary TEXT,
                has_doc_drift INTEGER DEFAULT 0,
                drift_notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_semantic_artifacts_project ON semantic_artifacts(project_id, file_path)
        """)
        conn.commit()
        conn.close()

    def _get_target_model(self) -> str:
        """Query the project row for `target_model` or return a sane default."""
        default_model = os.environ.get('DEFAULT_TARGET_MODEL', 'google/gemini-2.5-flash')
        try:
            if not os.path.exists(self.db_path):
                return default_model
            conn = self._get_connection()
            cursor = conn.cursor()
            # Check if column exists
            try:
                cursor.execute("PRAGMA table_info(wiki_projects)")
                cols = [r['name'] for r in cursor.fetchall()]
            except Exception:
                cols = []

            if 'target_model' not in cols:
                conn.close()
                return default_model

            cursor.execute("SELECT target_model FROM wiki_projects WHERE id = ?", (self.project_id,))
            row = cursor.fetchone()
            conn.close()
            if row and row.get('target_model'):
                return row['target_model']
            return default_model
        except Exception as exc:
            print(f"[SemanticistAgent] Failed to resolve target model: {exc}", file=sys.stderr)
            return default_model

    def _fetch_project_files(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.db_path):
            return []
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT relative_path as file_path, language FROM files ORDER BY relative_path")
            return [dict(row) for row in cursor.fetchall()]
        except Exception as exc:
            print(f"[SemanticistAgent] Error fetching files: {exc}", file=sys.stderr)
            return []
        finally:
            conn.close()

    def _fetch_symbol_overview(self, file_path: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT symbol_name, symbol_type, signature, start_line, end_line FROM core_symbols "
                "WHERE project_id = ? AND file_path = ?",
                (self.project_id, file_path)
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as exc:
            print(f"[SemanticistAgent] Error fetching symbols for {file_path}: {exc}", file=sys.stderr)
            return []
        finally:
            conn.close()

    def _fetch_dependency_overview(self, file_path: str) -> List[str]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT import_path FROM dependencies WHERE source_file = ?",
                (file_path,)
            )
            return [row['import_path'] for row in cursor.fetchall()]
        except Exception as exc:
            print(f"[SemanticistAgent] Error fetching dependencies for {file_path}: {exc}", file=sys.stderr)
            return []
        finally:
            conn.close()

    def _extract_docstring_summary(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return ''
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                contents = f.read()

            extension = os.path.splitext(file_path)[1].lower()
            if extension == '.py':
                match = re.search(r'^[ \t]*(["\']{3})([\s\S]*?)\1', contents, re.MULTILINE)
                if match:
                    return match.group(2).strip()
                return self._extract_comment_block(contents, prefix='#')

            if extension == '.go':
                match = re.search(r'/\*[\s\S]*?\*/', contents)
                if match:
                    return match.group(0).strip()
                return self._extract_comment_block(contents, prefix='//')

            if extension == '.php':
                match = re.search(r'/\*[\s\S]*?\*/', contents)
                if match:
                    return match.group(0).strip()
                return self._extract_comment_block(contents, prefix='//')

            return self._extract_comment_block(contents, prefix='//')
        except Exception as exc:
            print(f"[SemanticistAgent] Error reading {file_path}: {exc}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return ''

    def _extract_comment_block(self, contents: str, prefix: str = '#') -> str:
        lines = []
        for line in contents.splitlines():
            stripped = line.strip()
            if stripped.startswith(prefix):
                lines.append(stripped.lstrip(prefix).strip())
            elif stripped == '':
                if lines:
                    break
            else:
                if lines:
                    break
        return '\n'.join(lines).strip()

    def _normalize(self, text: str) -> str:
        return ' '.join(re.findall(r"\w+", text.lower()))

    def _detect_documentation_drift(self, purpose: str, docstring: str) -> Dict[str, Any]:
        if not docstring:
            return {
                'has_drift': 1,
                'drift_notes': 'No inline documentation found for comparison'
            }

        purpose_tokens = set(re.findall(r"\w+", purpose.lower()))
        doc_tokens = set(re.findall(r"\w+", docstring.lower()))
        overlap = purpose_tokens.intersection(doc_tokens)
        proportion = 0.0
        if purpose_tokens:
            proportion = len(overlap) / len(purpose_tokens)

        if proportion < 0.30:
            return {
                'has_drift': 1,
                'drift_notes': f'Documentation Drift Detected (overlap={proportion:.2f})'
            }

        return {
            'has_drift': 0,
            'drift_notes': 'Documentation appears aligned with inferred purpose'
        }

    def _generate_purpose_fallback(
        self,
        file_path: str,
        language: str,
        symbols: List[Dict[str, Any]],
        dependencies: List[str]
    ) -> str:
        symbol_counts = {}
        for sym in symbols:
            symbol_counts[sym.get('symbol_type', 'unknown')] = symbol_counts.get(sym.get('symbol_type', 'unknown'), 0) + 1

        parts = [f"This {language} module at '{file_path}'"]
        if symbol_counts:
            types = ', '.join([f"{count} {kind}" for kind, count in symbol_counts.items()])
            parts.append(f"exposes {types}")
        else:
            parts.append("contains utility or orchestration logic")

        if dependencies:
            parts.append(f"and depends on {len(dependencies)} external or internal components")
        else:
            parts.append("and has minimal external dependencies")

        return ' '.join(parts) + '.'

    def _generate_module_purpose(
        self,
        file_path: str,
        language: str,
        symbols: List[Dict[str, Any]],
        dependencies: List[str]
    ) -> str:
        purpose_text = self._generate_purpose_fallback(file_path, language, symbols, dependencies)
        if not self.llm_available:
            return purpose_text

        try:
            prompt = [
                "You are a semantic analyst. Generate a concise 2-3 sentence business-domain summary of the file's purpose.",
                f"File: {file_path}",
                f"Language: {language}",
                f"Symbols: {json.dumps(symbols, indent=0)}",
                f"Dependencies: {json.dumps(dependencies, indent=0)}",
                "Focus on what the module does, not how it is implemented."
            ]
            prompt_text = '\n'.join(prompt)
            self.budget.consume(prompt_text)

            response = self.llm_router.complete(
                prompt_text,
                model_id=self.target_model or 'google/gemini-2.5-flash',
                options={'temperature': 0.1, 'max_tokens': 200}
            )

            if response and response.content:
                self.budget.consume(response.content)
                return response.content.strip()
        except BudgetExceeded as exc:
            print(f"[SemanticistAgent] Budget halt while generating purpose: {exc}", file=sys.stderr)
            raise
        except Exception as exc:
            print(f"[SemanticistAgent] LLM purpose generation failed: {exc}", file=sys.stderr)

        return purpose_text

    def _upsert_artifact(
        self,
        file_path: str,
        purpose_summary: str,
        docstring_summary: str,
        has_doc_drift: int,
        drift_notes: str
    ) -> None:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            artifact_id = f"{self.project_id}:{file_path}"
            cursor.execute(
                "INSERT OR REPLACE INTO semantic_artifacts "
                "(id, project_id, file_path, purpose_summary, docstring_summary, has_doc_drift, drift_notes, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    artifact_id,
                    self.project_id,
                    file_path,
                    purpose_summary,
                    docstring_summary,
                    has_doc_drift,
                    drift_notes,
                    datetime.now().isoformat()
                )
            )
            conn.commit()
        except Exception as exc:
            print(f"[SemanticistAgent] Error persisting semantic artifact for {file_path}: {exc}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        finally:
            conn.close()

    def run_analysis(self, file_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        print("[SemanticistAgent] Starting semantic agent analysis", file=sys.stderr)
        files = file_paths or [f['file_path'] for f in self._fetch_project_files()]

        results = {
            'project_id': self.project_id,
            'files_analyzed': 0,
            'budget_used': 0,
            'budget_limit': self.budget.token_limit,
            'warnings': []
        }

        for file_path in files:
            try:
                if self.budget.remaining() <= 0:
                    warning = 'Token budget exhausted before completing all files.'
                    print(f"[SemanticistAgent] {warning}", file=sys.stderr)
                    results['warnings'].append(warning)
                    break

                symbols = self._fetch_symbol_overview(file_path)
                dependencies = self._fetch_dependency_overview(file_path)
                docstring_summary = self._extract_docstring_summary(file_path)

                purpose_summary = self._generate_module_purpose(
                    file_path=file_path,
                    language=os.path.splitext(file_path)[1].lstrip('.') or 'unknown',
                    symbols=symbols,
                    dependencies=dependencies
                )

                drift = self._detect_documentation_drift(purpose_summary, docstring_summary)
                self._upsert_artifact(
                    file_path=file_path,
                    purpose_summary=purpose_summary,
                    docstring_summary=docstring_summary,
                    has_doc_drift=drift['has_drift'],
                    drift_notes=drift['drift_notes']
                )

                print(f"[SemanticistAgent] Analyzed {file_path}: drift={drift['has_drift']}", file=sys.stderr)
                results['files_analyzed'] += 1
            except BudgetExceeded as exc:
                warning = f"Token budget ceiling reached: {exc}"
                print(f"[SemanticistAgent] {warning}", file=sys.stderr)
                results['warnings'].append(warning)
                break
            except Exception as exc:
                warning = f"Analysis failed for {file_path}: {exc}"
                print(f"[SemanticistAgent] {warning}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                results['warnings'].append(warning)
                continue

        results['budget_used'] = self.budget.tokens_used
        print(f"[SemanticistAgent] Analysis completed for {results['files_analyzed']} file(s)", file=sys.stderr)
        return results

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        file_list = state.get('file_paths')
        return self.run_analysis(file_paths=file_list)

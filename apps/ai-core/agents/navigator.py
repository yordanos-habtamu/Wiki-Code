"""
NavigatorAgent - Interactive LangGraph query worker providing multi-tool lookups.
Supports find_implementation, trace_lineage, blast_radius, and explain_module operations.
"""

import os
import sys
import sqlite3
import json
import traceback
from typing import List, Dict, Any, Optional, Set

# Project root discovery
current_file = os.path.abspath(__file__)
if 'apps' in current_file and 'ai-core' in current_file:
    apps_idx = current_file.find('apps')
    project_root = current_file[:apps_idx].rstrip('/')
else:
    project_root = os.path.dirname(os.path.dirname(current_file))
sys.path.insert(0, project_root)


class NavigatorAgent:
    """Interactive query agent for semantic search and dependency tracing."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        project_id: Optional[str] = None,
        archive_root: Optional[str] = None
    ):
        self.project_id = project_id or 'global'
        self.db_path = db_path or os.path.join(project_root, 'apps', 'cli', 'hub.db')
        self.archive_root = archive_root or os.path.join(project_root, 'apps', 'ai-core', '.cartography', self.project_id)
        self.archive_index = self._load_archive_index()

        # Resolve project-scoped execution model token
        self.target_model = self._get_target_model()

        print(f"NavigatorAgent initialized for project {self.project_id}", file=sys.stderr)
        print(f"Archive root: {self.archive_root}", file=sys.stderr)
        print(f"Database path: {self.db_path}", file=sys.stderr)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _load_archive_index(self) -> List[Dict[str, Any]]:
        path = os.path.join(self.archive_root, 'archive_index.json')
        if not os.path.exists(path):
            return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
                return payload.get('entries', [])
        except Exception as exc:
            print(f"[NavigatorAgent] Failed to load archive index: {exc}", file=sys.stderr)
            return []

    def _get_target_model(self) -> str:
        default = os.environ.get('DEFAULT_TARGET_MODEL', 'google/gemini-2.5-flash')
        try:
            if not os.path.exists(self.db_path):
                return default
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("PRAGMA table_info(wiki_projects)")
                cols = [r['name'] for r in cursor.fetchall()]
            except Exception:
                cols = []

            if 'target_model' not in cols:
                conn.close()
                return default

            cursor.execute("SELECT target_model FROM wiki_projects WHERE id = ?", (self.project_id,))
            row = cursor.fetchone()
            conn.close()
            if row and row['target_model']:
                return row['target_model']
            return default
        except Exception as exc:
            print(f"[NavigatorAgent] Failed to resolve target model: {exc}", file=sys.stderr)
            return default

    def _tokenize(self, text: str) -> Set[str]:
        return set(t.lower() for t in text.split() if t.isalpha())

    def _semantic_search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        if not self.archive_index:
            return self._fallback_search(query, limit)

        query_tokens = self._tokenize(query)
        scored = []
        for entry in self.archive_index:
            purpose = entry.get('purpose_summary', '')
            tokens = self._tokenize(purpose)
            score = len(query_tokens.intersection(tokens))
            if score > 0:
                scored.append({
                    'file_path': entry.get('file_path'),
                    'purpose_summary': purpose,
                    'score': score
                })

        scored.sort(key=lambda item: item['score'], reverse=True)
        return scored[:limit]

    def _fallback_search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        if not os.path.exists(self.db_path):
            return []
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            matches = []
            query_lower = query.lower()

            # Try semantic_artifacts table first if it exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='semantic_artifacts'")
            has_semantic = cursor.fetchone() is not None

            if has_semantic:
                cursor.execute(
                    "SELECT file_path, purpose_summary FROM semantic_artifacts WHERE project_id = ?",
                    (self.project_id,)
                )
                for row in cursor.fetchall():
                    purpose = row['purpose_summary'] or ''
                    score = purpose.lower().count(query_lower)
                    if score > 0:
                        matches.append({'file_path': row['file_path'], 'purpose_summary': purpose, 'score': score})

            # Fall back to quality_files if no matches found yet
            if not matches and self.project_id != 'global':
                cursor.execute(
                    "SELECT file_path, language FROM quality_files WHERE project_id = ?",
                    (self.project_id,)
                )
                for row in cursor.fetchall():
                    path = row['file_path'] or ''
                    lang = row['language'] or ''
                    # Search on file path components and language
                    search_text = f"{path} {lang}"
                    score = search_text.lower().count(query_lower)
                    # Also give bonus for path component matches
                    path_parts = path.replace('/', ' ').replace('\\', ' ').replace('.', ' ').lower().split()
                    for part in path_parts:
                        if part and (part in query_lower or query_lower in part):
                            score += 2
                    if score > 0:
                        matches.append({'file_path': path, 'purpose_summary': f'[{lang}] {path}', 'score': score})

            matches.sort(key=lambda item: item['score'], reverse=True)
            return matches[:limit]
        except Exception as exc:
            print(f"[NavigatorAgent] Fallback search failed: {exc}", file=sys.stderr)
            return []
        finally:
            conn.close()

    def find_implementation(self, query: str, limit: int = 5) -> Dict[str, Any]:
        print(f"[NavigatorAgent] Running find_implementation for query: {query}", file=sys.stderr)
        matches = self._semantic_search(query, limit=limit)
        return {'tool': 'find_implementation', 'query': query, 'matches': matches}

    def trace_lineage(
        self,
        dataset_name: str,
        direction: str = 'forward',
        max_steps: int = 5
    ) -> Dict[str, Any]:
        print(f"[NavigatorAgent] Running trace_lineage for dataset: {dataset_name}", file=sys.stderr)
        if not os.path.exists(self.db_path):
            return {'tool': 'trace_lineage', 'paths': []}

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            direction = direction.lower()
            visited = set()
            queue = [dataset_name]
            paths = []

            while queue and len(paths) < max_steps:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)

                if direction == 'forward':
                    cursor.execute(
                        "SELECT source_dataset, target_dataset, source_file, line_range FROM data_lineage_edges "
                        "WHERE project_id = ? AND source_dataset = ?",
                        (self.project_id, current)
                    )
                else:
                    cursor.execute(
                        "SELECT source_dataset, target_dataset, source_file, line_range FROM data_lineage_edges "
                        "WHERE project_id = ? AND target_dataset = ?",
                        (self.project_id, current)
                    )

                for row in cursor.fetchall():
                    record = dict(row)
                    paths.append(record)
                    next_node = record['target_dataset'] if direction == 'forward' else record['source_dataset']
                    if next_node not in visited:
                        queue.append(next_node)

            return {'tool': 'trace_lineage', 'direction': direction, 'dataset': dataset_name, 'paths': paths}
        except Exception as exc:
            print(f"[NavigatorAgent] trace_lineage failed: {exc}", file=sys.stderr)
            return {'tool': 'trace_lineage', 'paths': []}
        finally:
            conn.close()

    def blast_radius(self, target_file: str, max_depth: int = 3) -> Dict[str, Any]:
        print(f"[NavigatorAgent] Running blast_radius for file: {target_file}", file=sys.stderr)
        if not os.path.exists(self.db_path):
            return {'tool': 'blast_radius', 'impacted_files': []}

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            impacted = []
            visited = set()
            frontier = [(target_file, 1)]

            while frontier:
                file_path, depth = frontier.pop(0)
                if file_path in visited or depth > max_depth:
                    continue
                visited.add(file_path)
                cursor.execute(
                    "SELECT source_file FROM dependencies WHERE import_path = ?",
                    (file_path,)
                )
                dependents = [row['source_file'] for row in cursor.fetchall()]
                for dependent in dependents:
                    impacted.append({'file_path': dependent, 'depth': depth, 'depends_on': file_path})
                    frontier.append((dependent, depth + 1))

            risk_score = min(10.0, len(impacted) * 1.2)
            classification = self._classify_risk(risk_score)
            return {
                'tool': 'blast_radius',
                'target_file': target_file,
                'impacted_files': impacted,
                'risk_score': round(risk_score, 2),
                'classification': classification
            }
        except Exception as exc:
            print(f"[NavigatorAgent] blast_radius failed: {exc}", file=sys.stderr)
            return {'tool': 'blast_radius', 'impacted_files': [], 'risk_score': 0.0, 'classification': 'unknown'}
        finally:
            conn.close()

    def explain_module(self, file_path: str) -> Dict[str, Any]:
        print(f"[NavigatorAgent] Running explain_module for file: {file_path}", file=sys.stderr)
        if not os.path.exists(self.db_path):
            return {'tool': 'explain_module', 'file_path': file_path, 'summary': ''}

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT purpose_summary, docstring_summary, drift_notes, has_doc_drift "
                "FROM semantic_artifacts WHERE project_id = ? AND file_path = ?",
                (self.project_id, file_path)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'tool': 'explain_module',
                    'file_path': file_path,
                    'summary': row['purpose_summary'],
                    'docstring': row['docstring_summary'],
                    'drift_notes': row['drift_notes'],
                    'has_doc_drift': bool(row['has_doc_drift'])
                }

            cursor.execute(
                "SELECT symbol_name, symbol_type, start_line, end_line FROM core_symbols WHERE project_id = ? AND file_path = ?",
                (self.project_id, file_path)
            )
            symbols = [dict(r) for r in cursor.fetchall()]
            return {
                'tool': 'explain_module',
                'file_path': file_path,
                'summary': f'No semantic artifact found. {len(symbols)} symbol(s) were discovered.',
                'symbols': symbols
            }
        except Exception as exc:
            print(f"[NavigatorAgent] explain_module failed: {exc}", file=sys.stderr)
            return {'tool': 'explain_module', 'file_path': file_path, 'summary': ''}
        finally:
            conn.close()

    def _classify_risk(self, score: float) -> str:
        if score < 2.0:
            return 'isolated'
        if score < 4.0:
            return 'low'
        if score < 6.0:
            return 'medium'
        if score < 8.0:
            return 'high'
        return 'critical'

    def run_tool(
        self,
        tool_name: str,
        query: Optional[str] = None,
        target: Optional[str] = None,
        direction: str = 'forward',
        max_depth: int = 3
    ) -> Dict[str, Any]:
        tool_name = tool_name.lower()
        if tool_name == 'find_implementation':
            return self.find_implementation(query or '')
        if tool_name == 'trace_lineage':
            return self.trace_lineage(target or query or '', direction=direction, max_steps=max_depth)
        if tool_name == 'blast_radius':
            return self.blast_radius(target or query or '', max_depth=max_depth)
        if tool_name == 'explain_module':
            return self.explain_module(target or query or '')
        return {'tool': tool_name, 'error': 'Unknown tool'}

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return self.run_tool(
            state.get('tool', ''),
            query=state.get('query'),
            target=state.get('target'),
            direction=state.get('direction', 'forward'),
            max_depth=state.get('max_depth', 3)
        )

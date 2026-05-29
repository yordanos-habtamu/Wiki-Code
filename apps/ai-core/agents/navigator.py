"""
NavigatorAgent - Interactive LangGraph query worker providing multi-tool lookups.
Supports find_implementation, trace_lineage, blast_radius, and explain_module operations.
"""

import os
import sys
import sqlite3
import json
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

    def _partial_match_score(self, query_tokens: Set[str], text: str) -> int:
        """Score text against query tokens with partial/stem matching."""
        score = 0
        text_lower = text.lower()
        text_parts = set(text_lower.replace('/', ' ').replace('\\', ' ')
                         .replace('_', ' ').replace('.', ' ').split())
        for qtoken in query_tokens:
            for tpart in text_parts:
                if not tpart:
                    continue
                # Exact match
                if qtoken == tpart:
                    score += 3
                # Query token is a prefix of text part (e.g., "auth" in "authentication")
                elif tpart.startswith(qtoken) or qtoken.startswith(tpart):
                    score += 2
                # Substring match
                elif qtoken in tpart or tpart in qtoken:
                    score += 1
        return score

    def _semantic_search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        if not self.archive_index:
            return self._fallback_search(query, limit)

        query_tokens = self._tokenize(query)
        scored = []
        for entry in self.archive_index:
            purpose = entry.get('purpose_summary', '')
            tokens = self._tokenize(purpose)
            score = len(query_tokens.intersection(tokens))
            # Also try partial matching on purpose text
            if score == 0:
                score = self._partial_match_score(query_tokens, purpose)
            if score > 0:
                scored.append({
                    'file_path': entry.get('file_path'),
                    'purpose_summary': purpose,
                    'score': score
                })

        # If archive search found nothing, fall back to DB search
        if not scored:
            return self._fallback_search(query, limit)

        scored.sort(key=lambda item: item['score'], reverse=True)
        return scored[:limit]

    def _fallback_search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        if not os.path.exists(self.db_path):
            return []
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            matches = []
            query_tokens = self._tokenize(query)

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
                    score = self._partial_match_score(query_tokens, purpose)
                    if score > 0:
                        matches.append({'file_path': row['file_path'], 'purpose_summary': purpose, 'score': score})

            # Search core_symbols table for symbol name matches
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='core_symbols'")
            has_symbols = cursor.fetchone() is not None
            if has_symbols and self.project_id != 'global':
                cursor.execute(
                    "SELECT file_path, symbol_name, symbol_type FROM core_symbols WHERE project_id = ?",
                    (self.project_id,)
                )
                symbol_matches: Dict[str, Dict[str, Any]] = {}
                for row in cursor.fetchall():
                    sym_name = row['symbol_name'] or ''
                    sym_score = self._partial_match_score(query_tokens, sym_name)
                    if sym_score > 0:
                        fp = row['file_path']
                        if fp not in symbol_matches or sym_score > symbol_matches[fp]['score']:
                            symbol_matches[fp] = {
                                'file_path': fp,
                                'purpose_summary': f'{row["symbol_type"]} {sym_name}',
                                'score': sym_score
                            }
                matches.extend(symbol_matches.values())

            # Fall back to quality_files for path-based matching
            if self.project_id != 'global':
                cursor.execute(
                    "SELECT file_path, language FROM quality_files WHERE project_id = ?",
                    (self.project_id,)
                )
                for row in cursor.fetchall():
                    path = row['file_path'] or ''
                    lang = row['language'] or ''
                    # Check if already matched via symbols
                    if any(m['file_path'] == path for m in matches):
                        continue
                    score = self._partial_match_score(query_tokens, f"{path} {lang}")
                    if score > 0:
                        matches.append({'file_path': path, 'purpose_summary': f'[{lang}] {path}', 'score': score})

            matches.sort(key=lambda item: item['score'], reverse=True)
            return matches[:limit]
        except Exception as exc:
            print(f"[NavigatorAgent] Fallback search failed: {exc}", file=sys.stderr)
            return []
        finally:
            conn.close()

    def _get_all_files(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return all files from quality_files when no query is given."""
        if not os.path.exists(self.db_path) or self.project_id == 'global':
            return []
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT file_path, language FROM quality_files WHERE project_id = ? ORDER BY file_path LIMIT ?",
                (self.project_id, limit)
            )
            return [
                {'file_path': row['file_path'], 'purpose_summary': f'[{row["language"]}] {row["file_path"]}', 'score': 1}
                for row in cursor.fetchall()
            ]
        except Exception as exc:
            print(f"[NavigatorAgent] _get_all_files failed: {exc}", file=sys.stderr)
            return []
        finally:
            conn.close()

    def _get_most_depended(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Return files with the most dependents when no target is given."""
        if not os.path.exists(self.db_path):
            return []
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dependencies'")
            if not cursor.fetchone():
                return []
            cursor.execute(
                "SELECT import_path, COUNT(*) as dep_count FROM dependencies "
                "GROUP BY import_path ORDER BY dep_count DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as exc:
            print(f"[NavigatorAgent] _get_most_depended failed: {exc}", file=sys.stderr)
            return []
        finally:
            conn.close()

    def find_implementation(self, query: str = '', limit: int = 5) -> Dict[str, Any]:
        print(f"[NavigatorAgent] Running find_implementation for query: {query or '(all files)'}", file=sys.stderr)
        if not query:
            matches = self._get_all_files(limit=limit)
            return {'tool': 'find_implementation', 'query': '', 'matches': matches, 'auto': True}
        matches = self._semantic_search(query, limit=limit)
        return {'tool': 'find_implementation', 'query': query, 'matches': matches}

    def trace_lineage(
        self,
        dataset_name: str = '',
        direction: str = 'forward',
        max_steps: int = 5
    ) -> Dict[str, Any]:
        print(f"[NavigatorAgent] Running trace_lineage for dataset: {dataset_name or '(all)'}", file=sys.stderr)
        if not os.path.exists(self.db_path):
            return {'tool': 'trace_lineage', 'paths': []}

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # If no dataset specified, return all lineage edges for the project
            if not dataset_name:
                cursor.execute(
                    "SELECT source_dataset, target_dataset, source_file, line_range FROM data_lineage_edges "
                    "WHERE project_id = ? ORDER BY source_dataset LIMIT ?",
                    (self.project_id, max_steps)
                )
                paths = [dict(row) for row in cursor.fetchall()]
                return {'tool': 'trace_lineage', 'direction': direction, 'dataset': '', 'paths': paths, 'auto': True}

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

    def blast_radius(self, target_file: str = '', max_depth: int = 3) -> Dict[str, Any]:
        print(f"[NavigatorAgent] Running blast_radius for file: {target_file or '(no target, showing overview)'}", file=sys.stderr)
        if not os.path.exists(self.db_path):
            return {'tool': 'blast_radius', 'impacted_files': []}

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # If no target given, show most-depended-upon files as overview
            if not target_file:
                most_depended = self._get_most_depended(limit=10)
                return {
                    'tool': 'blast_radius',
                    'target_file': '',
                    'impacted_files': [
                        {'file_path': d['import_path'], 'depth': 0, 'depends_on': ''}
                        for d in most_depended
                    ],
                    'risk_score': 0.0,
                    'classification': 'overview',
                    'auto': True,
                    'message': 'No target specified. Showing most-imported files in the project. Enter a file path to analyze its blast radius.'
                }

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

    def explain_module(self, file_path: str = '') -> Dict[str, Any]:
        print(f"[NavigatorAgent] Running explain_module for file: {file_path or '(all files)'}", file=sys.stderr)
        if not os.path.exists(self.db_path):
            return {'tool': 'explain_module', 'file_path': file_path, 'summary': ''}

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # If no file specified, list all project files with symbol counts
            if not file_path:
                files = self._get_all_files(limit=50)
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='core_symbols'")
                has_symbols = cursor.fetchone() is not None
                if has_symbols and self.project_id != 'global':
                    for f in files:
                        cursor.execute(
                            "SELECT COUNT(*) as cnt FROM core_symbols WHERE project_id = ? AND file_path = ?",
                            (self.project_id, f['file_path'])
                        )
                        row = cursor.fetchone()
                        f['symbol_count'] = row['cnt'] if row else 0
                # Build a language breakdown summary
                lang_counts: Dict[str, int] = {}
                for f in files:
                    lang = f.get('purpose_summary', '')
                    if lang.startswith('['):
                        lang = lang[1:lang.index(']')]
                    else:
                        lang = f.get('language', 'Unknown')
                    lang_counts[lang] = lang_counts.get(lang, 0) + 1

                lang_summary = ', '.join(f'{c} {lang}' for lang, c in sorted(lang_counts.items(), key=lambda x: -x[1])[:6])

                top_files = sorted(
                    [f for f in files if f.get('symbol_count', 0) > 0],
                    key=lambda x: -x['symbol_count']
                )[:5]
                top_summary = '; '.join(f'{f["file_path"]} ({f["symbol_count"]} syms)' for f in top_files)

                summary_parts = [f'{len(files)} files across {len(lang_counts)} languages: {lang_summary}.']
                if top_summary:
                    summary_parts.append(f' Top by symbols: {top_summary}.')
                summary_parts.append(' Click any file below for details.')

                return {
                    'tool': 'explain_module',
                    'file_path': '',
                    'summary': ' '.join(summary_parts),
                    'files': files,
                    'auto': True
                }

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
            q = query or target or ''
            limit = 50 if not q else max(5, max_depth * 5)
            return self.find_implementation(query=q, limit=limit)
        if tool_name == 'trace_lineage':
            return self.trace_lineage(dataset_name=target or query or '', direction=direction, max_steps=max_depth)
        if tool_name == 'blast_radius':
            return self.blast_radius(target_file=target or query or '', max_depth=max_depth)
        if tool_name == 'explain_module':
            return self.explain_module(file_path=target or query or '')
        return {'tool': tool_name, 'error': 'Unknown tool'}

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return self.run_tool(
            state.get('tool', ''),
            query=state.get('query'),
            target=state.get('target'),
            direction=state.get('direction', 'forward'),
            max_depth=state.get('max_depth', 3)
        )

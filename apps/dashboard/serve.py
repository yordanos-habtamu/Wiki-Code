#!/usr/bin/env python3
"""
WikiHub Dashboard - Enhanced Server with SQLite API Gateway
Serves static assets + provides REST API endpoints reading from hub.db
All logging routed to stderr for stream purity compliance.
"""
import http.server
import socketserver
import sqlite3
import json
import sys
import os
import subprocess
import threading
import time
import urllib.request
import urllib.error
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# Configuration
PORT = 3000
DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DASHBOARD_DIR, '..', 'cli', 'hub.db')

# Resolve to absolute path
DB_PATH = os.path.abspath(DB_PATH)



# Global workspace context (in-memory session state)
active_workspace = {
    "project_id": None,
    "project_name": None,
    "repo_path": None
}

# Job status registry for tracking background processes
job_registry = {
    # "job_id": {
    #     "status": "running|completed|failed",
    #     "progress": 0-100,
    #     "message": "Current operation",
    #     "active_file": "File being processed",
    #     "started_at": timestamp,
    #     "completed_at": timestamp,
    #     "process": Popen object
    # }
}

def log(message):
    """Stream purity: All logs to stderr only"""
    print(f"[Dashboard Server] {message}", file=sys.stderr, flush=True)


def locate_python_bin():
    """Locate the ai-core virtualenv python binary or fallback to system python3."""
    venv_python = os.path.abspath(os.path.join(DASHBOARD_DIR, '..', 'ai-core', '.venv', 'bin', 'python'))
    if os.path.exists(venv_python) and os.access(venv_python, os.X_OK):
        return venv_python
    return 'python3'


def get_db_connection():
    """Create a new database connection with Row factory"""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_project_schema():
    """Ensure `wiki_projects` table exists and has `target_model` column."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wiki_projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                repo_path TEXT UNIQUE NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Add column if missing
        cursor.execute("PRAGMA table_info(wiki_projects)")
        cols = [r[1] for r in cursor.fetchall()]
        if 'target_model' not in cols:
            try:
                cursor.execute("ALTER TABLE wiki_projects ADD COLUMN target_model TEXT DEFAULT 'google/gemini-2.5-flash'")
                conn.commit()
                log('ensure_project_schema: added target_model column')
            except Exception as e:
                log(f'ensure_project_schema: failed to add column: {e}')

        conn.close()
    except Exception as e:
        log(f'ensure_project_schema error: {e}')


def ensure_telemetry_schema():
    """Ensure token_telemetry_logs table exists for tracking LLM usage."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_telemetry_logs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                model_id TEXT NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                estimated_cost REAL DEFAULT 0.0,
                execution_status TEXT DEFAULT 'UNKNOWN',
                error_message TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_telemetry_project ON token_telemetry_logs(project_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_telemetry_created ON token_telemetry_logs(created_at)
        """)
        conn.commit()
        conn.close()
        log('ensure_telemetry_schema: token_telemetry_logs table ready')
    except Exception as e:
        log(f'ensure_telemetry_schema error: {e}')

def query_to_dict(cursor):
    """Convert SQLite Row objects to dictionaries"""
    return [dict(row) for row in cursor.fetchall()]

# Helper to resolve active project context from query or server state
def _resolve_project_id(query_params=None):
    if query_params:
        project_ids = query_params.get('project_id', [])
        if project_ids:
            return project_ids[0]
    return active_workspace.get('project_id')


def _table_exists(cursor, table_name):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table_name,))
    return cursor.fetchone() is not None


def _get_project_row(cursor, project_id):
    if not project_id or not _table_exists(cursor, 'wiki_projects'):
        return None
    cursor.execute("SELECT id, name, repo_path FROM wiki_projects WHERE id = ?", (project_id,))
    return cursor.fetchone()


def _empty_stats():
    return {
        "files": 0,
        "dependencies": 0,
        "languages": 0,
        "symbols": 0,
        "files_with_issues": 0,
        "token_usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "last_updated": datetime.now().isoformat()
    }


def _normalize_rel_path(path):
    normalized = (path or '').replace('\\', '/')
    while normalized.startswith('./'):
        normalized = normalized[2:]
    return normalized.lstrip('/')


def _dependency_target_candidates(import_path, source_file):
    """Map import strings from the Go scanner to likely repository file paths."""
    raw = (import_path or '').replace('\\', '/').strip()
    source_dir = os.path.dirname(_normalize_rel_path(source_file))
    candidates = []

    def add(value):
        value = _normalize_rel_path(value)
        if value and value not in candidates:
            candidates.append(value)

    add(raw)

    if raw.startswith('.'):
        joined = os.path.normpath(os.path.join(source_dir, raw)).replace('\\', '/')
        add(joined)
    elif '/' in raw:
        add(raw)
    else:
        add(raw.replace('.', '/'))

    module_path = raw.replace('.', '/').replace('\\', '/')
    add(module_path)

    for base in list(candidates):
        root, ext = os.path.splitext(base)
        if ext:
            continue
        for suffix in ('.py', '.go', '.js', '.jsx', '.ts', '.tsx', '.php'):
            add(base + suffix)
        add(os.path.join(base, '__init__.py'))
        add(os.path.join(base, 'index.js'))
        add(os.path.join(base, 'index.ts'))
        add(os.path.join(base, 'index.tsx'))

    if '\\' in import_path:
        namespace_path = import_path.replace('\\', '/')
        add(namespace_path + '.php')
        add(os.path.basename(namespace_path) + '.php')

    return candidates


def _resolve_dependency_target(import_path, source_file, file_map):
    for candidate in _dependency_target_candidates(import_path, source_file):
        if candidate in file_map:
            return candidate
    basename = os.path.basename(import_path.replace('\\', '/'))
    if basename:
        for file_path in file_map:
            if os.path.splitext(os.path.basename(file_path))[0] == basename:
                return file_path
    return None


def _add_topology_link(links_by_pair, nodes, source_idx, target_idx, relationship, weight=1):
    if source_idx is None or target_idx is None or source_idx == target_idx:
        return
    key = (source_idx, target_idx, relationship)
    if key not in links_by_pair:
        links_by_pair[key] = {
            "source": source_idx,
            "target": target_idx,
            "weight": 0,
            "relationship": relationship,
            "isCrossLanguage": nodes[source_idx].get('lang', '') != nodes[target_idx].get('lang', '')
        }
    links_by_pair[key]["weight"] += weight

# ==================== API ENDPOINT HANDLERS ====================

def handle_stats(query_params=None):
    """GET /api/v1/stats - Aggregate database metrics"""
    project_id = _resolve_project_id(query_params)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        project = _get_project_row(cursor, project_id)
        if not project:
            conn.close()
            return {
                "success": True,
                "data": _empty_stats(),
                "message": "Select a project to load project-scoped statistics"
            }
        
        cursor.execute("SELECT COUNT(*) as count FROM quality_files WHERE project_id = ?", (project_id,))
        total_files = cursor.fetchone()['count']
        cursor.execute("SELECT COALESCE(SUM(dependency_count), 0) as count FROM quality_files WHERE project_id = ?", (project_id,))
        total_deps = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(DISTINCT language) as count FROM quality_files WHERE project_id = ?", (project_id,))
        distinct_languages = cursor.fetchone()['count']
        cursor.execute("SELECT COALESCE(SUM(symbol_count), 0) as count FROM quality_files WHERE project_id = ?", (project_id,))
        total_symbols = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM quality_files WHERE project_id = ? AND quality_score < 7.0", (project_id,))
        files_with_issues = cursor.fetchone()['count']
        
        if _table_exists(cursor, 'token_usage'):
            cursor.execute("PRAGMA table_info(token_usage)")
            token_cols = [row[1] for row in cursor.fetchall()]
            token_project_filter = "WHERE project_id = ?" if 'project_id' in token_cols else ""
            token_params = (project_id,) if 'project_id' in token_cols else ()
            cursor.execute("""
                SELECT 
                    COALESCE(SUM(prompt_tokens), 0) as input_tokens,
                    COALESCE(SUM(completion_tokens), 0) as output_tokens,
                    COALESCE(SUM(total_tokens), 0) as total_tokens
                FROM token_usage
                """ + token_project_filter, token_params)
            token_stats = dict(cursor.fetchone())
        else:
            token_stats = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        
        conn.close()
        
        return {
            "success": True,
            "data": {
                "files": total_files,
                "dependencies": total_deps,
                "languages": distinct_languages,
                "symbols": total_symbols,
                "files_with_issues": files_with_issues,
                "token_usage": token_stats,
                "last_updated": datetime.now().isoformat()
            }
        }
    except Exception as e:
        log(f"ERROR in /api/v1/stats: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": _empty_stats()
        }

def _ensure_quality_schema():
    """Ensure quality_files table has entity_count and file_size columns."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(quality_files)")
        cols = [r[1] for r in cursor.fetchall()]
        if 'entity_count' not in cols:
            cursor.execute("ALTER TABLE quality_files ADD COLUMN entity_count INTEGER DEFAULT 0")
            log('_ensure_quality_schema: added entity_count column')
        if 'file_size' not in cols:
            cursor.execute("ALTER TABLE quality_files ADD COLUMN file_size INTEGER DEFAULT 0")
            log('_ensure_quality_schema: added file_size column')
        conn.commit()
        conn.close()
    except Exception as e:
        log(f'_ensure_quality_schema error: {e}')


def handle_quality(query_params=None):
    """GET /api/v1/quality - File quality analysis data"""
    project_id = _resolve_project_id(query_params)
    try:
        _ensure_quality_schema()

        conn = get_db_connection()
        cursor = conn.cursor()
        project = _get_project_row(cursor, project_id)
        if not project:
            conn.close()
            return {
                "success": True,
                "data": [],
                "message": "Select a project to load project-scoped quality data"
            }
        
        cursor.execute("""
            SELECT
                file_path as path,
                language,
                quality_score,
                complexity,
                symbol_count,
                dependency_count,
                entity_count,
                file_size
            FROM quality_files
            WHERE project_id = ?
            ORDER BY file_path
        """, (project_id,))
        
        files = query_to_dict(cursor)

        # Resolve repo_path for file_size backfill from disk if needed
        repo_path = None
        if project_id:
            try:
                cursor.execute("SELECT repo_path FROM wiki_projects WHERE id = ?", (project_id,))
                proj_row = cursor.fetchone()
                if proj_row:
                    repo_path = proj_row['repo_path']
            except Exception:
                pass

        quality_data = []
        for file in files:
            score = float(file.get('quality_score', 0.0) or 0.0)
            symbols = int(file.get('symbol_count', 0) or 0)
            deps = int(file.get('dependency_count', 0) or 0)
            complexity = int(file.get('complexity', 0) or 0)
            entity_count = int(file.get('entity_count', 0) or 0)
            file_size = int(file.get('file_size', 0) or 0)

            # Backfill entity_count from symbol_count if zero
            if entity_count == 0 and symbols > 0:
                entity_count = symbols

            # Backfill file_size from disk if zero and repo_path available
            if file_size == 0 and repo_path:
                try:
                    abs_path = os.path.join(repo_path, file['path'])
                    if os.path.exists(abs_path):
                        file_size = os.path.getsize(abs_path)
                except Exception:
                    pass

            complexity_ratio = deps / symbols if symbols > 0 else 0
            
            if score >= 9.0:
                priority = "Isolated"
            elif score >= 7.5:
                priority = "Low"
            elif score >= 6.0:
                priority = "Medium"
            elif score >= 4.0:
                priority = "High"
            else:
                priority = "Critical"
            
            smell_count = 0
            smells = []
            
            if complexity_ratio > 2.0:
                smell_count += 1
                smells.append({
                    "type": "High Cyclomatic Coupling",
                    "description": f"Dependency-to-symbol ratio ({complexity_ratio:.1f}:1) exceeds recommended threshold"
                })
            if complexity > 15:
                smell_count += 1
                smells.append({
                    "type": "Excessive Module Complexity",
                    "description": f"Complexity score ({complexity}) exceeds moderate threshold"
                })
            if deps > 10:
                smell_count += 1
                smells.append({
                    "type": "Interface Inflation",
                    "description": f"Dependency count ({deps}) suggests coupling risk"
                })
            if score < 5.0 and smell_count == 0:
                smell_count = 1
                smells.append({
                    "type": "Low Quality Score",
                    "description": "Quality score is below acceptable levels"
                })
            
            quality_data.append({
                "path": file['path'],
                "language": file['language'],
                "score": round(score, 1),
                "priority": priority,
                "smellCount": smell_count,
                "smells": smells,
                "symbol_count": symbols,
                "dependency_count": deps,
                "entity_count": entity_count,
                "file_size": file_size,
                "metrics": {
                    "symbols": symbols,
                    "dependencies": deps,
                    "complexity": complexity,
                    "complexityRatio": f"{complexity_ratio:.1f}:1"
                }
            })
        
        conn.close()
        
        return {
            "success": True,
            "data": quality_data
        }
    except Exception as e:
        log(f"ERROR in /api/v1/quality: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": []
        }

def handle_topology(query_params=None):
    """GET /api/v1/topology - Dependency graph for visualization"""
    project_id = _resolve_project_id(query_params)
    selected_commit = ''
    if query_params:
        selected_commit = query_params.get('commit', [''])[0]
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        project = _get_project_row(cursor, project_id)
        if not project:
            conn.close()
            return {
                "success": True,
                "data": {
                    "nodes": [],
                    "links": [],
                    "meta": {
                        "project_id": project_id,
                        "repo_path": None,
                        "selected_commit": selected_commit,
                        "latest_commit": None,
                        "node_count": 0,
                        "link_count": 0,
                        "relationship_types": [],
                        "last_updated": datetime.now().isoformat()
                    }
                },
                "message": "Select a project to load project-scoped topology"
            }
        repo_path = project['repo_path'] if project else active_workspace.get('repo_path')
        
        cursor.execute("""
            SELECT 
                file_path as id,
                language as lang,
                quality_score,
                complexity,
                symbol_count,
                dependency_count
            FROM quality_files
            WHERE project_id = ?
            ORDER BY file_path
        """, (project_id,))
        
        files = query_to_dict(cursor)
        
        selected_commit_changes = {}
        if project_id and selected_commit and _table_exists(cursor, 'git_file_changes'):
            cursor.execute("""
                SELECT file_path, status, lines_added, lines_removed
                FROM git_file_changes
                WHERE project_id = ? AND commit_hash = ?
            """, (project_id, selected_commit))
            selected_commit_changes = {
                row['file_path']: {
                    "status": row['status'],
                    "lines_added": row['lines_added'],
                    "lines_removed": row['lines_removed']
                }
                for row in cursor.fetchall()
            }

        if selected_commit and not selected_commit_changes:
            diff_result = handle_git_diff(selected_commit)
            if diff_result.get('success'):
                for file_info in diff_result.get('data', {}).get('files', []):
                    path = _normalize_rel_path(file_info.get('path'))
                    selected_commit_changes[path] = {
                        "status": file_info.get('status'),
                        "lines_added": file_info.get('added', 0),
                        "lines_removed": file_info.get('removed', 0)
                    }

        nodes = []
        file_map = {}
        
        canvas_width = 800
        canvas_height = 500
        center_x = canvas_width / 2
        center_y = canvas_height / 2
        radius = min(canvas_width, canvas_height) * 0.35
        
        for idx, file in enumerate(files):
            x = center_x + radius * 0.5
            y = center_y + radius * 0.5
            
            base_weight = file.get('complexity', file.get('entity_count', 0)) or 0
            weight = 12 + min(8, int(base_weight * 0.5))
            
            score = float(file.get('quality_score', 0.0) or 0.0)
            if score == 0.0 and file.get('entity_count') is not None:
                symbols = file.get('entity_count', 0)
                score = 10.0 if symbols < 10 else max(5.0, 10.0 - (symbols - 10) * 0.5)
            
            node = {
                "id": file['id'],
                "lang": file.get('lang', 'Unknown'),
                "score": round(score, 1),
                "weight": int(weight),
                "smells": 0,
                "changedInSelectedCommit": file['id'] in selected_commit_changes,
                "change": selected_commit_changes.get(file['id']),
                "x": x + (idx * 50) % 200 - 100,
                "y": y + (idx * 70) % 150 - 75,
                "vx": 0,
                "vy": 0
            }
            
            nodes.append(node)
            file_map[file['id']] = idx
        
        links_by_pair = {}
        if _table_exists(cursor, 'git_file_changes'):
            params = [project_id]
            commit_filter = ""
            if selected_commit:
                commit_filter = " AND commit_hash = ?"
                params.append(selected_commit)
            cursor.execute(f"""
                SELECT commit_hash, file_path
                FROM git_file_changes
                WHERE project_id = ?{commit_filter}
                ORDER BY commit_hash
            """, tuple(params))
            commit_rows = query_to_dict(cursor)
            commit_files = {}
            for row in commit_rows:
                normalized_file = _normalize_rel_path(row['file_path'])
                if normalized_file in file_map:
                    commit_files.setdefault(row['commit_hash'], []).append(normalized_file)

            for files_in_commit in commit_files.values():
                unique_files = sorted(set(files_in_commit))
                for i in range(len(unique_files)):
                    for j in range(i + 1, len(unique_files)):
                        source_idx = file_map.get(unique_files[i])
                        target_idx = file_map.get(unique_files[j])
                        _add_topology_link(links_by_pair, nodes, source_idx, target_idx, "commit_cochange")

        if selected_commit and selected_commit_changes:
            unique_files = sorted(path for path in selected_commit_changes if path in file_map)
            for i in range(len(unique_files)):
                for j in range(i + 1, len(unique_files)):
                    _add_topology_link(
                        links_by_pair,
                        nodes,
                        file_map.get(unique_files[i]),
                        file_map.get(unique_files[j]),
                        "selected_commit"
                    )

        if _table_exists(cursor, 'dependencies'):
            cursor.execute("SELECT source_file, import_path FROM dependencies ORDER BY source_file")
            deps = query_to_dict(cursor)
            for dep in deps:
                source_file = _normalize_rel_path(dep['source_file'])
                if source_file not in file_map:
                    continue
                target_file = _resolve_dependency_target(dep['import_path'], source_file, file_map)
                if target_file:
                    _add_topology_link(
                        links_by_pair,
                        nodes,
                        file_map.get(source_file),
                        file_map.get(target_file),
                        "imports"
                    )

        links = list(links_by_pair.values())

        latest_commit = None
        if project_id and _table_exists(cursor, 'git_commits'):
            cursor.execute("""
                SELECT commit_hash, short_hash, timestamp, message
                FROM git_commits
                WHERE project_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """, (project_id,))
            latest_row = cursor.fetchone()
            if latest_row:
                latest_commit = dict(latest_row)
        
        for link in links:
            if link.get('isCrossLanguage'):
                nodes[link['source']]['smells'] += 1
        
        conn.close()
        
        return {
            "success": True,
            "data": {
                "nodes": nodes,
                "links": links,
                "meta": {
                    "project_id": project_id,
                    "repo_path": repo_path,
                    "selected_commit": selected_commit,
                    "latest_commit": latest_commit,
                    "node_count": len(nodes),
                    "link_count": len(links),
                    "relationship_types": sorted(set(link.get('relationship', 'unknown') for link in links)),
                    "last_updated": datetime.now().isoformat()
                }
            }
        }
    except Exception as e:
        log(f"ERROR in /api/v1/topology: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": {"nodes": [], "links": []}
        }


def handle_lineage_trace(query_params=None):
    """GET /api/v1/lineage/trace - Upstream/downstream lineage for a dataset"""
    project_id = _resolve_project_id(query_params)
    dataset = ''
    if query_params:
        dataset = query_params.get('dataset', [''])[0]

    if not dataset:
        return {
            "success": False,
            "error": "Missing dataset parameter",
            "data": {}
        }

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT source_dataset, target_dataset FROM data_lineage_edges WHERE project_id = ?", (project_id,))
        rows = query_to_dict(cursor)

        upstream = set()
        downstream = set()
        queue = [dataset]

        while queue:
            current = queue.pop(0)
            for row in rows:
                if row['target_dataset'] == current and row['source_dataset'] not in upstream:
                    upstream.add(row['source_dataset'])
                    queue.append(row['source_dataset'])
                if row['source_dataset'] == current and row['target_dataset'] not in downstream:
                    downstream.add(row['target_dataset'])
                    queue.append(row['target_dataset'])

        conn.close()

        return {
            "success": True,
            "data": {
                "dataset": dataset,
                "upstream": sorted(upstream),
                "downstream": sorted(downstream)
            }
        }
    except Exception as e:
        log(f"ERROR in /api/v1/lineage/trace: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": {}
        }


def handle_blast_radius(query_params=None):
    """GET /api/v1/topology/blast-radius - Dependent file radius for a public file signature"""
    project_id = _resolve_project_id(query_params)
    file_path = ''
    if query_params:
        file_path = query_params.get('file_path', [''])[0]

    if not file_path:
        return {
            "success": False,
            "error": "Missing file_path parameter",
            "data": {}
        }

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        project = _get_project_row(cursor, project_id)

        cursor.execute(
            "SELECT symbol_name FROM core_symbols WHERE project_id = ? AND file_path = ?",
            (project_id, file_path)
        )
        symbol_rows = cursor.fetchall()
        public_symbols = [row[0] for row in symbol_rows]

        cursor.execute(
            "SELECT target_dataset FROM data_lineage_edges WHERE project_id = ? AND source_file = ?",
            (project_id, file_path)
        )
        produced_rows = query_to_dict(cursor)
        produced_datasets = {row['target_dataset'] for row in produced_rows if row.get('target_dataset')}

        dependent_files = set()
        if produced_datasets:
            query_placeholders = ','.join('?' for _ in produced_datasets)
            cursor.execute(
                f"SELECT DISTINCT source_file FROM data_lineage_edges WHERE project_id = ? AND source_dataset IN ({query_placeholders})",
                (project_id, *sorted(produced_datasets))
            )
            dependent_rows = query_to_dict(cursor)
            for row in dependent_rows:
                if row['source_file'] != file_path:
                    dependent_files.add(row['source_file'])

        if not dependent_files:
            file_map = {}
            if project_id and _table_exists(cursor, 'quality_files'):
                cursor.execute("SELECT file_path FROM quality_files WHERE project_id = ?", (project_id,))
                file_map = {_normalize_rel_path(row['file_path']): True for row in cursor.fetchall()}
            elif _table_exists(cursor, 'files'):
                cursor.execute("SELECT relative_path FROM files")
                file_map = {_normalize_rel_path(row['relative_path']): True for row in cursor.fetchall()}

            cursor.execute("SELECT source_file, import_path FROM dependencies")
            deps = query_to_dict(cursor)
            dependency_graph = {}
            for dep in deps:
                source_file = _normalize_rel_path(dep['source_file'])
                if file_map and source_file not in file_map:
                    continue
                target_file = _resolve_dependency_target(dep['import_path'], source_file, file_map)
                if target_file:
                    dependency_graph.setdefault(target_file, []).append(source_file)

            queue = [_normalize_rel_path(file_path)]
            while queue:
                current = queue.pop(0)
                for dependent in dependency_graph.get(current, []):
                    if dependent not in dependent_files:
                        dependent_files.add(dependent)
                        queue.append(dependent)

        conn.close()

        return {
            "success": True,
            "data": {
                "file_path": file_path,
                "public_symbols": public_symbols,
                "dependent_files": sorted(dependent_files),
                "repo_path": project['repo_path'] if project else active_workspace.get('repo_path')
            }
        }
    except Exception as e:
        log(f"ERROR in /api/v1/topology/blast-radius: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": {}
        }

# ==================== FILE IMPORTANCE AI ENDPOINT ====================

def handle_file_importance(handler):
    """POST /api/v1/topology/file-importance - AI-powered file importance analysis."""
    try:
        content_length = int(handler.headers.get('Content-Length', 0))
        body = handler.rfile.read(content_length)
        data = json.loads(body)

        project_id = data.get('project_id', '').strip()
        file_path = data.get('file_path', '').strip()

        if not project_id:
            return {"success": False, "error": "project_id is required"}
        if not file_path:
            return {"success": False, "error": "file_path is required"}

        conn = get_db_connection()
        cursor = conn.cursor()

        project = _get_project_row(cursor, project_id)
        if not project:
            conn.close()
            return {"success": False, "error": "Project not found"}

        # 1. Quality file data
        quality = None
        cursor.execute(
            "SELECT file_path, language, quality_score, complexity, symbol_count, dependency_count, entity_count, file_size "
            "FROM quality_files WHERE project_id = ? AND file_path = ?",
            (project_id, file_path)
        )
        qrow = cursor.fetchone()
        if qrow:
            quality = dict(qrow)

        # 2. Symbols defined in this file
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='core_symbols'")
        has_symbols = cursor.fetchone() is not None
        symbols = []
        if has_symbols:
            cursor.execute(
                "SELECT symbol_name, symbol_type FROM core_symbols WHERE project_id = ? AND file_path = ? LIMIT 20",
                (project_id, file_path)
            )
            symbols = [dict(r) for r in cursor.fetchall()]

        # 3. Outgoing dependencies (what this file imports)
        outgoing_deps = []
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dependencies'")
        has_deps = cursor.fetchone() is not None
        if has_deps:
            cursor.execute("PRAGMA table_info(dependencies)")
            dep_cols = [r['name'] for r in cursor.fetchall()]
            if 'project_id' in dep_cols:
                cursor.execute(
                    "SELECT DISTINCT import_path FROM dependencies WHERE project_id = ? AND source_file = ? LIMIT 30",
                    (project_id, file_path)
                )
            else:
                cursor.execute(
                    "SELECT DISTINCT import_path FROM dependencies WHERE source_file = ? LIMIT 30",
                    (file_path,)
                )
            outgoing_deps = [r['import_path'] for r in cursor.fetchall()]

        # 4. Incoming dependencies (what imports this file)
        incoming_deps = []
        deps_has_project_id = has_deps and 'project_id' in dep_cols
        if has_deps:
            import_path_guess = file_path.replace('/', '.').rsplit('.', 1)[0] if '.' in file_path else file_path
            if deps_has_project_id:
                cursor.execute(
                    "SELECT DISTINCT source_file FROM dependencies WHERE project_id = ? AND import_path = ? LIMIT 30",
                    (project_id, import_path_guess)
                )
            else:
                cursor.execute(
                    "SELECT DISTINCT source_file FROM dependencies WHERE import_path = ? LIMIT 30",
                    (import_path_guess,)
                )
            incoming_deps = [r['source_file'] for r in cursor.fetchall()]

        # 5. Git change frequency
        change_count = 0
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='git_file_changes'")
        has_git = cursor.fetchone() is not None
        if has_git:
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM git_file_changes WHERE project_id = ? AND file_path = ?",
                (project_id, file_path)
            )
            row = cursor.fetchone()
            change_count = row['cnt'] if row else 0

        conn.close()

        # Build context for the AI
        lang = quality['language'] if quality else 'Unknown'
        score = quality['quality_score'] if quality else 0
        sym_count = quality['symbol_count'] if quality else 0
        dep_count = quality['dependency_count'] if quality else 0
        ent_count = quality['entity_count'] if quality else 0
        file_size = quality['file_size'] if quality else 0
        complexity = quality['complexity'] if quality else 0

        symbol_names = ', '.join(s['symbol_name'] for s in symbols) if symbols else 'none'

        prompt = f"""Analyze the importance of this file in the project. Return ONLY valid JSON with these fields.

File: {file_path}
Language: {lang}
Quality Score: {score}/10
Complexity: {complexity}
Symbols: {sym_count} ({symbol_names})
Dependencies (imports): {dep_count}
Outgoing imports: {', '.join(outgoing_deps[:10]) if outgoing_deps else 'none'}
Incoming dependents: {len(incoming_deps)} files
Git change frequency: {change_count} commits
Entity count: {ent_count}
File size: {file_size} bytes

Respond with JSON only:
{{
  "centrality": "low|medium|high|critical",
  "change_frequency": "stable|moderate|frequent|very_frequent",
  "complexity_rating": "simple|moderate|complex|very_complex",
  "criticality": "low|medium|high|critical",
  "risk_assessment": "<1-2 sentence risk description>",
  "explanation": "<2-3 sentence importance explanation>"
}}"""

        # Call AI provider
        result = process_live_agent_inference(project_id, prompt)

        if not result.get('success'):
            return {
                "success": False,
                "error": "AI inference failed",
                "message": result.get('message', 'Unknown AI error'),
                "context": {
                    "file_path": file_path,
                    "language": lang,
                    "quality_score": score,
                    "symbols": sym_count,
                    "dependencies": dep_count,
                    "incoming_dependents": len(incoming_deps),
                    "change_count": change_count
                }
            }

        # Parse AI response as JSON
        ai_text = result.get('suggestion', '')
        try:
            # Try to extract JSON from the response (handle markdown fences)
            import re as regex
            json_match = regex.search(r'\{.*\}', ai_text, regex.DOTALL)
            if json_match:
                importance = json.loads(json_match.group())
            else:
                importance = json.loads(ai_text)
        except (json.JSONDecodeError, Exception):
            importance = {
                "centrality": "unknown",
                "change_frequency": "unknown",
                "complexity_rating": "unknown",
                "criticality": "unknown",
                "risk_assessment": "AI analysis could not be parsed.",
                "explanation": ai_text[:500]
            }

        return {
            "success": True,
            "data": {
                "file_path": file_path,
                "importance": importance,
                "context": {
                    "language": lang,
                    "quality_score": score,
                    "symbols": sym_count,
                    "dependencies": dep_count,
                    "incoming_dependents": len(incoming_deps),
                    "change_count": change_count
                }
            }
        }
    except Exception as e:
        log(f"Error in handle_file_importance: {e}")
        return {"success": False, "error": str(e)}


# ==================== CONFIGURATION ENDPOINTS ====================

# Configuration file path
CONFIG_FILE = os.path.join(DASHBOARD_DIR, '..', 'cli', 'wikihub_config.json')

def _default_config():
    return {
        "providers": {
            "openrouter": {"apiKey": "", "defaultModel": "", "status": "not_configured"},
            "gemini": {"apiKey": "", "status": "not_configured"},
            "deepseek": {"apiKey": "", "status": "not_configured"},
            "qwen": {"apiKey": "", "status": "not_configured"}
        },
        "system": {
            "defaultModel": "",
            "tokenBudget": 100000
        },
        "github": {
            "token": "",
            "status": "not_configured"
        }
    }


def _dashboard_provider_config(provider_data):
    api_key = provider_data.get('apiKey') or provider_data.get('api_key') or ''
    default_model = provider_data.get('defaultModel') or ''
    models = provider_data.get('models') or []
    if not default_model and isinstance(models, list) and models:
        default_model = models[0]
    return {
        "apiKey": api_key,
        "defaultModel": default_model,
        "status": "configured" if api_key else provider_data.get('status', 'not_configured')
    }


def _merge_config(base, incoming):
    if not isinstance(incoming, dict):
        return base
    providers = incoming.get('providers', incoming)
    if isinstance(providers, dict):
        for provider in base['providers']:
            pdata = providers.get(provider)
            if isinstance(pdata, dict):
                normalized = _dashboard_provider_config(pdata)
                if normalized.get('apiKey') or not base['providers'][provider].get('apiKey'):
                    base['providers'][provider].update(normalized)
    system = incoming.get('system')
    if isinstance(system, dict):
        base['system'].update(system)
    github = incoming.get('github')
    if isinstance(github, dict):
        base['github'].update(github)
    return base


def load_config():
    """Load configuration from JSON file"""
    try:
        config = _default_config()
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = _merge_config(config, json.load(f))

        plaintext_provider_file = os.path.expanduser('~/.config/wikihub/providers.json')
        if os.path.exists(plaintext_provider_file):
            with open(plaintext_provider_file, 'r') as f:
                config = _merge_config(config, json.load(f))

        return config
    except Exception as e:
        log(f"ERROR loading config: {e}")
        return _default_config()

def save_config(config):
    """Save configuration to JSON file"""
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        log(f"ERROR saving config: {e}")
        return False

def _auto_set_project_model_from_vault(project_id):
    """Read the vault config and auto-set the project's target_model from the configured provider."""
    try:
        config = load_config()
        vault_providers = config.get('providers', {})
        system = config.get('system', {})

        for provider_name, pdata in vault_providers.items():
            api_key = pdata.get('apiKey', '') or pdata.get('api_key', '')
            status = pdata.get('status', 'not_configured')
            if api_key and status == 'configured':
                default_model = pdata.get('defaultModel', '') or ''
                # Build the target model string
                if default_model:
                    target_model = f'{provider_name}/{default_model}'
                else:
                    target_model = f'{provider_name}/default'
                # Fall back to system default if set
                system_default = system.get('defaultModel', '')
                if system_default:
                    target_model = system_default

                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("PRAGMA table_info(wiki_projects)")
                    cols = [r['name'] for r in cursor.fetchall()]
                    if 'target_model' in cols:
                        cursor.execute(
                            "UPDATE wiki_projects SET target_model = ? WHERE id = ? AND (target_model IS NULL OR target_model = '')",
                            (target_model, project_id)
                        )
                        if cursor.rowcount > 0:
                            conn.commit()
                            log(f'Auto-set target_model={target_model} for project {project_id} from vault provider {provider_name}')
                except Exception:
                    pass
                finally:
                    conn.close()
                break
    except Exception as e:
        log(f'Error auto-setting project model from vault: {e}')


def handle_get_config():
    """GET /api/v1/config - Get provider configuration"""
    try:
        config = load_config()
        return {
            "success": True,
            "data": config
        }
    except Exception as e:
        log(f"ERROR in /api/v1/config: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": {}
        }

def handle_save_config(handler):
    """POST /api/v1/config - Save provider configuration"""
    try:
        content_length = int(handler.headers.get('Content-Length', 0))
        body = handler.rfile.read(content_length)
        data = json.loads(body)
        
        if save_config(data):
            log("Configuration saved successfully")
            # Auto-set the active project's target model from the vault
            active_pid = active_workspace.get('project_id')
            if active_pid:
                _auto_set_project_model_from_vault(active_pid)
            return {
                "success": True,
                "message": "Configuration saved"
            }
        else:
            return {
                "success": False,
                "error": "Failed to save configuration"
            }
    except Exception as e:
        log(f"ERROR in POST /api/v1/config: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ==================== PROJECT SETTINGS ENDPOINTS ====================

def handle_get_project_settings(query_params=None):
    """GET /api/v1/project/settings - Get project settings including target model."""
    project_id = _resolve_project_id(query_params)
    try:
        if not project_id:
            return {"success": False, "error": "No active project selected"}

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, target_model FROM wiki_projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {"success": False, "error": f"Project not found: {project_id}"}

        return {
            "success": True,
            "data": {
                "id": row["id"],
                "name": row["name"],
                "target_model": row["target_model"] or "google/gemini-2.5-flash"
            }
        }
    except Exception as e:
        log(f"ERROR in GET /api/v1/project/settings: {e}")
        return {"success": False, "error": str(e)}


def handle_post_project_settings(handler):
    """POST /api/v1/project/settings - Update project settings including target model."""
    try:
        content_length = int(handler.headers.get('Content-Length', 0))
        body = handler.rfile.read(content_length)
        data = json.loads(body)

        project_id = (data.get('project_id') or '').strip()
        target_model = (data.get('target_model') or '').strip()

        if not project_id:
            return {"success": False, "error": "project_id is required"}
        if not target_model:
            return {"success": False, "error": "target_model is required"}

        conn = get_db_connection()
        cursor = conn.cursor()

        # Ensure target_model column exists
        cursor.execute("PRAGMA table_info(wiki_projects)")
        cols = [r[1] for r in cursor.fetchall()]
        if 'target_model' not in cols:
            cursor.execute("ALTER TABLE wiki_projects ADD COLUMN target_model TEXT DEFAULT 'google/gemini-2.5-flash'")
            conn.commit()

        cursor.execute("SELECT id FROM wiki_projects WHERE id = ?", (project_id,))
        if not cursor.fetchone():
            conn.close()
            return {"success": False, "error": f"Project not found: {project_id}"}

        cursor.execute("UPDATE wiki_projects SET target_model = ? WHERE id = ?", (target_model, project_id))
        conn.commit()
        conn.close()

        log(f"Updated project {project_id} target_model to {target_model}")
        return {"success": True, "message": f"Model updated to {target_model}"}
    except Exception as e:
        log(f"ERROR in POST /api/v1/project/settings: {e}")
        return {"success": False, "error": str(e)}


# ==================== PROVIDER CONNECTION TEST ====================

def handle_test_provider_connection(handler):
    """POST /api/v1/config/test-connection - Test a provider API key."""
    try:
        content_length = int(handler.headers.get('Content-Length', 0))
        body = handler.rfile.read(content_length)
        data = json.loads(body)

        provider = (data.get('provider') or '').strip().lower()
        api_key = (data.get('api_key') or '').strip()

        if not provider:
            return {"success": False, "error": "provider is required"}
        if not api_key:
            return {"success": False, "error": "api_key is required"}

        import ssl
        ssl_ctx = ssl.create_default_context()

        if provider == 'openrouter':
            # Test OpenRouter connection by listing models with auth
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            req = urllib.request.Request(
                'https://openrouter.ai/api/v1/auth/key',
                headers=headers,
                method='GET'
            )
            try:
                with urllib.request.urlopen(req, timeout=10.0, context=ssl_ctx) as resp:
                    if resp.status == 200:
                        return {"success": True, "message": "OpenRouter API key verified successfully"}
                    return {"success": False, "error": f"OpenRouter returned status {resp.status}"}
            except urllib.error.HTTPError as http_err:
                if http_err.code == 401:
                    return {"success": False, "error": "OpenRouter API key is invalid"}
                return {"success": False, "error": f"OpenRouter HTTP error {http_err.code}"}
            except Exception as e:
                return {"success": False, "error": f"Connection failed: {str(e)}"}

        elif provider == 'gemini':
            # Test Google Gemini connection
            url = f'https://generativelanguage.googleapis.com/v1beta/models?key={api_key}'
            try:
                req = urllib.request.Request(url, method='GET')
                with urllib.request.urlopen(req, timeout=10.0, context=ssl_ctx) as resp:
                    if resp.status == 200:
                        return {"success": True, "message": "Google Gemini API key verified successfully"}
                    return {"success": False, "error": f"Gemini returned status {resp.status}"}
            except urllib.error.HTTPError as http_err:
                if http_err.code in (400, 401, 403):
                    return {"success": False, "error": "Gemini API key is invalid or unauthorized"}
                return {"success": False, "error": f"Gemini HTTP error {http_err.code}"}
            except Exception as e:
                return {"success": False, "error": f"Connection failed: {str(e)}"}

        elif provider == 'deepseek':
            # Test DeepSeek connection
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            req = urllib.request.Request(
                'https://api.deepseek.com/models',
                headers=headers,
                method='GET'
            )
            try:
                with urllib.request.urlopen(req, timeout=10.0, context=ssl_ctx) as resp:
                    if resp.status == 200:
                        return {"success": True, "message": "DeepSeek API key verified successfully"}
                    return {"success": False, "error": f"DeepSeek returned status {resp.status}"}
            except urllib.error.HTTPError as http_err:
                if http_err.code == 401:
                    return {"success": False, "error": "DeepSeek API key is invalid"}
                return {"success": False, "error": f"DeepSeek HTTP error {http_err.code}"}
            except Exception as e:
                return {"success": False, "error": f"Connection failed: {str(e)}"}

        elif provider == 'qwen':
            # Test Qwen connection (DashScope API)
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            req = urllib.request.Request(
                'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation',
                headers=headers,
                method='GET'
            )
            try:
                with urllib.request.urlopen(req, timeout=10.0, context=ssl_ctx) as resp:
                    if resp.status == 200:
                        return {"success": True, "message": "Qwen API key verified successfully"}
                    return {"success": False, "error": f"Qwen returned status {resp.status}"}
            except urllib.error.HTTPError as http_err:
                if http_err.code in (400, 401, 403):
                    return {"success": False, "error": "Qwen API key is invalid or unauthorized"}
                return {"success": False, "error": f"Qwen HTTP error {http_err.code}"}
            except Exception as e:
                return {"success": False, "error": f"Connection failed: {str(e)}"}

        else:
            return {"success": False, "error": f"Unknown provider: {provider}"}

    except Exception as e:
        log(f"ERROR in POST /api/v1/config/test-connection: {e}")
        return {"success": False, "error": str(e)}


# ==================== GITHUB CONNECTION & REMOTE INGESTION ====================

def handle_github_test_connection(handler):
    """POST /api/v1/github/test-connection - Validate GitHub PAT."""
    import ssl
    try:
        content_length = int(handler.headers.get('Content-Length', 0))
        body = handler.rfile.read(content_length)
        data = json.loads(body)
        token = (data.get('github_token') or '').strip()

        if not token:
            return {
                'success': False,
                'error': 'GitHub token is required'
            }

        ssl_ctx = ssl.create_default_context()

        # Try with Bearer first (works for both classic and fine-grained PATs)
        headers = {
            'Authorization': f'Bearer {token}',
            'User-Agent': 'WikiHub-Dashboard/1.0',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28'
        }

        request = urllib.request.Request(
            'https://api.github.com/user',
            headers=headers,
            method='GET'
        )

        try:
            with urllib.request.urlopen(request, timeout=10.0, context=ssl_ctx) as resp:
                if resp.status == 200:
                    user_data = json.loads(resp.read().decode('utf-8'))
                    username = user_data.get('login', 'unknown')
                    log(f"GitHub auth verified for user: {username}")
                    return {
                        'success': True,
                        'message': f'GitHub connection verified successfully (user: {username})'
                    }
                return {
                    'success': False,
                    'error': f'GitHub responded with status {resp.status}'
                }
        except urllib.error.HTTPError as http_err:
            if http_err.code == 401:
                # Try fallback with 'token' prefix for classic PATs
                headers_fallback = {
                    'Authorization': f'token {token}',
                    'User-Agent': 'WikiHub-Dashboard/1.0',
                    'Accept': 'application/vnd.github+json',
                    'X-GitHub-Api-Version': '2022-11-28'
                }
                request_fallback = urllib.request.Request(
                    'https://api.github.com/user',
                    headers=headers_fallback,
                    method='GET'
                )
                try:
                    with urllib.request.urlopen(request_fallback, timeout=10.0, context=ssl_ctx) as resp2:
                        if resp2.status == 200:
                            user_data = json.loads(resp2.read().decode('utf-8'))
                            username = user_data.get('login', 'unknown')
                            log(f"GitHub auth verified (fallback) for user: {username}")
                            return {
                                'success': True,
                                'message': f'GitHub connection verified successfully (user: {username})'
                            }
                except urllib.error.HTTPError as http_err2:
                    if http_err2.code == 401:
                        return {
                            'success': False,
                            'error': 'GitHub token is invalid or unauthorized. Please check your token and ensure it has the correct scopes.'
                        }
                    if http_err2.code == 403:
                        return {
                            'success': False,
                            'error': 'GitHub API rate limit or access denied'
                        }
                    return {
                        'success': False,
                        'error': f'GitHub HTTP error {http_err2.code}: {http_err2.reason}'
                    }
                except Exception:
                    pass
                return {
                    'success': False,
                    'error': 'GitHub token is invalid or unauthorized'
                }
            if http_err.code == 403:
                return {
                    'success': False,
                    'error': 'GitHub API rate limit or access denied'
                }
            return {
                'success': False,
                'error': f'GitHub HTTP error {http_err.code}: {http_err.reason}'
            }
        except urllib.error.URLError as url_err:
            reason = getattr(url_err, 'reason', str(url_err))
            log(f"GitHub connection test URL error: {reason}")
            return {
                'success': False,
                'error': f'Network error: {reason}. Check your internet connection or firewall settings.'
            }
        except Exception as e:
            log(f"GitHub connection test failed: {type(e).__name__}: {e}")
            return {
                'success': False,
                'error': f'Unexpected error: {type(e).__name__}: {str(e)}'
            }
    except Exception as e:
        log(f"Error in handle_github_test_connection: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def handle_ingest_github(handler):
    """POST /api/v1/project/ingest-github - Spawn async remote repository ingestion.
    
    If no project_id is provided, auto-creates a project from the GitHub URL
    so ingestion can proceed without manually registering a project first.
    """
    try:
        import uuid
        
        content_length = int(handler.headers.get('Content-Length', 0))
        body = handler.rfile.read(content_length)
        data = json.loads(body)

        project_id = (data.get('project_id') or '').strip()
        github_token = (data.get('github_token') or '').strip()
        repository_url = (data.get('repository_url') or '').strip()
        clone_depth = int(data.get('clone_depth') or 50)

        if not github_token:
            return {'success': False, 'error': 'github_token is required'}
        if not repository_url:
            return {'success': False, 'error': 'repository_url is required'}

        project_name = ''
        # Auto-create project from GitHub URL if no project_id provided
        if not project_id:
            try:
                # Parse the GitHub URL to extract owner/repo
                sys.path.insert(0, os.path.join(DASHBOARD_DIR, '..', 'ai-core', 'services'))
                from github_ingestion_worker import normalize_github_url
                url_info = normalize_github_url(repository_url)
                repo_segment = url_info.get('repo_path_segment', 'unknown/repo')
                project_name = repo_segment.split('/')[-1] or 'github-project'
                
                # Use sandbox path as repo_path for remote-only projects
                project_id = str(uuid.uuid4())[:8]
                repo_path = f'/tmp/wikihub/sandboxes/{project_id}/repo'
                
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS wiki_projects (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        repo_path TEXT UNIQUE NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Check if project with same repo_path already exists
                cursor.execute('SELECT id FROM wiki_projects WHERE repo_path = ?', (repo_path,))
                existing = cursor.fetchone()
                if existing:
                    project_id = existing['id']
                else:
                    cursor.execute(
                        'INSERT INTO wiki_projects (id, name, repo_path) VALUES (?, ?, ?)',
                        (project_id, project_name, repo_path)
                    )
                    conn.commit()
                    log(f'Auto-created project: {project_name} ({project_id}) for GitHub ingestion')
                
                conn.close()

                # Auto-set target_model from vault if a provider is configured
                _auto_set_project_model_from_vault(project_id)
                
                # Set as active workspace
                active_workspace['project_id'] = project_id
                active_workspace['project_name'] = project_name
                active_workspace['repo_path'] = repo_path
                
            except Exception as e:
                log(f'Failed to auto-create project from GitHub URL: {e}')
                return {'success': False, 'error': f'Failed to auto-create project: {str(e)}'}
        else:
            # Verify existing project
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT id, name FROM wiki_projects WHERE id = ?', (project_id,))
            project = cursor.fetchone()
            conn.close()

            if not project:
                return {'success': False, 'error': f'Project not found: {project_id}'}
            project_name = project['name']

        job_id = f'ingest_{str(uuid.uuid4())[:8]}'
        python_bin = locate_python_bin()
        worker_script = os.path.join(DASHBOARD_DIR, '..', 'ai-core', 'services', 'github_ingestion_worker.py')
        cmd = [
            python_bin,
            worker_script,
            '--project-id', project_id,
            '--repo-url', repository_url,
            '--db', DB_PATH,
            '--depth', str(clone_depth)
        ]

        env = os.environ.copy()
        env['WIKIHUB_GITHUB_TOKEN'] = github_token

        success = spawn_background_job(job_id, cmd, project_id, env=env)
        if success:
            # Persist GitHub token to config vault
            try:
                config = load_config()
                config['github'] = config.get('github', {})
                config['github']['token'] = github_token
                config['github']['status'] = 'configured'
                save_config(config)
            except Exception as e:
                log(f'Warning: Failed to persist GitHub token to config: {e}')

            return {
                'success': True,
                'data': {
                    'job_id': job_id,
                    'project_id': project_id,
                    'project_name': project_name,
                    'message': 'GitHub ingestion job queued successfully'
                }
            }

        return {
            'success': False,
            'error': 'Failed to start GitHub ingestion job'
        }
    except Exception as e:
        log(f"Error in handle_ingest_github: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# ==================== MODEL CATALOG (OpenRouter) PAGINATION & CACHE ====================

# Simple in-memory cache for OpenRouter catalog
OPENROUTER_CACHE = {"data": [], "ts": 0}
OPENROUTER_TTL = 3600  # seconds


def fetch_openrouter_catalog_paginated(page: int = 1, limit: int = 20) -> dict:
    """Fetch catalog with server-side caching and return a paginated slice.

    Returns dict: { models: [...], has_more: bool, total: int }
    On external failure, return warmed cache slice immediately.
    """
    now = time.time()
    # Refresh cache if empty or expired
    if not OPENROUTER_CACHE['data'] or (now - OPENROUTER_CACHE['ts'] > OPENROUTER_TTL):
        try:
            url = 'https://openrouter.ai/api/v1/models'
            with __import__('urllib.request').request.urlopen(url, timeout=5.0) as resp:
                raw = resp.read()
                payload = json.loads(raw.decode('utf-8'))
                models = []
                items = payload if isinstance(payload, list) else payload.get('models', payload.get('data', payload))
                for item in items:
                    try:
                        mid = item.get('id') or item.get('model_id') or item.get('name')
                        name = item.get('name') or item.get('title') or mid
                        ctx = item.get('context_length') or item.get('context') or item.get('max_tokens') or 0
                        models.append({
                            'id': mid,
                            'name': name,
                            'context_length': ctx
                        })
                    except Exception:
                        continue

                models.sort(key=lambda m: (m.get('name') or '').lower())
                OPENROUTER_CACHE['data'] = models
                OPENROUTER_CACHE['ts'] = now
        except Exception as e:
            log(f"OpenRouter fetch error (paginated): {e}")
            # On failure, serve warmed cache if available

    total_items = len(OPENROUTER_CACHE.get('data', []))
    # sanitize page/limit
    try:
        page = max(1, int(page))
    except Exception:
        page = 1
    try:
        limit = max(1, min(200, int(limit)))
    except Exception:
        limit = 20

    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    sliced = OPENROUTER_CACHE.get('data', [])[start_idx:end_idx]

    return {
        'models': sliced,
        'has_more': end_idx < total_items,
        'total': total_items,
        'page': page,
        'limit': limit
    }


def handle_get_models(query_params=None):
    """GET /api/v1/config/models?page=1&limit=20 - return paginated catalog slice."""
    try:
        page = 1
        limit = 20
        if query_params:
            page = int(query_params.get('page', [1])[0]) if query_params.get('page') else 1
            limit = int(query_params.get('limit', [20])[0]) if query_params.get('limit') else 20

        data = fetch_openrouter_catalog_paginated(page=page, limit=limit)
        return {"success": True, "data": data}
    except Exception as e:
        log(f"Error in handle_get_models: {e}")
        return {"success": False, "error": str(e), "data": {"models": [], "has_more": False, "total": 0}}


# ==================== LIVE OPENROUTER INFERENCE & TELEMETRY ====================

def process_live_agent_inference(project_id: str, prompt_payload: str) -> dict:
    """
    Looks up the per-project target_model choice from hub.db, reads the OpenRouter API key
    from the configuration vault, routes a live authenticated call to OpenRouter, 
    and records token metrics in the telemetry ledger.
    
    Args:
        project_id: The project UUID to look up model settings for
        prompt_payload: The user's prompt text
        
    Returns:
        dict with success status and suggestion text or error message
    """
    import uuid as uuid_module
    
    # 1. Resolve project-scoped model selection from database
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT target_model FROM wiki_projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        active_model = row[0] if (row and row[0]) else "google/gemini-2.5-flash"
        
        # 2. Read OpenRouter API key from configuration vault (BYOK)
        config = load_config()
        openrouter_config = config.get('providers', {}).get('openrouter', {})
        openrouter_key = openrouter_config.get('apiKey', '')
        
        if not openrouter_key:
            return {"success": False, "message": "OpenRouter API key not configured in the configuration vault. Please add your key in the settings."}
            
        try:
            # 2. Dispatch network request to OpenRouter using urllib
            import urllib.request as ureq
            import urllib.error as uerr
            
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "Content-Type": "application/json"
            }
            
            payload_data = json.dumps({
                "model": active_model,
                "messages": [{"role": "user", "content": prompt_payload}]
            }).encode('utf-8')
            
            req = ureq.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=payload_data,
                headers=headers,
                method='POST'
            )
            
            with ureq.urlopen(req, timeout=30.0) as response:
                res_json = json.loads(response.read().decode('utf-8'))
                
            if response.status == 200:
                suggestion_text = res_json["choices"][0]["message"]["content"]
                usage = res_json.get("usage", {"prompt_tokens": 0, "completion_tokens": 0})
                
                # 3. Commit quantitative operational usage stats to SQLite telemetry logs
                in_t = usage.get("prompt_tokens", 0)
                out_t = usage.get("completion_tokens", 0)
                cost_est = (in_t * 0.000001) + (out_t * 0.000002)
                
                log_id = str(uuid_module.uuid4())[:8]
                cursor.execute("""
                    INSERT INTO token_telemetry_logs (id, project_id, model_id, input_tokens, output_tokens, estimated_cost, execution_status)
                    VALUES (?, ?, ?, ?, ?, ?, 'SUCCESS')
                """, (log_id, project_id, active_model, in_t, out_t, cost_est))
                conn.commit()
                
                return {"success": True, "suggestion": suggestion_text}
                
            return {"success": False, "message": f"Gateway error code: {response.status}"}
        except uerr.HTTPError as http_err:
            error_body = ""
            try:
                error_body = http_err.read().decode('utf-8')
            except Exception:
                pass
            return {"success": False, "message": f"HTTP error {http_err.code}: {error_body}"}
        except Exception as e:
            return {"success": False, "message": f"Inference pipeline crash: {str(e)}"}
    except Exception as e:
        return {"success": False, "message": f"Database error: {str(e)}"}
    finally:
        if conn:
            conn.close()


def handle_chat_completion(handler):
    """POST /api/v1/chat/completion - Live OpenRouter chat inference with telemetry."""
    try:
        content_length = int(handler.headers.get('Content-Length', 0))
        body = handler.rfile.read(content_length)
        data = json.loads(body)
        
        project_id = data.get('project_id', '').strip()
        prompt = data.get('prompt', '').strip()
        
        if not project_id:
            return {"success": False, "error": "project_id is required"}
        if not prompt:
            return {"success": False, "error": "prompt is required"}
        
        result = process_live_agent_inference(project_id, prompt)
        return result
    except Exception as e:
        log(f"Error in handle_chat_completion: {e}")
        return {"success": False, "error": str(e)}


def handle_get_telemetry(query_params=None):
    """GET /api/v1/telemetry - Get token usage telemetry logs."""
    project_id = _resolve_project_id(query_params)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if project_id:
            cursor.execute("""
                SELECT id, project_id, model_id, input_tokens, output_tokens, 
                       estimated_cost, execution_status, created_at
                FROM token_telemetry_logs 
                WHERE project_id = ?
                ORDER BY created_at DESC
                LIMIT 100
            """, (project_id,))
        else:
            cursor.execute("""
                SELECT id, project_id, model_id, input_tokens, output_tokens, 
                       estimated_cost, execution_status, created_at
                FROM token_telemetry_logs 
                ORDER BY created_at DESC
                LIMIT 100
            """)
        
        logs = query_to_dict(cursor)
        
        # Calculate aggregates
        total_input = sum(log.get('input_tokens', 0) for log in logs)
        total_output = sum(log.get('output_tokens', 0) for log in logs)
        total_cost = sum(log.get('estimated_cost', 0) for log in logs)
        
        conn.close()
        
        return {
            "success": True,
            "data": {
                "logs": logs,
                "aggregates": {
                    "total_input_tokens": total_input,
                    "total_output_tokens": total_output,
                    "total_estimated_cost": round(total_cost, 6)
                }
            }
        }
    except Exception as e:
        log(f"Error in /api/v1/telemetry: {e}")
        return {"success": False, "error": str(e), "data": {"logs": [], "aggregates": {}}}




# ==================== NAVIGATOR QUERY ENDPOINT ====================

def handle_navigator_query(handler):
    """POST /api/v1/navigator/query - Execute navigator agent tools via background job."""
    try:
        import uuid

        content_length = int(handler.headers.get('Content-Length', 0))
        body = handler.rfile.read(content_length)
        data = json.loads(body)

        project_id = data.get('project_id', '').strip()
        tool = data.get('tool', '').strip()
        target = data.get('target', '').strip()
        query = data.get('query', '').strip()
        direction = data.get('direction', 'forward').strip().lower()
        max_depth = int(data.get('max_depth', 3) or 3)

        if not project_id:
            return {
                "success": False,
                "error": "project_id is required"
            }

        if tool not in ['find_implementation', 'trace_lineage', 'blast_radius', 'explain_module']:
            return {
                "success": False,
                "error": "Invalid tool requested"
            }

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, repo_path, target_model FROM wiki_projects WHERE id = ?", (project_id,))
        project = cursor.fetchone()
        conn.close()

        if not project:
            return {
                "success": False,
                "error": f"Project not found: {project_id}"
            }

        active_model = project['target_model'] if project and project['target_model'] else ''

        python_bin = locate_python_bin()
        cmd = [
            python_bin,


            os.path.join(DASHBOARD_DIR, '..', 'ai-core', 'cli.py'),
            '--action', 'navigator',
            '--project-id', project_id,
            '--db', DB_PATH,
            '--tool', tool,
            '--max-depth', str(max_depth)
        ]

        if target:
            cmd += ['--target', target]
        if query:
            cmd += ['--query', query]
        if direction in ['forward', 'backward']:
            cmd += ['--direction', direction]

        job_id = f"navigator_{str(uuid.uuid4())[:8]}"
        success = spawn_background_job(job_id, cmd, project_id)

        # Store model in job registry for telemetry logging on completion
        if success and active_model:
            if job_id in job_registry:
                job_registry[job_id]['model'] = active_model

        if success:
            log(f"[Navigator] Started {tool} query for project {project_id}")
            return {
                "success": True,


                "data": {
                    "job_id": job_id,
                    "project_id": project_id,
                    "tool": tool,
                    "message": "Navigator query dispatched"
                }
            }
        else:
            return {
                "success": False,
                "error": "Failed to start navigator query"
            }
    except Exception as e:
        log(f"Error in handle_navigator_query: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# ==================== SUBPROCESS CONTROLLER ====================

def drain_stdout_stream(job_id, process):
    """Background thread to drain subprocess stdout stream."""
    try:
        for line in iter(process.stdout.readline, ''):
            if not line:
                break

            line = line.rstrip('\n')
            if line:
                log(f"[Job {job_id} STDOUT] {line}")
                if job_id in job_registry:
                    job_registry[job_id].setdefault('stdout_lines', []).append(line)
                    job_registry[job_id]['stdout_buffer'] = job_registry[job_id].get('stdout_buffer', '') + line + '\n'
    except Exception as e:
        log(f"Error draining stdout for job {job_id}: {e}")


def monitor_stderr_stream(job_id, process):
    """Background thread to monitor subprocess stderr stream"""
    try:
        for line in iter(process.stderr.readline, ''):
            if not line:
                break
            
            line = line.strip()
            if line:
                log(f"[Job {job_id}] {line}")
                
                if job_id in job_registry:
                    job_registry[job_id].setdefault('stderr_lines', []).append(line)
                    job_registry[job_id]["message"] = line
                    
                    # Parse progress if available (e.g., "[45%] Processing...")
                    if '%' in line:
                        try:
                            progress_str = line.split('%')[0].split('[')[-1]
                            job_registry[job_id]["progress"] = int(progress_str)
                        except Exception:
                            pass
    except Exception as e:
        log(f"Error monitoring stderr for job {job_id}: {e}")

def wait_for_process_completion(job_id, process):
    """Background thread to wait for process completion"""
    try:
        process.wait()
        
        if job_id in job_registry:
            if process.returncode == 0:
                job_registry[job_id]["status"] = "completed"
                job_registry[job_id]["progress"] = 100
                job_registry[job_id]["message"] = "Execution completed successfully"
                log(f"[Job {job_id}] Completed successfully")

                # Log telemetry for navigator queries on success
                if job_id.startswith('navigator_'):
                    try:
                        nav_project_id = job_registry[job_id].get('project_id', '')
                        nav_model = job_registry[job_id].get('model', 'unknown')
                        if nav_project_id:
                            import uuid as _uuid_mod
                            t_conn = get_db_connection()
                            t_cursor = t_conn.cursor()
                            stdout_buf = job_registry[job_id].get('stdout_buffer', '')
                            est_input = max(200, len(str(job_registry[job_id].get('stdout_lines', []))) // 2)
                            est_output = max(100, len(stdout_buf) // 4)
                            est_cost = (est_input * 0.000001) + (est_output * 0.000002)
                            t_cursor.execute("""
                                INSERT INTO token_telemetry_logs
                                (id, project_id, model_id, input_tokens, output_tokens, estimated_cost, execution_status)
                                VALUES (?, ?, ?, ?, ?, ?, 'SUCCESS')
                            """, (str(_uuid_mod.uuid4())[:8], nav_project_id, nav_model, est_input, est_output, est_cost))
                            t_conn.commit()
                            t_conn.close()
                            log(f"[Telemetry] Logged navigator query for project {nav_project_id}, model={nav_model}")
                    except Exception as te:
                        log(f"[Telemetry] Failed to log navigator telemetry: {te}")
            else:
                job_registry[job_id]["status"] = "failed"
                job_registry[job_id]["message"] = f"Process failed with exit code {process.returncode}"
                log(f"[Job {job_id}] Failed with exit code {process.returncode}")

                # Log failed telemetry for navigator queries
                if job_id.startswith('navigator_'):
                    try:
                        nav_project_id = job_registry[job_id].get('project_id', '')
                        nav_model = job_registry[job_id].get('model', 'unknown')
                        if nav_project_id:
                            import uuid as _uuid_mod2
                            t_conn = get_db_connection()
                            t_cursor = t_conn.cursor()
                            t_cursor.execute("""
                                INSERT INTO token_telemetry_logs
                                (id, project_id, model_id, input_tokens, output_tokens, estimated_cost, execution_status)
                                VALUES (?, ?, ?, ?, ?, ?, 'FAILED')
                            """, (str(_uuid_mod2.uuid4())[:8], nav_project_id, nav_model, 0, 0, 0.0))
                            t_conn.commit()
                            t_conn.close()
                    except Exception as te2:
                        log(f"[Telemetry] Failed to log failed navigator telemetry: {te2}")

            job_registry[job_id]["completed_at"] = datetime.now().isoformat()

            # Attempt to parse any JSON response from stdout buffer for structured results
            stdout_buffer = job_registry[job_id].get('stdout_buffer', '')
            if stdout_buffer:
                try:
                    parsed = json.loads(stdout_buffer)
                    job_registry[job_id]['result'] = parsed
                except Exception:
                    # preserve raw output if parsing fails
                    job_registry[job_id]['result'] = None
    except Exception as e:
        log(f"Error waiting for job {job_id}: {e}")
        if job_id in job_registry:
            job_registry[job_id]["status"] = "failed"
            job_registry[job_id]["message"] = str(e)

def spawn_background_job(job_id, cmd, project_id=None, env=None):
    """Spawn a non-blocking background subprocess"""
    try:
        log(f"[Job {job_id}] Spawning: {' '.join(cmd)}")
        
        # Initialize job status
        job_registry[job_id] = {
            "status": "running",
            "progress": 0,
            "message": "Initializing...",
            "active_file": "",
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "project_id": project_id,
            "stdout_lines": [],
            "stderr_lines": [],
            "stdout_buffer": "",
            "result": None
        }
        
        # Start subprocess with PIPE for stdout and stderr
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            env=env or os.environ.copy()
        )
        
        job_registry[job_id]["process"] = process
        
        # Start monitoring threads
        stdout_thread = threading.Thread(
            target=drain_stdout_stream,
            args=(job_id, process),
            daemon=True
        )
        stdout_thread.start()

        stderr_thread = threading.Thread(
            target=monitor_stderr_stream,
            args=(job_id, process),
            daemon=True
        )
        stderr_thread.start()
        
        completion_thread = threading.Thread(
            target=wait_for_process_completion,
            args=(job_id, process),
            daemon=True
        )
        completion_thread.start()
        
        log(f"[Job {job_id}] Process started with PID {process.pid}")
        
        return True
    except Exception as e:
        log(f"Error spawning job {job_id}: {e}")
        job_registry[job_id] = {
            "status": "failed",
            "progress": 0,
            "message": f"Failed to start: {str(e)}",
            "started_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat(),
            "stdout_lines": [],
            "stderr_lines": [],
            "stdout_buffer": "",
            "result": None
        }
        return False

# ==================== PROJECT SCAN ENDPOINT ====================

def handle_scan_project(handler):
    """POST /api/v1/workspace/scan - Scan active project repository"""
    try:
        import uuid
        
        # Parse request body
        content_length = int(handler.headers.get('Content-Length', 0))
        body = handler.rfile.read(content_length)
        data = json.loads(body)
        
        project_id = data.get('project_id', '')
        
        if not project_id:
            return {
                "success": False,
                "error": "project_id is required"
            }
        
        # Get project details
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, repo_path FROM wiki_projects WHERE id = ?", (project_id,))
        project = cursor.fetchone()
        conn.close()
        
        if not project:
            return {
                "success": False,
                "error": f"Project not found: {project_id}"
            }
        
        repo_path = project["repo_path"]
        
        if not os.path.exists(repo_path):
            return {
                "success": False,
                "error": f"Path does not exist: {repo_path}"
            }
        
        # Generate job ID
        job_id = f"scan_{str(uuid.uuid4())[:8]}"
        
        # Spawn background scanner process
        python_bin = locate_python_bin()
        cmd = [
            python_bin,
            os.path.join(DASHBOARD_DIR, '..', 'ai-core', 'services', 'git_extraction_engine.py'),
            "--action", "scan-all",
            "--project-id", project_id,
            "--repo-path", repo_path,
            "--db", DB_PATH,
            "--limit", "50"
        ]
        
        success = spawn_background_job(job_id, cmd, project_id)
        
        if success:
            log(f"[Scan] Started scan for project: {project['name']}")
            return {
                "success": True,
                "data": {
                    "job_id": job_id,
                    "project_id": project_id,
                    "project_name": project["name"],
                    "message": "Scan initiated in background"
                }
            }
        else:
            return {
                "success": False,
                "error": "Failed to start scan process"
            }
    except Exception as e:
        log(f"Error in handle_scan_project: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def handle_job_status():
    """GET /api/v1/workspace/job-status - Get job execution status"""
    try:
        active_jobs = {}
        for jid, job_data in job_registry.items():
            # Don't include process object in JSON response
            job_copy = {k: v for k, v in job_data.items() if k != 'process'}
            active_jobs[jid] = job_copy
        
        return {
            "success": True,
            "data": {
                "jobs": active_jobs,
                "count": len(active_jobs)
            }
        }
    except Exception as e:
        log(f"Error in handle_job_status: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": {"jobs": {}}
        }

def handle_audit_file(handler):
    """POST /api/v1/workspace/audit-file - Audit a single file"""
    try:
        import uuid
        
        # Parse request body
        content_length = int(handler.headers.get('Content-Length', 0))
        body = handler.rfile.read(content_length)
        data = json.loads(body)
        
        project_id = data.get('project_id', '')
        file_path = data.get('file_path', '')
        
        if not project_id:
            return {
                "success": False,
                "error": "project_id is required"
            }
        
        if not file_path:
            return {
                "success": False,
                "error": "file_path is required"
            }
        
        # Get project details
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, repo_path FROM wiki_projects WHERE id = ?", (project_id,))
        project = cursor.fetchone()
        conn.close()
        
        if not project:
            return {
                "success": False,
                "error": f"Project not found: {project_id}"
            }
        
        repo_path = project["repo_path"]
        
        # Generate job ID
        job_id = f"audit_{str(uuid.uuid4())[:8]}"
        
        # Spawn background audit process
        python_bin = locate_python_bin()
        cmd = [
            python_bin,
            os.path.join(DASHBOARD_DIR, '..', 'ai-core', 'services', 'git_extraction_engine.py'),
            "--action", "audit-single",
            "--project-id", project_id,
            "--repo-path", repo_path,
            "--db", DB_PATH,
            "--target-file", file_path
        ]
        
        success = spawn_background_job(job_id, cmd, project_id)
        
        if success:
            log(f"[Audit] Started audit for file: {file_path}")
            return {
                "success": True,
                "data": {
                    "job_id": job_id,
                    "project_id": project_id,
                    "file_path": file_path,
                    "message": "File audit initiated in background"
                }
            }
        else:
            return {
                "success": False,
                "error": "Failed to start audit process"
            }
    except Exception as e:
        log(f"Error in handle_audit_file: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# ==================== WORKSPACE MANAGEMENT ENDPOINTS ====================

def handle_get_projects():
    """GET /api/v1/projects - List all registered workspace projects"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wiki_projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                repo_path TEXT UNIQUE NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        
        # Fetch all projects
        cursor.execute("SELECT id, name, repo_path, created_at FROM wiki_projects ORDER BY created_at DESC")
        projects = query_to_dict(cursor)
        
        conn.close()
        
        log(f"Retrieved {len(projects)} projects")
        
        return {
            "success": True,
            "data": {
                "projects": projects,
                "count": len(projects)
            }
        }
    except Exception as e:
        log(f"Error in handle_get_projects: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": {"projects": []}
        }

def handle_delete_project(handler, project_id):
    """DELETE /api/v1/projects/{id} - Delete a project and its data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if project exists
        cursor.execute("SELECT id, name, repo_path FROM wiki_projects WHERE id = ?", (project_id,))
        project = cursor.fetchone()
        
        if not project:
            conn.close()
            return {
                "success": False,
                "error": f"Project not found: {project_id}"
            }
        
        project_name = project["name"]
        
        # Delete project-related data from all tables (ignore if table doesn't exist)
        tables_to_clean = [
            "scan_jobs",
            "git_branches",
            "git_commits",
            "git_files",
            "git_file_changes",
            "quality_files",
            "core_symbols",
            "data_lineage_edges",
            "semantic_artifacts",
            "token_telemetry_logs",
            "projects"
        ]
        
        for table in tables_to_clean:
            try:
                id_column = "id" if table == "projects" else "project_id"
                cursor.execute(f"DELETE FROM {table} WHERE {id_column} = ?", (project_id,))
            except Exception as e:
                # Table might not exist yet, skip it
                log(f"Skipping {table} cleanup (table may not exist): {e}")
        
        # Finally, delete the project itself
        cursor.execute("DELETE FROM wiki_projects WHERE id = ?", (project_id,))
        
        conn.commit()
        conn.close()
        
        # Clear active workspace if this was the active project
        if active_workspace.get("project_id") == project_id:
            active_workspace.clear()
        
        log(f"Deleted project: {project_name} ({project_id})")
        
        return {
            "success": True,
            "message": f"Project '{project_name}' deleted successfully"
        }
    except Exception as e:
        log(f"Error in handle_delete_project: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def handle_create_project(handler):
    """POST /api/v1/projects - Register a new codebase path"""
    try:
        import uuid
        
        # Parse request body
        content_length = int(handler.headers.get('Content-Length', 0))
        body = handler.rfile.read(content_length)
        data = json.loads(body)
        
        project_name = data.get('name', '').strip()
        repo_path = data.get('repo_path', '').strip()
        
        # Validation
        if not project_name:
            return {
                "success": False,
                "error": "Project name is required"
            }
        
        if not repo_path:
            return {
                "success": False,
                "error": "Repository path is required"
            }
        
        # Validate path exists
        if not os.path.exists(repo_path):
            return {
                "success": False,
                "error": f"Path does not exist: {repo_path}"
            }
        
        # Validate it's a directory
        if not os.path.isdir(repo_path):
            return {
                "success": False,
                "error": f"Path is not a directory: {repo_path}"
            }
        
        # Validate .git directory exists
        git_dir = os.path.join(repo_path, '.git')
        if not os.path.exists(git_dir):
            return {
                "success": False,
                "error": f"Not a git repository (no .git directory): {repo_path}"
            }
        
        # Generate project ID
        project_id = str(uuid.uuid4())[:8]
        
        # Save to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wiki_projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                repo_path TEXT UNIQUE NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            INSERT INTO wiki_projects (id, name, repo_path)
            VALUES (?, ?, ?)
        """, (project_id, project_name, repo_path))
        
        conn.commit()
        conn.close()

        # Auto-set target_model from vault if a provider is configured
        _auto_set_project_model_from_vault(project_id)
        
        log(f"Created project: {project_name} ({project_id}) at {repo_path}")
        
        return {
            "success": True,
            "data": {
                "id": project_id,
                "name": project_name,
                "repo_path": repo_path
            }
        }
    except sqlite3.IntegrityError:
        return {
            "success": False,
            "error": "Repository path already registered"
        }
    except Exception as e:
        log(f"Error in handle_create_project: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def handle_get_active_workspace():
    """GET /api/v1/workspace/active - Get currently selected workspace"""
    try:
        # Return in consistent format with id, name, repo_path
        if active_workspace.get("project_id"):
            return {
                "success": True,
                "data": {
                    "id": active_workspace["project_id"],
                    "name": active_workspace["project_name"],
                    "repo_path": active_workspace["repo_path"]
                }
            }
        else:
            return {
                "success": True,
                "data": {}
            }
    except Exception as e:
        log(f"Error in handle_get_active_workspace: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": {}
        }

def handle_select_workspace(handler):
    """POST /api/v1/workspace/select - Set active workspace context"""
    try:
        # Parse request body
        content_length = int(handler.headers.get('Content-Length', 0))
        body = handler.rfile.read(content_length)
        data = json.loads(body)
        
        project_id = data.get('project_id')
        
        if not project_id:
            return {
                "success": False,
                "error": "project_id is required"
            }
        
        # Fetch project details
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, name, repo_path FROM wiki_projects WHERE id = ?", (project_id,))
        project = cursor.fetchone()
        
        conn.close()
        
        if not project:
            return {
                "success": False,
                "error": f"Project not found: {project_id}"
            }
        
        # Update global workspace context
        active_workspace["project_id"] = project["id"]
        active_workspace["project_name"] = project["name"]
        active_workspace["repo_path"] = project["repo_path"]
        
        log(f"Workspace switched to: {project['name']} ({project_id})")
        
        return {
            "success": True,
            "data": {
                "id": project["id"],
                "name": project["name"],
                "repo_path": project["repo_path"]
            }
        }
    except Exception as e:
        log(f"Error in handle_select_workspace: {e}")
        return {
            "success": False,
            "error": str(e),
            "data": {}
        }

# ==================== GIT ANALYTICS ENDPOINTS ====================

def get_repo_path():
    """Get the repository path from active workspace or default"""
    if active_workspace.get("repo_path"):
        return active_workspace["repo_path"]
    return None

def run_git_command(args, repo_path=None):
    """Run git command and return stdout. All logs to stderr."""
    if repo_path is None:
        repo_path = get_repo_path()

    if not repo_path:
        print("[Git] No active project selected; refusing projectless git command", file=sys.stderr)
        return None
    
    try:
        result = subprocess.run(
            ['git'] + args,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"[Git] Command failed: {' '.join(args)}", file=sys.stderr)
            print(f"[Git] stderr: {result.stderr}", file=sys.stderr)
            return None
        
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"[Git] Command timed out: {' '.join(args)}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[Git] Error: {e}", file=sys.stderr)
        return None

def handle_git_branches():
    """GET /api/v1/git/branches - List all branches"""
    try:
        # Get all local branches
        branches_output = run_git_command(['branch', '--format=%(refname:short)'])
        
        if branches_output is None:
            return {
                "success": False,
                "error": "Failed to retrieve branches",
                "data": {"branches": [], "active": ""}
            }
        
        branches = [b.strip() for b in branches_output.split('\n') if b.strip()]
        
        # Get active branch
        active_output = run_git_command(['branch', '--show-current'])
        active_branch = active_output if active_output else "main"
        
        print(f"[Git] Found {len(branches)} branches, active: {active_branch}", file=sys.stderr)
        
        return {
            "success": True,
            "data": {
                "branches": branches,
                "active": active_branch
            }
        }
    except Exception as e:
        print(f"[Git] Error in handle_git_branches: {e}", file=sys.stderr)
        return {
            "success": False,
            "error": str(e),
            "data": {"branches": [], "active": ""}
        }

def handle_git_commits(branch="main", limit=50):
    """GET /api/v1/git/commits - Get commit history for a branch"""
    try:
        # Format: hash|author|date|message
        log_output = run_git_command([
            'log', 
            '--format=%H|%an|%ai|%s',
            f'-{limit}',
            branch
        ])
        
        if log_output is None:
            return {
                "success": False,
                "error": f"Failed to retrieve commits for branch: {branch}",
                "data": {"commits": []}
            }
        
        commits = []
        for line in log_output.split('\n'):
            if not line.strip():
                continue
            
            parts = line.split('|', 3)
            if len(parts) == 4:
                commits.append({
                    "hash": parts[0],
                    "short_hash": parts[0][:7],
                    "author": parts[1],
                    "date": parts[2],
                    "message": parts[3]
                })
        
        print(f"[Git] Retrieved {len(commits)} commits from {branch}", file=sys.stderr)
        
        return {
            "success": True,
            "data": {
                "branch": branch,
                "commits": commits,
                "count": len(commits)
            }
        }
    except Exception as e:
        print(f"[Git] Error in handle_git_commits: {e}", file=sys.stderr)
        return {
            "success": False,
            "error": str(e),
            "data": {"commits": []}
        }

def handle_git_diff(commit_hash):
    """GET /api/v1/git/diff - Get abstract diff metrics (NO source code)"""
    try:
        # Get file status (added, modified, deleted)
        # Use --root to handle shallow clones where the initial commit has no parent
        status_output = run_git_command([
            'diff-tree', '-r', '--no-commit-id', '--name-status',
            '--root', commit_hash
        ])
        
        if status_output is None:
            return {
                "success": False,
                "error": f"Failed to retrieve diff for commit: {commit_hash}",
                "data": {}
            }
        
        # Get numstat (lines added/removed per file)
        # Use diff-tree with --root to handle shallow clones where commit^ may not exist
        # --no-commit-id prevents the commit hash from appearing as the first output line
        numstat_output = run_git_command([
            'diff-tree', '--numstat', '-r',
            '--no-commit-id', '--root', commit_hash
        ])
        
        # Parse file changes
        files_changed = []
        total_added = 0
        total_removed = 0
        
        if status_output:
            for line in status_output.split('\n'):
                if not line.strip():
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 2:
                    status = parts[0]
                    file_path = parts[1]
                    
                    file_info = {
                        "path": file_path,
                        "status": status,  # A=added, M=modified, D=deleted
                        "added": 0,
                        "removed": 0
                    }
                    
                    files_changed.append(file_info)
        
        # Parse numstat for line counts
        if numstat_output:
            numstat_lines = numstat_output.split('\n')
            for i, line in enumerate(numstat_lines):
                if not line.strip() or i >= len(files_changed):
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 3:
                    try:
                        added = int(parts[0]) if parts[0] != '-' else 0
                        removed = int(parts[1]) if parts[1] != '-' else 0
                        
                        if i < len(files_changed):
                            files_changed[i]["added"] = added
                            files_changed[i]["removed"] = removed
                            
                            total_added += added
                            total_removed += removed
                    except ValueError:
                        pass
        
        # Calculate complexity delta (simplified heuristic)
        # More lines added than removed = potential complexity increase
        delta_lines = total_added - total_removed
        complexity_delta = delta_lines / 100.0 if delta_lines > 0 else 0
        
        print(f"[Git] Commit {commit_hash[:7]}: {len(files_changed)} files, +{total_added}/-{total_removed} lines", file=sys.stderr)
        
        return {
            "success": True,
            "data": {
                "commit": commit_hash,
                "short_hash": commit_hash[:7],
                "files_changed": len(files_changed),
                "total_added": total_added,
                "total_removed": total_removed,
                "delta_lines": delta_lines,
                "complexity_delta": round(complexity_delta, 2),
                "files": files_changed
            }
        }
    except Exception as e:
        print(f"[Git] Error in handle_git_diff: {e}", file=sys.stderr)
        return {
            "success": False,
            "error": str(e),
            "data": {}
        }

# ==================== HTTP REQUEST HANDLER ====================

class WikiHubHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler with API routing and static file serving"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)
    
    def do_GET(self):
        """Handle GET requests - route API calls or serve static files"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        params = parse_qs(parsed_path.query)
        
        # API Route Multiplexing
        if path == '/api/v1/stats':
            self._send_json_response(handle_stats(params))
        elif path == '/api/v1/quality':
            self._send_json_response(handle_quality(params))
        elif path == '/api/v1/topology':
            self._send_json_response(handle_topology(params))
        elif path == '/api/v1/config':
            self._send_json_response(handle_get_config())
        elif path == '/api/v1/config/models':
            self._send_json_response(handle_get_models(params))
        elif path == '/api/v1/project/settings':
            self._send_json_response(handle_get_project_settings(params))
        elif path == '/api/v1/lineage/trace':
            self._send_json_response(handle_lineage_trace(params))
        elif path == '/api/v1/topology/blast-radius':
            self._send_json_response(handle_blast_radius(params))
        elif path == '/api/v1/projects':
            self._send_json_response(handle_get_projects())
        elif path == '/api/v1/workspace/active':
            self._send_json_response(handle_get_active_workspace())
        elif path.startswith('/api/v1/workspace/job-status'):
            self._send_json_response(handle_job_status())
        elif path == '/api/v1/git/branches':
            self._send_json_response(handle_git_branches())
        elif path.startswith('/api/v1/git/commits'):
            branch = params.get('branch', ['main'])[0]
            limit = int(params.get('limit', ['50'])[0])
            self._send_json_response(handle_git_commits(branch, limit))
        elif path.startswith('/api/v1/git/diff'):
            commit = params.get('commit', [''])[0]
            if not commit:
                self._send_json_response({
                    "success": False,
                    "error": "Missing commit parameter",
                    "data": {}
                })
            else:
                self._send_json_response(handle_git_diff(commit))
        elif path == '/api/v1/telemetry':
            self._send_json_response(handle_get_telemetry(params))
        else:
            # API-only mode — no static file serving
            self._send_json_response({
                "success": False,
                "error": "Endpoint not found"
            }, status_code=404)
    
    def do_POST(self):
        """Handle POST requests for API endpoints"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == '/api/v1/projects':
            self._send_json_response(handle_create_project(self))
        elif path == '/api/v1/workspace/select':
            self._send_json_response(handle_select_workspace(self))
        elif path == '/api/v1/project/settings':
            self._send_json_response(handle_post_project_settings(self))
        elif path == '/api/v1/workspace/scan':
            self._send_json_response(handle_scan_project(self))
        elif path == '/api/v1/workspace/audit-file':
            self._send_json_response(handle_audit_file(self))
        elif path == '/api/v1/navigator/query':
            self._send_json_response(handle_navigator_query(self))
        elif path == '/api/v1/github/test-connection':
            self._send_json_response(handle_github_test_connection(self))
        elif path == '/api/v1/project/ingest-github':
            self._send_json_response(handle_ingest_github(self))
        elif path == '/api/v1/config':
            self._send_json_response(handle_save_config(self))
        elif path == '/api/v1/config/test-connection':
            self._send_json_response(handle_test_provider_connection(self))
        elif path == '/api/v1/topology/file-importance':
            self._send_json_response(handle_file_importance(self))
        elif path == '/api/v1/chat/completion':
            self._send_json_response(handle_chat_completion(self))
        else:
            log(f"POST request to {path}")
            self._send_json_response({
                "success": False,
                "error": "Endpoint not found"
            }, status_code=404)
    
    def do_DELETE(self):
        """Handle DELETE requests for API endpoints"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # Handle /api/v1/projects/{id}
        if path.startswith('/api/v1/projects/'):
            # Extract project ID from path
            project_id = path.replace('/api/v1/projects/', '')
            if project_id:
                self._send_json_response(handle_delete_project(self, project_id))
            else:
                self._send_json_response({
                    "success": False,
                    "error": "Project ID is required"
                }, status_code=400)
        else:
            log(f"DELETE request to {path}")
            self._send_json_response({
                "success": False,
                "error": "Endpoint not found"
            }, status_code=404)
    
    def _send_json_response(self, data, status_code=200):
        """Send JSON response with proper headers"""
        try:
            response_body = json.dumps(data, indent=2)
            self.send_response(status_code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response_body.encode('utf-8')))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(response_body.encode('utf-8'))
            
            log(f"Response {status_code} sent for {self.path}")
        except Exception as e:
            log(f"ERROR sending response: {e}")
    
    def log_message(self, format, *args):
        """Stream purity: Override to log to stderr instead of stdout"""
        log(f"{self.client_address[0]} - {format % args}")

# ==================== SERVER STARTUP ====================

if __name__ == "__main__":
    log(f"Starting WikiHub Dashboard Server on port {PORT}")
    log(f"API server running on port {PORT} (static files served separately by static-server)")
    log(f"Database path: {DB_PATH}")
    log("API Endpoints:")
    log("  GET /api/v1/stats    - Aggregate metrics")
    log("  GET /api/v1/quality  - File quality analysis")
    log("  GET /api/v1/topology - Dependency graph")
    log("")
    
    # Ensure DB schema and migration run
    ensure_project_schema()
    ensure_telemetry_schema()
    
    log("Server ready. Press Ctrl+C to stop.")
    log("")
    
    # Start server with address reuse enabled
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), WikiHubHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            log("\nServer stopped by user")
            httpd.shutdown()

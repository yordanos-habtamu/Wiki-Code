"""
ArchivistAgent - File generation engine for structured markdown context artifacts.
Compiles CODEBASE.md and onboarding_brief.md into a project-scoped cartography archive.
"""

import os
import sys
import sqlite3
import json
import traceback
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


class ArchivistAgent:
    """Persistent markdown artifact generator for codebase context."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        project_id: Optional[str] = None,
        archive_root: Optional[str] = None
    ):
        self.project_id = project_id or 'global'
        self.db_path = db_path or os.path.join(project_root, 'apps', 'cli', 'hub.db')
        self.archive_root = archive_root or os.path.join(project_root, 'apps', 'ai-core', '.cartography', self.project_id)
        os.makedirs(self.archive_root, exist_ok=True)

        print(f"ArchivistAgent initialized for project {self.project_id}", file=sys.stderr)
        print(f"Archive path: {self.archive_root}", file=sys.stderr)
        print(f"Database file: {self.db_path}", file=sys.stderr)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _fetch_semantic_artifacts(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.db_path):
            return []
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT file_path, purpose_summary, docstring_summary, has_doc_drift, drift_notes "
                "FROM semantic_artifacts WHERE project_id = ? ORDER BY file_path",
                (self.project_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as exc:
            print(f"[ArchivistAgent] Error loading semantic artifacts: {exc}", file=sys.stderr)
            return []
        finally:
            conn.close()

    def _fetch_lineage_edges(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.db_path):
            return []
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT source_dataset, target_dataset, transformation_type, source_file, line_range "
                "FROM data_lineage_edges WHERE project_id = ? ORDER BY created_at",
                (self.project_id,)
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as exc:
            print(f"[ArchivistAgent] Error loading lineage edges: {exc}", file=sys.stderr)
            return []
        finally:
            conn.close()

    def _fetch_drift_warnings(self) -> List[Dict[str, Any]]:
        artifacts = self._fetch_semantic_artifacts()
        return [a for a in artifacts if a.get('has_doc_drift')]

    def _calculate_critical_path(self, artifacts: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        scores = {}
        for artifact in artifacts:
            path = artifact.get('file_path')
            score = 1.0
            if artifact.get('purpose_summary'):
                score += 2.0
            if artifact.get('has_doc_drift'):
                score -= 0.5
            scores[path] = score

        for edge in edges:
            source = edge.get('source_file')
            target = edge.get('target_dataset')
            scores[source] = scores.get(source, 1.0) + 0.6
            if target in scores:
                scores[target] += 0.3

        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        return [{'file_path': fp, 'impact_score': round(score, 2)} for fp, score in ordered[:10]]

    def _calculate_lineage_sources_and_sinks(self, edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        sources = set()
        sinks = set()
        for edge in edges:
            sources.add(edge.get('source_dataset'))
            sinks.add(edge.get('target_dataset'))

        pure_sinks = [sink for sink in sinks if sink not in sources]
        pure_sources = [source for source in sources if source not in sinks]

        return {
            'sources': sorted(pure_sources)[:10],
            'sinks': sorted(pure_sinks)[:10]
        }

    def _detect_circular_imports(self) -> List[str]:
        if not os.path.exists(self.db_path):
            return []
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT source_file, import_path FROM dependencies")
            edges = [dict(row) for row in cursor.fetchall()]
            graph = {}
            for item in edges:
                source = item.get('source_file')
                target = item.get('import_path')
                graph.setdefault(source, set()).add(target)

            cycles = []
            visited = set()
            path = []

            def dfs(node):
                if node in path:
                    cycle = ' -> '.join(path[path.index(node):] + [node])
                    cycles.append(cycle)
                    return
                if node in visited:
                    return
                visited.add(node)
                path.append(node)
                for neighbor in graph.get(node, []):
                    dfs(neighbor)
                path.pop()

            for node in graph:
                dfs(node)

            return sorted(set(cycles))[:5]
        except Exception as exc:
            print(f"[ArchivistAgent] Error detecting circular imports: {exc}", file=sys.stderr)
            return []
        finally:
            conn.close()

    def _save_markdown(self, path: str, body: str) -> None:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(body)
            print(f"[ArchivistAgent] Wrote artifact: {path}", file=sys.stderr)
        except Exception as exc:
            print(f"[ArchivistAgent] Failed to write {path}: {exc}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

    def _write_archive_index(self, entries: List[Dict[str, Any]]) -> None:
        manifest_path = os.path.join(self.archive_root, 'archive_index.json')
        try:
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump({'project_id': self.project_id, 'entries': entries}, f, indent=2)
            print(f"[ArchivistAgent] Wrote vector index manifest: {manifest_path}", file=sys.stderr)
        except Exception as exc:
            print(f"[ArchivistAgent] Failed to write archive index: {exc}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

    def _build_codebase_md(self, artifacts: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> str:
        critical_path = self._calculate_critical_path(artifacts, edges)
        lineage = self._calculate_lineage_sources_and_sinks(edges)
        drift_warnings = self._fetch_drift_warnings()
        circular_imports = self._detect_circular_imports()

        lines = [
            '# CODEBASE.md',
            '',
            '## Architecture Overview',
            '',
            f"This archive captures semantic composition, lineage topology, and documentation drift for project `{self.project_id}`.",
            '',
            'The system is represented as a mix of public symbols, lineage transformations, and dependency boundaries derived from the shared SQLite metadata layer.',
            '',
            '## Critical Path',
            ''
        ]

        if critical_path:
            lines.append('| File Path | Impact Score |')
            lines.append('| --- | ---: |')
            for row in critical_path:
                lines.append(f"| {row['file_path']} | {row['impact_score']} |")
        else:
            lines.append('No critical path candidates were available from semantic metadata.')

        lines.extend([
            '',
            '## Data Lineage Flow',
            ''
        ])

        if lineage['sources'] or lineage['sinks']:
            lines.append('**Source datasets:** ' + (', '.join(lineage['sources']) or 'None'))
            lines.append('')
            lines.append('**Sink datasets:** ' + (', '.join(lineage['sinks']) or 'None'))
            lines.append('')
            lines.append('Detailed lineage edges:')
            lines.append('')
            lines.append('| Source Dataset | Target Dataset | Transformation | Source File | Line Range |')
            lines.append('| --- | --- | --- | --- | --- |')
            for edge in edges[:20]:
                lines.append(
                    f"| {edge['source_dataset']} | {edge['target_dataset']} | {edge['transformation_type']} | {edge['source_file']} | {edge.get('line_range', 'n/a')} |"
                )
        else:
            lines.append('No lineage edge documentation was available for this project.')

        lines.extend([
            '',
            '## Known Debt',
            ''
        ])

        if drift_warnings:
            lines.append('### Documentation Drift')
            lines.append('')
            for warning in drift_warnings:
                lines.append(f"- `{warning['file_path']}` — {warning['drift_notes']}")
            lines.append('')
        else:
            lines.append('No documentation drift warnings were detected.')
            lines.append('')

        if circular_imports:
            lines.append('### Circular Imports')
            lines.append('')
            for cycle in circular_imports:
                lines.append(f"- {cycle}")
            lines.append('')
        else:
            lines.append('No circular import cycles were identified.')
            lines.append('')

        return '\n'.join(lines)

    def _build_onboarding_brief(self, artifacts: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> str:
        sources = self._calculate_lineage_sources_and_sinks(edges)['sources']
        sinks = self._calculate_lineage_sources_and_sinks(edges)['sinks']
        critical_path = self._calculate_critical_path(artifacts, edges)
        drift_warnings = self._fetch_drift_warnings()

        lines = [
            '# onboarding_brief.md',
            '',
            '## 1. Ingestion Pathways',
            '',
            'Data enters the system through semantic extraction, file symbol analysis, and SQL lineage parsing. ',
            'Primary ingestion sources are the `core_symbols` table and the `data_lineage_edges` ledger, which are populated during repository scan passes.',
            '',
            'Key files include:',
        ]

        for artifact in artifacts[:5]:
            lines.append(f"- `{artifact['file_path']}` — Purpose: {artifact['purpose_summary'][:120]}" )
        lines.extend([
            '',
            '## 2. Critical Endpoints',
            '',
        ])

        if critical_path:
            for item in critical_path[:5]:
                lines.append(f"- `{item['file_path']}` — impact score {item['impact_score']}")
        else:
            lines.append('- No critical endpoints were inferred from current metadata. Please run the semantic scanner.')

        lines.extend([
            '',
            '## 3. Blast-Radius Vectors',
            '',
            'The system calculates blast radius by tracing dependency and lineage relationships. High impact files are those with dense outgoing lineage edges or multiple consumer dependencies.',
        ])

        lines.extend([
            '',
            '## 4. Business Logic Nodes',
            '',
        ])

        for artifact in artifacts[:5]:
            lines.append(f"- `{artifact['file_path']}` — Summary: {artifact['purpose_summary']}")

        lines.extend([
            '',
            '## 5. 90-Day Change Velocity',
            '',
            'This brief currently uses structural metadata age and drift alerts as a proxy for change velocity. Files with documentation drift and repeated lineage updates should be prioritized for review.',
        ])

        if drift_warnings:
            lines.append('')
            lines.append('### Notable change velocity signals:')
            for warning in drift_warnings[:5]:
                lines.append(f"- `{warning['file_path']}` — {warning['drift_notes']}" )
        else:
            lines.append('No immediate documentation drift signals were found.')

        lines.extend([
            '',
            '### Provenance Citations',
            '',
        ])

        for artifact in artifacts[:3]:
            lines.append(
                f"- `{artifact['file_path']}` (doc summary lines) — lines referenced from core symbol and semantic artifact analysis."
            )

        return '\n'.join(lines)

    def run(self) -> Dict[str, Any]:
        print('[ArchivistAgent] Starting archive generation', file=sys.stderr)
        artifacts = self._fetch_semantic_artifacts()
        edges = self._fetch_lineage_edges()

        codebase_md = self._build_codebase_md(artifacts, edges)
        onboarding_md = self._build_onboarding_brief(artifacts, edges)

        codebase_path = os.path.join(self.archive_root, 'CODEBASE.md')
        onboarding_path = os.path.join(self.archive_root, 'onboarding_brief.md')

        self._save_markdown(codebase_path, codebase_md)
        self._save_markdown(onboarding_path, onboarding_md)

        index_entries = [
            {
                'file_path': artifact['file_path'],
                'purpose_summary': artifact['purpose_summary'],
                'line_reference': artifact.get('docstring_summary', '')[:120]
            }
            for artifact in artifacts
        ]
        self._write_archive_index(index_entries)

        return {
            'project_id': self.project_id,
            'archive_root': self.archive_root,
            'files_indexed': len(artifacts),
            'lineage_edges': len(edges)
        }

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return self.run()

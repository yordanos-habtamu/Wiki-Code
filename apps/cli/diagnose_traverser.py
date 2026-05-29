#!/usr/bin/env python3
"""
Diagnostic script to check why Code Traverser might not be showing files.
"""

import sqlite3
import json
import sys
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'hub.db')

def check_projects():
    """List all projects in the database."""
    print("\n" + "=" * 70)
    print("PROJECTS IN DATABASE")
    print("=" * 70)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, repo_path, target_model FROM wiki_projects")
    projects = cursor.fetchall()
    
    if not projects:
        print("❌ No projects found in database!")
        conn.close()
        return None
    
    for proj in projects:
        print(f"\nProject ID: {proj['id']}")
        print(f"  Name: {proj['name']}")
        print(f"  Path: {proj['repo_path']}")
        print(f"  Model: {proj['target_model']}")
    
    conn.close()
    return projects[0]['id'] if projects else None


def check_quality_files(project_id):
    """Check quality_files table for a project."""
    print("\n" + "=" * 70)
    print(f"QUALITY FILES FOR PROJECT: {project_id}")
    print("=" * 70)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT file_path, language, quality_score, symbol_count, dependency_count
        FROM quality_files
        WHERE project_id = ?
        ORDER BY file_path
    """, (project_id,))
    
    files = cursor.fetchall()
    
    if not files:
        print(f"❌ No files found for project {project_id}")
        print("\nPossible reasons:")
        print("  1. Project hasn't been scanned yet")
        print("  2. Ingestion failed")
        print("  3. Wrong project ID")
        print("\nSolution:")
        print(f"  python3 apps/ai-core/cli.py --action archivist --project-id {project_id}")
        conn.close()
        return False
    
    print(f"✅ Found {len(files)} files:\n")
    for f in files:
        print(f"  {f['file_path']}")
        print(f"    Language: {f['language']}")
        print(f"    Quality: {f['quality_score']}")
        print(f"    Symbols: {f['symbol_count']}")
        print(f"    Dependencies: {f['dependency_count']}")
        print()
    
    conn.close()
    return True


def check_git_changes(project_id):
    """Check git_file_changes for link data."""
    print("\n" + "=" * 70)
    print(f"GIT FILE CHANGES FOR PROJECT: {project_id}")
    print("=" * 70)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM git_file_changes
        WHERE project_id = ?
    """, (project_id,))
    
    count = cursor.fetchone()['count']
    
    if count == 0:
        print("⚠️  No git file changes found")
        print("   This means the graph will have nodes but no links")
        print("   Links are created from commit co-occurrence")
    else:
        print(f"✅ Found {count} git file changes")
        
        cursor.execute("""
            SELECT commit_hash, COUNT(*) as file_count
            FROM git_file_changes
            WHERE project_id = ?
            GROUP BY commit_hash
            LIMIT 5
        """, (project_id,))
        
        commits = cursor.fetchall()
        print(f"\nSample commits:")
        for c in commits:
            print(f"  {c['commit_hash'][:8]}: {c['file_count']} files")
    
    conn.close()


def test_topology_api(project_id):
    """Simulate the topology API call."""
    print("\n" + "=" * 70)
    print(f"SIMULATING TOPOLOGY API CALL")
    print("=" * 70)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Same query as serve.py
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
    
    files = cursor.fetchall()
    
    if not files:
        print("❌ API would return empty nodes array")
        conn.close()
        return
    
    print(f"✅ API would return {len(files)} nodes")
    
    # Create nodes (simplified)
    nodes = []
    for idx, file in enumerate(files):
        node = {
            "id": file['id'],
            "lang": file['lang'],
            "score": round(float(file['quality_score'] or 0.0), 1),
            "weight": 12 + min(8, int((file['complexity'] or 0) * 0.5))
        }
        nodes.append(node)
    
    print(f"\nSample nodes:")
    for node in nodes[:3]:
        print(f"  {node['id']}")
        print(f"    Language: {node['lang']}")
        print(f"    Score: {node['score']}")
        print(f"    Weight: {node['weight']}")
    
    # Check for links
    cursor.execute("""
        SELECT COUNT(DISTINCT commit_hash) as commit_count
        FROM git_file_changes
        WHERE project_id = ?
    """, (project_id,))
    
    commit_count = cursor.fetchone()['commit_count']
    
    if commit_count == 0:
        print(f"\n⚠️  No commits found - graph will have no links")
    else:
        print(f"\n✅ {commit_count} commits available for link generation")
    
    conn.close()


def check_dependencies():
    """Check dependencies table."""
    print("\n" + "=" * 70)
    print("DEPENDENCIES TABLE")
    print("=" * 70)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM dependencies")
    count = cursor.fetchone()['count']
    
    if count == 0:
        print("⚠️  No dependencies found")
        print("   Navigator blast_radius tool will return empty results")
    else:
        print(f"✅ Found {count} dependencies")
        
        cursor.execute("SELECT source_file, import_path FROM dependencies LIMIT 5")
        deps = cursor.fetchall()
        print("\nSample dependencies:")
        for d in deps:
            print(f"  {d['source_file']} → {d['import_path']}")
    
    conn.close()


def main():
    print("\n🔍 WikiHub Code Traverser Diagnostic Tool")
    print("=" * 70)
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at: {DB_PATH}")
        sys.exit(1)
    
    print(f"✅ Database found: {DB_PATH}")
    
    # Check projects
    project_id = check_projects()
    
    if not project_id:
        print("\n❌ No projects to diagnose")
        sys.exit(1)
    
    # Allow user to specify project ID
    if len(sys.argv) > 1:
        project_id = sys.argv[1]
        print(f"\n📌 Using specified project ID: {project_id}")
    
    # Run diagnostics
    has_files = check_quality_files(project_id)
    
    if has_files:
        check_git_changes(project_id)
        test_topology_api(project_id)
        check_dependencies()
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    if has_files:
        print("✅ Code Traverser should work!")
        print("\nIf files still don't show in dashboard:")
        print("  1. Refresh the browser (Ctrl+R)")
        print("  2. Check browser console for errors (F12)")
        print("  3. Verify project is selected in dashboard")
        print("  4. Click 'Rescan Project' button")
    else:
        print("❌ Code Traverser won't work - no files in database")
        print("\nTo fix:")
        print(f"  python3 apps/ai-core/cli.py --action archivist --project-id {project_id}")
    
    print("\n" + "=" * 70)


if __name__ == '__main__':
    main()

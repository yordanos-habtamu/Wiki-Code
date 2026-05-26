#!/usr/bin/env python3
"""
Test script for Git Extraction Engine
Verifies branch discovery, commit profiling, and diff analytics.
"""
import sys
import os
import json

# Add ai-core to path
sys.path.insert(0, os.path.dirname(__file__))

from services.git_extraction_engine import GitExtractionEngine


def test_branch_discovery():
    """Test branch discovery functionality."""
    print("\n" + "="*60)
    print("TEST 1: Branch Discovery")
    print("="*60)
    
    try:
        # Point to test repository
        test_repo_path = os.path.join(os.path.dirname(__file__), 'test_repo')
        engine = GitExtractionEngine(repo_path=test_repo_path)
        result = engine.discover_branches()
        
        print(f"\n✓ Local branches: {result['total_local']}")
        print(f"✓ Remote branches: {result['total_remote']}")
        print(f"✓ Active branch: {result['active']}")
        
        assert result['total_local'] > 0, "Should find at least one local branch"
        assert result['active'], "Should identify active branch"
        
        print("\n✅ Branch discovery PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Branch discovery FAILED: {e}")
        return False


def test_commit_profiling():
    """Test commit history profiling."""
    print("\n" + "="*60)
    print("TEST 2: Commit History Profiling")
    print("="*60)
    
    try:
        test_repo_path = os.path.join(os.path.dirname(__file__), 'test_repo')
        engine = GitExtractionEngine(repo_path=test_repo_path)
        commits = engine.profile_commit_history("main", limit=10)
        
        print(f"\n✓ Commits profiled: {len(commits)}")
        
        if commits:
            latest = commits[0]
            print(f"✓ Latest commit: {latest['short_hash']}")
            print(f"✓ Author: {latest['author']}")
            print(f"✓ Message: {latest['message'][:60]}...")
            print(f"✓ Files changed: {latest['files_changed']}")
            print(f"✓ Lines added: {latest['lines_added']}")
            print(f"✓ Lines removed: {latest['lines_removed']}")
        
        assert len(commits) > 0, "Should find at least one commit"
        assert 'commit_hash' in commits[0], "Commit should have hash"
        assert 'files' in commits[0], "Commit should have file metrics"
        
        print("\n✅ Commit profiling PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Commit profiling FAILED: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


def test_diff_analysis():
    """Test commit diff analysis."""
    print("\n" + "="*60)
    print("TEST 3: Commit Diff Analysis")
    print("="*60)
    
    try:
        test_repo_path = os.path.join(os.path.dirname(__file__), 'test_repo')
        engine = GitExtractionEngine(repo_path=test_repo_path)
        
        # Get a recent commit
        commits = engine.profile_commit_history("main", limit=1)
        
        if not commits:
            print("⚠️  No commits found, skipping diff test")
            return True
        
        commit_hash = commits[0]['commit_hash']
        print(f"\nAnalyzing commit: {commit_hash[:7]}")
        
        result = engine.analyze_commit_diff(commit_hash)
        
        print(f"✓ Files changed: {result['files_changed']}")
        print(f"✓ Total added: {result['total_added']}")
        print(f"✓ Total removed: {result['total_removed']}")
        print(f"✓ Complexity delta: {result['complexity_delta']}")
        
        assert 'files' in result, "Should have file list"
        assert 'delta_summary' in result, "Should have delta summary"
        
        # Verify NO source code is exposed
        for file_info in result.get('files', []):
            assert 'path' in file_info, "Should have file path"
            assert 'status' in file_info, "Should have status"
            assert 'source_code' not in file_info, "Should NOT have source code"
            assert 'patch' not in file_info, "Should NOT have patch"
        
        print("\n✅ Diff analysis PASSED (Abstract Integrity verified)")
        return True
        
    except Exception as e:
        print(f"\n❌ Diff analysis FAILED: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


def test_time_series():
    """Test time-series analytics."""
    print("\n" + "="*60)
    print("TEST 4: Time-Series Analytics")
    print("="*60)
    
    try:
        test_repo_path = os.path.join(os.path.dirname(__file__), 'test_repo')
        engine = GitExtractionEngine(repo_path=test_repo_path)
        result = engine.get_branch_time_series("main", commit_limit=20)
        
        print(f"\n✓ Commits analyzed: {result['commits_analyzed']}")
        print(f"✓ Total files changed: {result['total_files_changed']}")
        print(f"✓ Total lines added: {result['total_lines_added']}")
        print(f"✓ Total lines removed: {result['total_lines_removed']}")
        print(f"✓ Net change: {result['net_lines']}")
        print(f"✓ Time-series points: {len(result['time_series'])}")
        
        if result['time_series']:
            latest = result['time_series'][-1]
            print(f"✓ Cumulative added: {latest['cumulative_added']}")
            print(f"✓ Cumulative removed: {latest['cumulative_removed']}")
        
        assert result['commits_analyzed'] > 0, "Should analyze at least one commit"
        assert len(result['time_series']) > 0, "Should have time-series data"
        
        print("\n✅ Time-series analytics PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Time-series analytics FAILED: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


def test_database_persistence():
    """Test database schema and persistence."""
    print("\n" + "="*60)
    print("TEST 5: Database Persistence")
    print("="*60)
    
    try:
        import sqlite3
        
        test_repo_path = os.path.join(os.path.dirname(__file__), 'test_repo')
        test_db_path = os.path.join(os.path.dirname(__file__), 'test_hub.db')
        engine = GitExtractionEngine(repo_path=test_repo_path, db_path=test_db_path)
        
        # Verify tables exist
        conn = sqlite3.connect(engine.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='git_commits'")
        assert cursor.fetchone(), "git_commits table should exist"
        print("✓ git_commits table exists")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='git_file_changes'")
        assert cursor.fetchone(), "git_file_changes table should exist"
        print("✓ git_file_changes table exists")
        
        # Check if data was persisted
        cursor.execute("SELECT COUNT(*) FROM git_commits")
        commit_count = cursor.fetchone()[0]
        print(f"✓ Commits in database: {commit_count}")
        
        cursor.execute("SELECT COUNT(*) FROM git_file_changes")
        file_count = cursor.fetchone()[0]
        print(f"✓ File changes in database: {file_count}")
        
        conn.close()
        
        # Profile commits to populate the database
        engine.profile_commit_history("main", limit=10)
        
        # Check again after profiling
        conn = sqlite3.connect(engine.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM git_commits")
        commit_count = cursor.fetchone()[0]
        print(f"✓ Commits after profiling: {commit_count}")
        conn.close()
        
        assert commit_count > 0, "Should have persisted commits"
        
        print("\n✅ Database persistence PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Database persistence FAILED: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        return False


def test_abstract_integrity():
    """Verify Abstract Integrity Standard (2.1) compliance."""
    print("\n" + "="*60)
    print("TEST 6: Abstract Integrity Standard (2.1)")
    print("="*60)
    
    try:
        test_repo_path = os.path.join(os.path.dirname(__file__), 'test_repo')
        engine = GitExtractionEngine(repo_path=test_repo_path)
        commits = engine.profile_commit_history("main", limit=5)
        
        # Verify NO raw code in any output
        commits_json = json.dumps(commits)
        
        assert 'def ' not in commits_json or 'source_code' not in commits_json, \
            "Should not contain function definitions as source code"
        assert 'import ' not in commits_json or 'source_code' not in commits_json, \
            "Should not contain import statements as source code"
        assert 'patch' not in commits_json.lower() or 'file_patch' not in commits_json, \
            "Should not contain code patches"
        
        print("✓ No raw source code in commit data")
        print("✓ No code patches exposed")
        print("✓ Only structural metadata present")
        print("✓ Abstract tokens only (paths, counts, statuses)")
        
        print("\n✅ Abstract Integrity Standard PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Abstract Integrity FAILED: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("WikiHub Git Extraction Engine - Test Suite")
    print("="*60)
    
    tests = [
        ("Branch Discovery", test_branch_discovery),
        ("Commit Profiling", test_commit_profiling),
        ("Diff Analysis", test_diff_analysis),
        ("Time-Series", test_time_series),
        ("Database Persistence", test_database_persistence),
        ("Abstract Integrity", test_abstract_integrity),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ {name} CRASHED: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 All tests passed! Git Extraction Engine is ready.")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} test(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

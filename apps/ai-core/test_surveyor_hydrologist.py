#!/usr/bin/env python3
"""
Test the Surveyor AST analyzer and Hydrologist SQL lineage analyzer.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services'))

from tree_sitter_analyzer import LanguageRouter
from sql_lineage import SQLLineageAnalyzer


def test_language_router():
    print("\n" + "="*60)
    print("TEST: Surveyor LanguageRouter")
    print("="*60)
    router = LanguageRouter()
    print(f"Supported extensions: {router.supported_extensions()}")
    sample_py = 'def hello_world():\n    return "hello"\n'
    try:
        temp_path = os.path.join(os.path.dirname(__file__), 'temp_sample.py')
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(sample_py)
        result = router.analyze_file(temp_path)
        print(f"Symbols: {result.get('symbols')}")
        print(f"Imports: {result.get('imports')}")
        assert isinstance(result.get('symbols'), list)
        assert isinstance(result.get('imports'), list)
        print("✅ LanguageRouter analysis PASSED")
    except AssertionError as err:
        print(f"❌ LanguageRouter analysis FAILED: {err}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_sql_lineage():
    print("\n" + "="*60)
    print("TEST: Hydrologist SQLLineageAnalyzer")
    print("="*60)
    lineage = SQLLineageAnalyzer()
    sql = """
        WITH cte AS (
            SELECT id, user_id FROM users
        )
        SELECT u.name, o.amount FROM cte u
        JOIN orders o ON u.id = o.user_id
    """
    dependencies = lineage.extract_sql_dependencies(sql, dialect='postgres')
    print(f"Dependencies: {dependencies}")
    assert isinstance(dependencies, list)
    if dependencies:
        assert 'source_datasets' in dependencies[0]
        assert 'target_dataset' in dependencies[0]
    print("✅ SQL lineage parsing PASSED")


def test_python_inline_sql():
    print("\n" + "="*60)
    print("TEST: Hydrologist Python inline SQL extraction")
    print("="*60)
    lineage = SQLLineageAnalyzer()
    sample_code = '''\nquery = """SELECT id FROM customers WHERE active = 1"""\nprint(query)\n'''
    results = lineage.extract_lineage_from_python_source(sample_code)
    print(f"Inline results: {results}")
    assert isinstance(results, list)
    print("✅ Inline SQL lineage extraction PASSED")


if __name__ == '__main__':
    test_language_router()
    test_sql_lineage()
    test_python_inline_sql()

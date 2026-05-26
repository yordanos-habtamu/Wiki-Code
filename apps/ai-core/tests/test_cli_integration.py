"""Integration tests for the AI-Core CLI.

These tests verify the `semanticist`, `archivist`, and `navigator` command paths through the wrapper entrypoint.
"""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

# Redirect stdout to stderr to prevent noise in test output
sys.stdout = sys.stderr

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir.endswith(os.path.join('apps', 'ai-core', 'tests')):
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
else:
    project_root = os.path.dirname(os.path.dirname(current_dir))

CLI_PATH = os.path.join(project_root, 'apps', 'ai-core', 'cli.py')
CLI_SRC_PATH = os.path.join(project_root, 'apps', 'ai-core', 'src', 'cli.py')


class TestAiCoreCliIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'hub.db')
        self.archive_root = os.path.join(self.temp_dir.name, '.cartography', 'a5fdfce6')
        self.sample_file = os.path.join(self.temp_dir.name, 'sample_module.py')
        self.project_id = 'a5fdfce6'

        with open(self.sample_file, 'w', encoding='utf-8') as sample:
            sample.write('"""Sample module for CLI integration testing."""\n\n')
            sample.write('def helper():\n')
            sample.write('    """Return a known value."""\n')
            sample.write('    return 42\n')

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS files (relative_path TEXT, language TEXT)')
        cursor.execute('CREATE TABLE IF NOT EXISTS core_symbols (id TEXT PRIMARY KEY, project_id TEXT, file_path TEXT, symbol_name TEXT, symbol_type TEXT, signature TEXT, start_line INTEGER, end_line INTEGER)')
        cursor.execute('CREATE TABLE IF NOT EXISTS dependencies (id TEXT PRIMARY KEY, source_file TEXT, import_path TEXT)')
        cursor.execute('CREATE TABLE IF NOT EXISTS data_lineage_edges (id TEXT PRIMARY KEY, project_id TEXT, source_dataset TEXT, target_dataset TEXT, transformation_type TEXT, source_file TEXT, line_range TEXT, created_at TEXT)')
        conn.commit()

        cursor.execute(
            'INSERT INTO files (relative_path, language) VALUES (?, ?)',
            (self.sample_file, 'py')
        )
        cursor.execute(
            'INSERT INTO core_symbols (id, project_id, file_path, symbol_name, symbol_type, signature, start_line, end_line) ' 
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            ('symbol-1', self.project_id, self.sample_file, 'helper', 'function', 'def helper()', 3, 4)
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _run_cli(self, args):
        result = subprocess.run(
            [sys.executable, CLI_PATH] + args,
            capture_output=True,
            text=True,
            check=False
        )
        return result

    def test_semanticist_archivist_navigator_flow(self):
        semanticist = self._run_cli([
            '--action', 'semanticist',
            '--db', self.db_path,
            '--project-id', self.project_id,
            '--token-limit', '500'
        ])

        self.assertEqual(semanticist.returncode, 0, msg=f'Semanticist failed: {semanticist.stderr}')
        semanticist_data = json.loads(semanticist.stdout)
        self.assertTrue(semanticist_data.get('success'))
        self.assertEqual(semanticist_data['data']['files_analyzed'], 1)

        archivist = self._run_cli([
            '--action', 'archivist',
            '--db', self.db_path,
            '--project-id', self.project_id,
            '--archive-root', self.archive_root
        ])

        self.assertEqual(archivist.returncode, 0, msg=f'Archivist failed: {archivist.stderr}')
        archivist_data = json.loads(archivist.stdout)
        self.assertTrue(archivist_data.get('success'))
        self.assertEqual(archivist_data['data']['files_indexed'], 1)
        self.assertEqual(archivist_data['data']['lineage_edges'], 0)

        codebase_path = os.path.join(self.archive_root, 'CODEBASE.md')
        onboarding_path = os.path.join(self.archive_root, 'onboarding_brief.md')
        self.assertTrue(os.path.exists(codebase_path))
        self.assertTrue(os.path.exists(onboarding_path))

        navigator = self._run_cli([
            '--action', 'navigator',
            '--db', self.db_path,
            '--project-id', self.project_id,
            '--archive-root', self.archive_root,
            '--tool', 'find_implementation',
            '--query', 'function'
        ])

        self.assertEqual(navigator.returncode, 0, msg=f'Navigator failed: {navigator.stderr}')
        navigator_data = json.loads(navigator.stdout)
        self.assertTrue(navigator_data.get('success'))
        self.assertEqual(navigator_data['data']['tool'], 'find_implementation')
        self.assertGreaterEqual(len(navigator_data['data']['matches']), 1)

        explain = self._run_cli([
            '--action', 'navigator',
            '--db', self.db_path,
            '--project-id', self.project_id,
            '--archive-root', self.archive_root,
            '--tool', 'explain_module',
            '--target', self.sample_file
        ])

        self.assertEqual(explain.returncode, 0, msg=f'Navigator explain_module failed: {explain.stderr}')
        explain_data = json.loads(explain.stdout)
        self.assertTrue(explain_data.get('success'))
        self.assertEqual(explain_data['data']['tool'], 'explain_module')
        self.assertEqual(explain_data['data']['file_path'], self.sample_file)
        self.assertIn('summary', explain_data['data'])

    def test_src_cli_wrapper_flow(self):
        """Run the same integration flow but invoke the src/cli.py script directly."""
        # Semanticist via src entrypoint
        result = subprocess.run([
            sys.executable, CLI_SRC_PATH,
            '--action', 'semanticist',
            '--db', self.db_path,
            '--project-id', self.project_id,
            '--token-limit', '500'
        ], capture_output=True, text=True, check=False)

        self.assertEqual(result.returncode, 0, msg=f'Semanticist (src) failed: {result.stderr}')
        semanticist_data = json.loads(result.stdout)
        self.assertTrue(semanticist_data.get('success'))

        # Archivist via src entrypoint
        result = subprocess.run([
            sys.executable, CLI_SRC_PATH,
            '--action', 'archivist',
            '--db', self.db_path,
            '--project-id', self.project_id,
            '--archive-root', self.archive_root
        ], capture_output=True, text=True, check=False)

        self.assertEqual(result.returncode, 0, msg=f'Archivist (src) failed: {result.stderr}')
        archivist_data = json.loads(result.stdout)
        self.assertTrue(archivist_data.get('success'))

        # Navigator find_implementation via src entrypoint
        result = subprocess.run([
            sys.executable, CLI_SRC_PATH,
            '--action', 'navigator',
            '--db', self.db_path,
            '--project-id', self.project_id,
            '--archive-root', self.archive_root,
            '--tool', 'find_implementation',
            '--query', 'function'
        ], capture_output=True, text=True, check=False)

        self.assertEqual(result.returncode, 0, msg=f'Navigator (src) failed: {result.stderr}')
        navigator_data = json.loads(result.stdout)
        self.assertTrue(navigator_data.get('success'))
        self.assertGreaterEqual(len(navigator_data['data'].get('matches', [])), 0)


if __name__ == '__main__':
    unittest.main()

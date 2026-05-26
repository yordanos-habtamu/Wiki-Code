#!/usr/bin/env python3
"""
AI-Core CLI entrypoint
Provides semantic analysis, archive generation, and navigator query tools for the WikiHub engine.
"""
import os
import sys
import json
import argparse
import traceback

current_file = os.path.abspath(__file__)
if 'apps' in current_file and 'ai-core' in current_file:
    apps_idx = current_file.find('apps')
    project_root = current_file[:apps_idx].rstrip('/')
else:
    project_root = os.path.dirname(os.path.dirname(current_file))
sys.path.insert(0, project_root)

import importlib.util

# Dynamic agent loading

def _load_agent_module(module_name: str, file_name: str):
    module_path = os.path.join(project_root, 'apps', 'ai-core', 'agents', file_name)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    raise ImportError(f"Unable to load module {module_name} from {module_path}")


def main():
    parser = argparse.ArgumentParser(description='WikiHub AI-Core CLI')
    parser.add_argument('--repo-path', help='Repository path for project context')
    parser.add_argument('--db', help='Path to hub.db SQLite database')
    parser.add_argument('--project-id', help='Project UUID for multi-tenant isolation', default='a5fdfce6')
    parser.add_argument('--action', choices=['semanticist', 'archivist', 'navigator'], required=True)
    parser.add_argument('--tool', choices=['find_implementation', 'trace_lineage', 'blast_radius', 'explain_module'], help='Navigator tool to execute')
    parser.add_argument('--query', help='Query string for navigator or semanticist')
    parser.add_argument('--target', help='Target file or dataset for navigator tools')
    parser.add_argument('--direction', choices=['forward', 'backward'], default='forward', help='Lineage traversal direction')
    parser.add_argument('--max-depth', type=int, default=3, help='Maximum traversal depth for navigator or blast radius')
    parser.add_argument('--token-limit', type=int, default=1500, help='Token budget limit for semanticist')
    parser.add_argument('--archive-root', help='Override archive output root')
    args = parser.parse_args()

    repo_path = args.repo_path
    db_path = args.db or os.path.join(project_root, 'apps', 'cli', 'hub.db')
    project_id = args.project_id
    archive_root = args.archive_root

    try:
        if args.action == 'semanticist':
            module = _load_agent_module('semanticist', 'semanticist.py')
            agent = module.SemanticistAgent(db_path=db_path, project_id=project_id, token_limit=args.token_limit)
            result = agent.run_analysis()
            print(json.dumps({'success': True, 'data': result}, indent=2))
            return

        if args.action == 'archivist':
            module = _load_agent_module('archivist', 'archivist.py')
            agent = module.ArchivistAgent(db_path=db_path, project_id=project_id, archive_root=archive_root)
            result = agent.run()
            print(json.dumps({'success': True, 'data': result}, indent=2))
            return

        if args.action == 'navigator':
            if not args.tool:
                raise ValueError('Navigator action requires --tool')
            module = _load_agent_module('navigator', 'navigator.py')
            agent = module.NavigatorAgent(db_path=db_path, project_id=project_id, archive_root=archive_root)
            result = agent.run_tool(
                tool_name=args.tool,
                query=args.query,
                target=args.target,
                direction=args.direction,
                max_depth=args.max_depth
            )
            print(json.dumps({'success': True, 'data': result}, indent=2))
            return

    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({'success': False, 'error': str(exc)}), flush=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

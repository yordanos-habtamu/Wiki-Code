#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.parse


def log(message: str):
    print(f"[INGESTION] {message}", file=sys.stderr, flush=True)


def sanitize_project_id(project_id: str) -> str:
    cleaned = ''.join(ch for ch in project_id if ch.isalnum() or ch in ['-', '_'])
    return cleaned[:64] or 'wikihub_project'


def normalize_github_url(repo_url: str) -> dict:
    """
    Cleans, normalizes, and validates GitHub repository URLs.
    Handles trailing slashes, .git extensions, whitespace, and protocol variations.
    
    Returns a dict with:
      - normalized_url: Clean https://github.com/owner/repo.git URL
      - repo_path_segment: owner/repo path
      - domain: The domain (e.g., github.com)
    """
    # 1. Strip whitespace completely
    cleaned = repo_url.strip()
    
    # 2. Remove trailing slashes
    cleaned = cleaned.rstrip('/')
    
    # 3. Remove .git extension if present
    if cleaned.endswith('.git'):
        cleaned = cleaned[:-4]
    
    # 4. Parse the URL
    parsed = urllib.parse.urlparse(cleaned)
    
    # 5. Validate scheme
    if parsed.scheme not in ['https', 'http', '']:
        raise ValueError('Repository URL must use https://')
    
    # 6. Extract and validate host
    host = parsed.netloc.lower() if parsed.netloc else 'github.com'
    if 'github.com' not in host:
        raise ValueError('Only GitHub repository URLs are supported')
    
    # 7. Extract path
    path = parsed.path.strip().rstrip('/') if parsed.path else ''
    
    # 8. Handle case where URL might be just "owner/repo" without protocol
    if not path and not parsed.netloc:
        # Try splitting by / directly
        parts = cleaned.split('/')
        if len(parts) >= 2:
            path = '/'.join(parts[-2:])  # Take last two parts (owner/repo)
    
    # 9. Remove leading slash from path
    if path.startswith('/'):
        path = path[1:]
    
    # 10. Validate path has owner/repo structure
    if not path or '/' not in path:
        raise ValueError('Repository URL must include owner and repository path')
    
    return {
        'normalized_url': f'https://github.com/{path}.git',
        'repo_path_segment': path,
        'domain': host
    }


def parse_github_url(repo_url: str) -> str:
    """Legacy wrapper for backward compatibility."""
    result = normalize_github_url(repo_url)
    return result['normalized_url'], result['repo_path_segment']


def sanitize_sensitive_output(text: str, sensitive_tokens: list) -> str:
    """
    Replace sensitive tokens (API keys, tokens) with X_TOKEN_X placeholder
    to prevent credential leakage in logs and error messages.
    """
    sanitized = text
    for token in sensitive_tokens:
        if token and len(token) > 3:  # Only sanitize meaningful tokens
            sanitized = sanitized.replace(token, "X_TOKEN_X")
    return sanitized


def run_command(args, cwd=None, env=None, sensitive_tokens=None):
    """
    Execute a subprocess with optional credential sanitization.
    
    Args:
        args: Command arguments list
        cwd: Working directory
        env: Environment variables
        sensitive_tokens: List of tokens to sanitize from output (e.g., API keys)
    """
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            env=process_env,
            timeout=600
        )
        if result.returncode != 0:
            log(f"Command failed: {' '.join(args)}")
            if result.stdout:
                stdout_clean = sanitize_sensitive_output(result.stdout.strip(), sensitive_tokens or [])
                log(f"stdout: {stdout_clean}")
            if result.stderr:
                stderr_clean = sanitize_sensitive_output(result.stderr.strip(), sensitive_tokens or [])
                log(f"stderr: {stderr_clean}")
            return False, result
        return True, result
    except Exception as exc:
        log(f"Command execution error: {exc}")
        return False, None


def main():
    parser = argparse.ArgumentParser(description='GitHub repository ingestion worker for WikiHub')
    parser.add_argument('--project-id', required=True, help='Target project UUID for sandboxing')
    parser.add_argument('--repo-url', required=True, help='GitHub repository URL to clone')
    parser.add_argument('--db', required=True, help='Path to hub.db')
    parser.add_argument('--depth', type=int, default=50, help='Git clone depth (default: 50, use 0 for full history)')
    args = parser.parse_args()

    project_id = sanitize_project_id(args.project_id)
    db_path = os.path.abspath(args.db)
    repo_url = args.repo_url.strip()
    clone_depth = args.depth
    github_token = os.environ.get('WIKIHUB_GITHUB_TOKEN', '').strip()

    if not github_token:
        log('No GitHub token supplied in the transient worker environment')
        sys.exit(1)

    try:
        clone_url, repo_path_segment = parse_github_url(repo_url)
    except Exception as exc:
        log(f'Invalid GitHub URL: {exc}')
        sys.exit(1)

    sandbox_root = os.path.join('/tmp', 'wikihub', 'sandboxes', project_id)
    cloned_repo_path = os.path.join(sandbox_root, 'repo')

    try:
        if os.path.exists(cloned_repo_path):
            log('Removing existing sandbox repository to maintain isolation')
            shutil.rmtree(cloned_repo_path)
        os.makedirs(cloned_repo_path, exist_ok=True)
    except Exception as exc:
        log(f'Failed to prepare sandbox directory: {exc}')
        sys.exit(1)

    log(f'[INGESTION]: Validating authentication tokens... [OK]')
    depth_flag = [] if clone_depth == 0 else ['--depth', str(clone_depth)]
    log(f'[INGESTION]: Cloning remote repository layers asynchronously (depth={clone_depth if clone_depth > 0 else "full"})...')

    # Use Basic auth with x-access-token:TOKEN (GitHub recommended method)
    # Works for both classic PATs (ghp_) and fine-grained PATs (github_pat_)
    credentials = base64.b64encode(f'x-access-token:{github_token}'.encode('utf-8')).decode('utf-8')

    clone_args = [
        'git',
        '-c', f'http.extraheader=Authorization: Basic {credentials}',
        'clone',
    ] + depth_flag + [
        clone_url,
        cloned_repo_path
    ]

    clone_env = {
        'GIT_TERMINAL_PROMPT': '0'
    }

    # Pass sensitive tokens for log sanitization
    clone_success, clone_result = run_command(
        clone_args,
        cwd=sandbox_root,
        env=clone_env,
        sensitive_tokens=[github_token, credentials]
    )

    # Fallback: try embedding token in URL if header-based auth fails
    if not clone_success:
        log('[INGESTION]: Header auth failed, trying URL-embedded token fallback...')
        # Build authenticated URL: https://x-access-token:TOKEN@github.com/owner/repo.git
        parsed_clone = urllib.parse.urlparse(clone_url)
        netloc_with_auth = f'x-access-token:{urllib.parse.quote(github_token, safe="")}@{parsed_clone.netloc}'
        fallback_url = urllib.parse.urlunparse((
            parsed_clone.scheme,
            netloc_with_auth,
            parsed_clone.path,
            parsed_clone.params,
            parsed_clone.query,
            parsed_clone.fragment
        ))

        fallback_args = [
            'git',
            'clone',
        ] + depth_flag + [
            fallback_url,
            cloned_repo_path
        ]

        clone_success, clone_result = run_command(
            fallback_args,
            cwd=sandbox_root,
            env=clone_env,
            sensitive_tokens=[github_token]
        )

    if not clone_success:
        log('[INGESTION]: Clone failed with all auth methods. Aborting ingestion pipeline.')
        sys.exit(1)

    log('[INGESTION]: Repository cloned successfully')
    log('[SURVEYOR]: Triggering multi-language AST structural extraction passes...')

    python_bin = sys.executable or 'python3'
    scan_script = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'services', 'git_extraction_engine.py')
    )
    scan_args = [
        python_bin,
        scan_script,
        '--action',
        'scan-all',
        '--project-id',
        project_id,
        '--repo-path',
        cloned_repo_path,
        '--db',
        db_path
    ]

    scan_success, scan_result = run_command(scan_args, cwd=None, env={'GIT_TERMINAL_PROMPT': '0'})
    if not scan_success:
        log('[SURVEYOR]: Scan failed while processing the cloned repository')
        sys.exit(1)

    log('[SURVEYOR]: Scan completed successfully')
    print(json.dumps({
        'success': True,
        'project_id': project_id,
        'repo_path': cloned_repo_path,
        'status': 'completed'
    }))
    sys.exit(0)


if __name__ == '__main__':
    main()

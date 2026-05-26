#!/usr/bin/env python3
"""AI-Core CLI wrapper.

This file exists to expose a simple top-level entrypoint for the ai-core CLI.
It imports the real implementation from `apps/ai-core/src/cli.py`.
"""
import os
import sys

current_file = os.path.abspath(__file__)
project_root = os.path.dirname(current_file)
sys.path.insert(0, project_root)

from src.cli import main

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Main entry point for Test Automation Agent."""

import sys
from pathlib import Path

# Ensure src is in python path
src_dir = Path(__file__).parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from agent.cli import app

if __name__ == "__main__":
    app()


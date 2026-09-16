#!/usr/bin/env python3
"""Launcher so Grok Bot can run: python3 run.py search --keywords 'AI'"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from job_agent.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Grok Bot / local launcher: python3 run.py discover --source jobsdb"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from auto_resume_bot.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

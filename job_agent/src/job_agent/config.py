from __future__ import annotations

import json
import os
from pathlib import Path

from .models import Profile

APP_DIR = Path(os.environ.get("JOB_AGENT_HOME", Path.cwd() / "workspace")).resolve()
PROFILE_PATH = APP_DIR / "profile.json"
RESUME_PATH = APP_DIR / "resume.md"
DB_PATH = APP_DIR / "tracker.sqlite"
PACKETS_DIR = APP_DIR / "packets"
IMPORT_DIR = APP_DIR / "imports"
REPLIES_DIR = APP_DIR / "replies"


def set_home(path: str | Path) -> Path:
    """Point the workspace at a folder. Safe to call from --home or tests."""
    global APP_DIR, PROFILE_PATH, RESUME_PATH, DB_PATH, PACKETS_DIR, IMPORT_DIR, REPLIES_DIR
    APP_DIR = Path(path).expanduser().resolve()
    PROFILE_PATH = APP_DIR / "profile.json"
    RESUME_PATH = APP_DIR / "resume.md"
    DB_PATH = APP_DIR / "tracker.sqlite"
    PACKETS_DIR = APP_DIR / "packets"
    IMPORT_DIR = APP_DIR / "imports"
    REPLIES_DIR = APP_DIR / "replies"
    return APP_DIR


def ensure_dirs() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    PACKETS_DIR.mkdir(parents=True, exist_ok=True)
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPLIES_DIR.mkdir(parents=True, exist_ok=True)


def load_profile() -> Profile:
    ensure_dirs()
    if not PROFILE_PATH.exists():
        return Profile()
    return Profile.from_dict(json.loads(PROFILE_PATH.read_text(encoding="utf-8")))


def save_profile(profile: Profile) -> None:
    ensure_dirs()
    PROFILE_PATH.write_text(
        json.dumps(profile.__dict__, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_resume() -> str:
    if RESUME_PATH.exists():
        return RESUME_PATH.read_text(encoding="utf-8")
    return ""

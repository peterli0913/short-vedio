from __future__ import annotations

import os
from pathlib import Path

import yaml


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_env(path: Path | None = None) -> None:
    env_path = path or project_root() / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config(config_path: str | Path | None = None) -> dict:
    root = project_root()
    path = Path(config_path) if config_path else root / "config.yaml"
    if not path.exists():
        path = root / "config.example.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data["_root"] = str(root)
    data["_config_path"] = str(path)
    return data


def load_profile(config_path: str | Path | None = None) -> tuple[dict, str]:
    cfg = load_config(config_path)
    profile = dict(cfg.get("profile") or {})
    rel = profile.get("resume_summary_path") or "data/resume_summary.txt"
    summary_path = Path(rel)
    if not summary_path.is_absolute():
        summary_path = project_root() / summary_path
    summary = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""
    return profile, summary

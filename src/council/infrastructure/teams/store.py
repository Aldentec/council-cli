from __future__ import annotations

from pathlib import Path


def teams_dir() -> Path:
    directory = Path.home() / ".council" / "teams"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def cache_dir() -> Path:
    directory = Path.home() / ".council" / "cache"
    directory.mkdir(parents=True, exist_ok=True)
    return directory

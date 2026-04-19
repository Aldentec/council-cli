from __future__ import annotations

from pathlib import Path

import yaml

from council.domain.models.config import CouncilFile


def load_council_file(path: str | Path = "council.yaml") -> CouncilFile:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    council = CouncilFile.model_validate(data)
    council.assign_missing_colors()
    return council


def save_council_file(council: CouncilFile, path: str | Path = "council.yaml") -> Path:
    path = Path(path)
    council.assign_missing_colors()
    path.write_text(council.to_yaml(), encoding="utf-8")
    return path

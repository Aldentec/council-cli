from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ContextBuildResult:
    content: str
    included_files: list[str] = field(default_factory=list)
    summarized_files: list[str] = field(default_factory=list)
    dropped_files: list[str] = field(default_factory=list)
    tokens_estimated: int = 0
    cache_status: str = "MISS"
    cache_path: str = ""


class ContextCache:
    def __init__(self, cache_directory: Path) -> None:
        self._dir = cache_directory

    def get(self, key: str) -> ContextBuildResult | None:
        text_path = self._dir / f"{key}.txt"
        meta_path = self._dir / f"{key}.json"
        if text_path.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            return ContextBuildResult(
                content=text_path.read_text(encoding="utf-8"),
                included_files=meta.get("included_files", []),
                summarized_files=meta.get("summarized_files", []),
                dropped_files=meta.get("dropped_files", []),
                tokens_estimated=meta.get("tokens_estimated", 0),
                cache_status="HIT",
                cache_path=str(text_path),
            )
        return None

    def put(self, key: str, result: ContextBuildResult) -> None:
        text_path = self._dir / f"{key}.txt"
        meta_path = self._dir / f"{key}.json"
        text_path.write_text(result.content, encoding="utf-8")
        meta_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")

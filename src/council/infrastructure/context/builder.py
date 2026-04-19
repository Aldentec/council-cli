from __future__ import annotations

import fnmatch
import hashlib
from pathlib import Path
from typing import Callable, Optional

from council.domain.models.config import CouncilFile
from council.infrastructure.context.cache import ContextBuildResult, ContextCache
from council.infrastructure.teams.store import cache_dir

ALLOWED_SUFFIXES = {".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".rst"}
ALLOWED_NAMES = {".env.example"}
FIXED_IGNORE_PATTERNS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    ".pytest_cache",
    ".history",
    "dist",
    "build",
    ".DS_Store",
}
FIXED_IGNORE_GLOBS = ["*.lock", "*.log", "*.pyc"]
PRIORITY_KEYWORDS = [
    "readme",
    "prd",
    "spec",
    "architecture",
    "roadmap",
    "brief",
    "overview",
    "summary",
    "design",
    "requirements",
]
MAX_FILE_SIZE = 50 * 1024


class ContextBuilder:
    def __init__(
        self,
        council: CouncilFile,
        workspace: str | Path,
        summarizer: Callable[[str, str], str] | None = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.council = council
        self.workspace = Path(workspace).resolve()
        self.summarizer = summarizer or self._fallback_summary
        self.on_progress = on_progress
        self._cache = ContextCache(cache_dir())

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    def build(self) -> ContextBuildResult:
        gathered = self._gather_files()
        digest = hashlib.md5()
        summarizer_id = f"{self.council.providers.default_provider}:{self.council.providers.ollama_default_model}"
        digest.update(summarizer_id.encode("utf-8"))
        for path, content in gathered:
            digest.update(self._display_path(path).encode("utf-8"))
            digest.update(content.encode("utf-8", errors="ignore"))
        cache_key = digest.hexdigest()

        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        sorted_gathered = sorted(gathered, key=lambda item: self._priority_score(item[0]))
        total = len(sorted_gathered)
        processed: list[tuple[str, str, int, bool]] = []
        for i, (path, content) in enumerate(sorted_gathered, 1):
            display_path = self._display_path(path)
            if self.on_progress:
                self.on_progress(f"Scanning project context... ({i}/{total}) {display_path}")
            rendered = content
            summarized = False
            if (
                self.council.context.summarize
                and self.estimate_tokens(content) > self.council.context.summarize_threshold
            ):
                if self.on_progress:
                    self.on_progress(f"Summarizing ({i}/{total}) {display_path}")
                rendered = self.summarizer(display_path, content)
                summarized = True
            processed.append((display_path, rendered.strip(), self.estimate_tokens(rendered), summarized))

        parts: list[str] = []
        included_files: list[str] = []
        summarized_files: list[str] = []
        dropped_files: list[str] = []
        total_tokens = 0

        for display_path, rendered, _, summarized in processed:
            block = f"## {display_path}\n\n{rendered}\n"
            block_tokens = self.estimate_tokens(block)
            if total_tokens + block_tokens > self.council.context.max_tokens:
                dropped_files.append(f"{display_path} (lowest priority, over budget)")
                continue
            parts.append(block)
            included_files.append(display_path)
            total_tokens += block_tokens
            if summarized:
                summarized_files.append(display_path)

        compiled = "\n".join(parts).strip() or "No eligible project context was found."
        cache_text_path = self._cache._dir / f"{cache_key}.txt"
        result = ContextBuildResult(
            content=compiled,
            included_files=included_files,
            summarized_files=summarized_files,
            dropped_files=dropped_files,
            tokens_estimated=self.estimate_tokens(compiled),
            cache_status="MISS",
            cache_path=str(cache_text_path),
        )
        self._cache.put(cache_key, result)
        return result

    def _gather_files(self) -> list[tuple[Path, str]]:
        found: dict[str, tuple[Path, str]] = {}
        for directory in self.council.context.directories or ["."]:
            root = (self.workspace / directory).resolve()
            if not root.exists():
                continue
            if root.is_file():
                self._maybe_add_file(root, found)
                continue
            for candidate in root.rglob("*"):
                self._maybe_add_file(candidate, found)

        for explicit in self.council.context.files:
            candidate = (self.workspace / explicit).resolve()
            self._maybe_add_file(candidate, found, explicit=True)

        return list(found.values())

    def _maybe_add_file(self, path: Path, found: dict[str, tuple[Path, str]], explicit: bool = False) -> None:
        if not path.exists() or not path.is_file():
            return
        if path.stat().st_size > MAX_FILE_SIZE:
            return
        if not explicit and not self._is_allowed(path):
            return
        rel = self._display_path(path)
        if self._should_ignore(path, rel):
            return
        try:
            content = path.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            return
        if not content:
            return
        found[rel] = (path, content)

    def _is_allowed(self, path: Path) -> bool:
        return path.suffix.lower() in ALLOWED_SUFFIXES or path.name.lower() in ALLOWED_NAMES

    def _should_ignore(self, path: Path, rel: str) -> bool:
        rel_lower = rel.lower()
        parts = {part.lower() for part in path.parts}
        if parts & {item.lower() for item in FIXED_IGNORE_PATTERNS}:
            return True
        if any(fnmatch.fnmatch(path.name.lower(), pattern.lower()) for pattern in FIXED_IGNORE_GLOBS):
            return True
        for pattern in self.council.context.ignore:
            normalized = pattern.replace("\\", "/").lower()
            if fnmatch.fnmatch(rel_lower, normalized) or normalized.rstrip("/") in rel_lower:
                return True
        return False

    def _priority_score(self, path: Path) -> tuple[int, str]:
        name = path.name.lower()
        for index, keyword in enumerate(PRIORITY_KEYWORDS):
            if keyword in name:
                return (index, name)
        return (999, name)

    def _display_path(self, path: Path) -> str:
        try:
            return path.relative_to(self.workspace).as_posix()
        except ValueError:
            return path.as_posix()

    @staticmethod
    def _fallback_summary(filename: str, content: str) -> str:
        excerpt = content.strip().splitlines()[:12]
        condensed = "\n".join(excerpt)
        if len(condensed) > 1200:
            condensed = condensed[:1200].rsplit(" ", 1)[0] + "…"
        return f"[Summarized from {filename}]\n{condensed}"

from pathlib import Path
from uuid import uuid4

from council.context import ContextBuilder
from council.models import ContextConfig, CouncilFile, ProjectConfig


def test_context_builder_summarizes_and_caches(tmp_path: Path):
    unique_marker = uuid4().hex
    (tmp_path / "README.md").write_text(
        f"# Project {unique_marker}\n" + ("important detail\n" * 500),
        encoding="utf-8",
    )
    (tmp_path / "notes.txt").write_text("small note", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.txt").write_text("ignore me", encoding="utf-8")

    council = CouncilFile(
        project=ProjectConfig(name="Test", description="Desc"),
        context=ContextConfig(directories=["."], max_tokens=500, summarize_threshold=20),
    )

    calls = []

    def summarizer(filename: str, content: str) -> str:
        calls.append(filename)
        return f"[Summarized from {filename}]\nsummary"

    first = ContextBuilder(council, tmp_path, summarizer=summarizer).build()
    second = ContextBuilder(council, tmp_path, summarizer=summarizer).build()

    assert first.cache_status == "MISS"
    assert second.cache_status == "HIT"
    assert calls
    assert "README.md" in first.included_files
    assert all("node_modules" not in item for item in first.included_files)

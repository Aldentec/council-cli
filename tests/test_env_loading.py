import os
from pathlib import Path

from council.env_utils import load_council_env


def test_load_council_env_reads_local_dotenv(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=test-key\n", encoding="utf-8")

    loaded = load_council_env(tmp_path)

    assert loaded is True
    assert os.getenv("ANTHROPIC_API_KEY") == "test-key"

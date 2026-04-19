from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class SavedSession:
    session_id: str
    started_at: str
    project_name: str
    history: list[dict]
    summary: str = ""                  # LLM-generated summary, filled after /end
    turn_count: int = 0


def sessions_dir(workspace: Path) -> Path:
    directory = workspace / ".council" / "sessions"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


class SessionStore:
    def __init__(self, workspace: Path) -> None:
        self._dir = sessions_dir(workspace)

    def save(self, session: SavedSession) -> Path:
        path = self._dir / f"{session.session_id}.json"
        payload = {
            "session_id": session.session_id,
            "started_at": session.started_at,
            "project_name": session.project_name,
            "turn_count": session.turn_count,
            "summary": session.summary,
            "history": session.history,
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def load(self, session_id: str) -> SavedSession | None:
        path = self._dir / f"{session_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return SavedSession(**data)

    def list_recent(self, limit: int = 5) -> list[SavedSession]:
        files = sorted(self._dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        sessions: list[SavedSession] = []
        for f in files[:limit]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                sessions.append(SavedSession(**data))
            except Exception:
                continue
        return sessions


def new_session_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

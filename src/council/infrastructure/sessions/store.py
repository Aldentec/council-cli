from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from council.domain.models.agent import AgentConfig


@dataclass
class SavedSession:
    session_id: str
    started_at: str
    project_name: str
    history: list[dict]
    team_id: str = ""
    team_meeting_number: int = 0
    summary: str = ""                  # LLM-generated summary, filled after /end
    turn_count: int = 0
    decision_ledger: dict = None


def sessions_dir(workspace: Path) -> Path:
    directory = workspace / ".council" / "sessions"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def canonical_team_signature(project_name: str, agents: Iterable[AgentConfig]) -> str:
    normalized_agents: list[str] = []
    for agent in agents:
        persona = (agent.persona or "").strip().lower()
        normalized_agents.append(f"{agent.name.strip().lower()}|{agent.role.strip().lower()}|{persona}")
    normalized_agents.sort()
    base = f"project:{project_name.strip().lower()}||agents:{'||'.join(normalized_agents)}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


class SessionStore:
    def __init__(self, workspace: Path) -> None:
        self._dir = sessions_dir(workspace)

    def save(self, session: SavedSession) -> Path:
        path = self._dir / f"{session.session_id}.json"
        payload = {
            "session_id": session.session_id,
            "started_at": session.started_at,
            "project_name": session.project_name,
            "team_id": session.team_id,
            "team_meeting_number": session.team_meeting_number,
            "turn_count": session.turn_count,
            "summary": session.summary,
            "history": session.history,
            "decision_ledger": session.decision_ledger or {"decisions": []},
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def load(self, session_id: str) -> SavedSession | None:
        path = self._dir / f"{session_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("team_id", "")
        data.setdefault("team_meeting_number", 0)
        data.setdefault("decision_ledger", {"decisions": []})
        return SavedSession(**data)

    def list_recent(self, limit: int = 5) -> list[SavedSession]:
        files = sorted(self._dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        sessions: list[SavedSession] = []
        for f in files[:limit]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                data.setdefault("team_id", "")
                data.setdefault("team_meeting_number", 0)
                data.setdefault("decision_ledger", {"decisions": []})
                sessions.append(SavedSession(**data))
            except Exception:
                continue
        return sessions

    def next_team_meeting_number(self, team_id: str) -> int:
        if not team_id:
            return 1

        highest = 0
        files = sorted(self._dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for file_path in files:
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            existing_team_id = str(data.get("team_id", ""))
            if existing_team_id != team_id:
                continue
            number = data.get("team_meeting_number", 0)
            if isinstance(number, int) and number > highest:
                highest = number
        return highest + 1


def new_session_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

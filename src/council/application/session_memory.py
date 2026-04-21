from __future__ import annotations

from council.domain.models.config import CouncilFile
from council.infrastructure.sessions.store import SavedSession, SessionStore, canonical_team_signature


def build_past_sessions_block(
    council: CouncilFile,
    workspace_path,
    summarizer: object | None = None,
) -> tuple[str, int]:
    """
    Load recent saved sessions and return a context block injected into the
    project briefing. Uses the LLM-generated summary when available; falls back
    to a compact transcript excerpt so the block is never empty.
    """
    if not council.settings.persist_sessions:
        return "", 0

    team_id = canonical_team_signature(council.project.name, council.agents)
    store = SessionStore(workspace_path)
    sessions = [
        s
        for s in store.list_recent(limit=max(council.settings.max_sessions_loaded * 5, 25))
        if s.team_id == team_id
    ][: council.settings.max_sessions_loaded]
    if not sessions:
        return "", 0

    parts: list[str] = []
    highest_meeting_number = 0
    for s in sessions:
        highest_meeting_number = max(highest_meeting_number, s.team_meeting_number)
        meeting_number = s.team_meeting_number if s.team_meeting_number > 0 else "Unknown"
        header = f"### Team Meeting #{meeting_number} — {s.started_at} ({s.turn_count} turns)"
        if s.summary:
            parts.append(f"{header}\n{s.summary.strip()}")
        else:
            # Summarize on the fly if summarizer available, else excerpt
            raw = _transcript_excerpt(s.history)
            if summarizer is not None:
                try:
                    text = summarizer(  # type: ignore[call-arg]
                        f"session-{s.session_id}",
                        raw,
                    )
                    parts.append(f"{header}\n{text.strip()}")
                    # Persist summary so we don't re-summarize next time
                    s.summary = text.strip()
                    store.save(s)
                except Exception:
                    parts.append(f"{header}\n{raw}")
            else:
                parts.append(f"{header}\n{raw}")

    if not parts:
        return "", highest_meeting_number

    return "## Past Sessions\n\n" + "\n\n".join(parts), highest_meeting_number


def _transcript_excerpt(history: list[dict], max_entries: int = 10) -> tuple[str, int]:
    lines: list[str] = []
    for item in history[-max_entries:]:
        speaker = item.get("speaker", "?")
        role = item.get("role", "")
        prefix = f"{speaker} ({role})" if role and role != "User" else speaker
        content = item.get("content", "").strip()
        if content:
            # Truncate very long turns to keep excerpt tight
            if len(content) > 300:
                content = content[:300].rsplit(" ", 1)[0] + "…"
            lines.append(f"{prefix}: {content}")
    return "\n".join(lines)

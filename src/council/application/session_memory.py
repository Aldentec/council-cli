from __future__ import annotations

from council.domain.models.config import CouncilFile
from council.infrastructure.sessions.store import SavedSession, SessionStore


def build_past_sessions_block(
    council: CouncilFile,
    workspace_path,
    summarizer: object | None = None,
) -> str:
    """
    Load recent saved sessions and return a context block injected into the
    project briefing. Uses the LLM-generated summary when available; falls back
    to a compact transcript excerpt so the block is never empty.
    """
    if not council.settings.persist_sessions:
        return ""

    store = SessionStore(workspace_path)
    sessions = store.list_recent(limit=council.settings.max_sessions_loaded)
    if not sessions:
        return ""

    parts: list[str] = []
    for s in sessions:
        header = f"### Session {s.started_at} ({s.turn_count} turns)"
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
        return ""

    return "## Past Sessions\n\n" + "\n\n".join(parts)


def _transcript_excerpt(history: list[dict], max_entries: int = 10) -> str:
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

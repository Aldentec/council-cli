from pathlib import Path

from council.application.session_memory import build_past_sessions_block
from council.domain.models.agent import AgentConfig
from council.domain.models.config import CouncilFile, ProjectConfig, SettingsConfig
from council.infrastructure.sessions.store import SavedSession, SessionStore, canonical_team_signature


def _council(persist_sessions: bool = True) -> CouncilFile:
    return CouncilFile(
        project=ProjectConfig(name="MemoryTest", description="Memory behavior"),
        settings=SettingsConfig(persist_sessions=persist_sessions, max_sessions_loaded=3),
        agents=[
            AgentConfig(name="Alex", role="CEO", persona="Strategic", system_prompt="You are Alex."),
            AgentConfig(name="Jordan", role="CTO", persona="Technical", system_prompt="You are Jordan."),
        ],
    )


def test_team_signature_changes_with_team_composition():
    council = _council()
    first = canonical_team_signature(council.project.name, council.agents)

    changed_agents = list(council.agents)
    changed_agents.append(
        AgentConfig(name="Sam", role="CFO", persona="Financial", system_prompt="You are Sam.")
    )
    second = canonical_team_signature(council.project.name, changed_agents)

    assert first != second


def test_session_store_tracks_team_meeting_numbers(tmp_path: Path):
    council = _council()
    team_id = canonical_team_signature(council.project.name, council.agents)
    store = SessionStore(tmp_path)

    assert store.next_team_meeting_number(team_id) == 1

    store.save(
        SavedSession(
            session_id="20260101T000000Z",
            started_at="2026-01-01T00:00:00Z",
            project_name=council.project.name,
            history=[{"speaker": "You", "role": "User", "content": "Hi"}],
            team_id=team_id,
            team_meeting_number=1,
            turn_count=1,
        )
    )

    assert store.next_team_meeting_number(team_id) == 2


def test_build_past_sessions_block_filters_to_same_team(tmp_path: Path):
    council = _council()
    team_id = canonical_team_signature(council.project.name, council.agents)
    other_team_id = "different-team"
    store = SessionStore(tmp_path)

    store.save(
        SavedSession(
            session_id="20260101T000000Z",
            started_at="2026-01-01T00:00:00Z",
            project_name=council.project.name,
            history=[{"speaker": "You", "role": "User", "content": "Meeting one"}],
            team_id=team_id,
            team_meeting_number=1,
            summary="First summary",
            turn_count=1,
        )
    )
    store.save(
        SavedSession(
            session_id="20260102T000000Z",
            started_at="2026-01-02T00:00:00Z",
            project_name=council.project.name,
            history=[{"speaker": "You", "role": "User", "content": "Other team"}],
            team_id=other_team_id,
            team_meeting_number=5,
            summary="Other summary",
            turn_count=1,
        )
    )

    block, highest = build_past_sessions_block(council, tmp_path)

    assert "First summary" in block
    assert "Other summary" not in block
    assert "Team Meeting #1" in block
    assert highest == 1

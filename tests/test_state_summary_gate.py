from council.application.council_service import CouncilService
from council.application.meeting_session import MeetingSession
from council.domain.models.agent import AgentConfig
from council.domain.models.config import CouncilFile, ProjectConfig


def _council() -> CouncilFile:
    return CouncilFile(
        project=ProjectConfig(name="StateGate", description="Coordinator gating"),
        agents=[
            AgentConfig(name="Alex", role="CEO", persona="Strategic", system_prompt="You are Alex."),
        ],
    )


def test_state_summary_only_for_relevant_user_messages():
    session = MeetingSession(_council(), "briefing", CouncilService(_council()))

    assert session._wants_state_summary("what did we discuss last time?")
    assert session._wants_state_summary("we have a contradiction here")
    assert not session._wants_state_summary("can you elaborate on that point")

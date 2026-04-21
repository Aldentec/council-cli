from council.application.council_service import CouncilService
from council.application.meeting_session import MeetingSession
from council.domain.models.agent import AgentConfig
from council.domain.models.config import CouncilFile, ProjectConfig


def _council() -> CouncilFile:
    return CouncilFile(
        project=ProjectConfig(name="LedgerSession", description="Decision consistency"),
        agents=[
            AgentConfig(name="Alex", role="CEO", persona="Strategic", system_prompt="You are Alex."),
        ],
    )


def test_user_delay_statement_updates_reddit_ledger():
    session = MeetingSession(_council(), "briefing", CouncilService(_council()))

    session._extract_decision_from_user("We should delay Reddit ads until we interview users.")

    rendered = session.decision_ledger.render_for_prompt()
    assert "Reddit ads" in rendered
    assert "Delay Reddit ads" in rendered

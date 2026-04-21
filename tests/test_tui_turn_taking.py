from council.application.meeting_session import MeetingSession
from council.domain.models.agent import AgentConfig
from council.domain.models.config import CouncilFile, ProjectConfig


def _council() -> CouncilFile:
    return CouncilFile(
        project=ProjectConfig(name="LyricFollow", description="Music app"),
        agents=[
            AgentConfig(name="Alex", role="CEO", persona="Strategic", system_prompt="You are Alex."),
            AgentConfig(name="Jordan", role="CTO", persona="Technical", system_prompt="You are Jordan."),
            AgentConfig(name="Sam", role="CFO", persona="Financial", system_prompt="You are Sam."),
            AgentConfig(name="Morgan", role="Devil's Advocate", persona="Contrarian", system_prompt="You are Morgan."),
        ],
    )


def test_direct_address_limits_first_response_to_target_agent():
    session = MeetingSession(_council(), "briefing")

    ordered = session._ordered_agents("Jordan, what do you think about iOS vs Android?")

    assert [agent.name for agent in ordered] == ["Jordan"]


def test_general_prompt_keeps_full_room_in_rotation():
    session = MeetingSession(_council(), "briefing")

    ordered = session._ordered_agents("What does everyone think about iOS vs Android?")

    assert [agent.name for agent in ordered] == ["Alex", "Jordan", "Sam", "Morgan"]


def test_history_question_summons_full_room():
    session = MeetingSession(_council(), "briefing")

    ordered = session._ordered_agents("What did we talk about last time?")

    assert set(agent.name for agent in ordered) == {"Alex", "Jordan", "Sam", "Morgan"}

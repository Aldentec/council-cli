from council.models import AgentConfig, CouncilFile, ProjectConfig
from council.orchestrator import MeetingOrchestrator


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
    orchestrator = MeetingOrchestrator(_council(), "briefing")

    ordered = orchestrator._ordered_agents("Jordan, what do you think about iOS vs Android?")

    assert [agent.name for agent in ordered] == ["Jordan"]


def test_general_prompt_keeps_full_room_in_rotation():
    orchestrator = MeetingOrchestrator(_council(), "briefing")

    ordered = orchestrator._ordered_agents("What does the room think about iOS vs Android?")

    assert [agent.name for agent in ordered] == ["Alex", "Jordan", "Sam", "Morgan"]

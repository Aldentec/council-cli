from council.models import AgentConfig, CouncilFile, ProjectConfig
from council.orchestrator import AnthropicFacade, MeetingOrchestrator


def _council() -> CouncilFile:
    return CouncilFile(
        project=ProjectConfig(name="LyricFollow", description="Music app"),
        agents=[
            AgentConfig(name="Alex", role="CEO", persona="Strategic", system_prompt="You are Alex."),
            AgentConfig(name="Jordan", role="CTO", persona="Technical", system_prompt="You are Jordan."),
            AgentConfig(name="Sam", role="CFO", persona="Financial", system_prompt="You are Sam."),
        ],
    )


def test_model_aliases_are_normalized_for_api_calls():
    ai = AnthropicFacade()

    # Legacy shorthand aliases should resolve to canonical versioned IDs
    assert ai._model_name("claude-sonnet-4-6") != "claude-sonnet-4-6"
    assert ai._model_name("claude-3-5-haiku-latest") == "claude-haiku-4-5-20251001"
    # Canonical versioned IDs should pass through unchanged
    assert ai._model_name("claude-haiku-4-5-20251001") == "claude-haiku-4-5-20251001"


def test_directly_addressed_agent_speaks_first():
    orchestrator = MeetingOrchestrator(_council(), "briefing")

    ordered = orchestrator._ordered_agents("Jordan, what do you think about iOS vs Android?")

    assert ordered[0].name == "Jordan"

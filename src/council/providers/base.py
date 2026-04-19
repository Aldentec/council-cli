from __future__ import annotations

from typing import Generator, Protocol, runtime_checkable

from council.models import AgentConfig, CouncilFile


@runtime_checkable
class LLMProvider(Protocol):
    provider_name: str

    def ping(self) -> tuple[bool, str]: ...
    def fetch_models(self) -> list[str]: ...

    def expand_persona(
        self,
        name: str,
        role: str,
        short_persona: str,
        project_name: str,
        project_description: str,
    ) -> str: ...

    def summarize_file(self, filename: str, content: str) -> str: ...

    def stream_reply(
        self,
        agent: AgentConfig,
        council: CouncilFile,
        shared_context: str,
        history: list[dict],
    ) -> Generator[str, None, None]: ...

    def summarize_meeting(self, council: CouncilFile, history: list[dict]) -> str: ...

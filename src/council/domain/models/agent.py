from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    role: str
    persona: str
    system_prompt: str
    model: str = "llama3.2"
    provider: str | None = None  # None = auto-detect: claude-* → anthropic, else → ollama
    color: str = "#C9A227"

from __future__ import annotations

import yaml
from pydantic import BaseModel, Field, field_validator

from council.domain.models.agent import AgentConfig
from council.shared.constants import DEFAULT_COLORS, DEFAULT_IGNORES
from council.shared.types import ConversationStyle


class ProjectConfig(BaseModel):
    name: str = "My Startup"
    description: str = "A project that needs a sharper room."
    industry: str = "Technology"
    stage: str = "Idea"


class ContextConfig(BaseModel):
    directories: list[str] = Field(default_factory=lambda: ["."])
    files: list[str] = Field(default_factory=list)
    ignore: list[str] = Field(default_factory=lambda: list(DEFAULT_IGNORES))
    max_tokens: int = 6000
    summarize_threshold: int = 800
    summarize: bool = True

    @field_validator("directories", "files", "ignore", mode="before")
    @classmethod
    def _normalize_list(cls, value: object) -> list[str]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return [str(item).strip() for item in value if str(item).strip()]


class AuthorConfig(BaseModel):
    name: str = ""
    github: str = ""


class TemplateConfig(BaseModel):
    name: str = "Custom"
    tags: list[str] = Field(default_factory=list)


class SettingsConfig(BaseModel):
    max_turns: int = 10
    sequential: bool = True
    user_can_interject: bool = True
    conversation_style: ConversationStyle = "collaborative"
    persist_sessions: bool = False
    max_sessions_loaded: int = 3


class ProvidersConfig(BaseModel):
    default_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "llama3.2"


class CouncilFile(BaseModel):
    council_version: str = "1.0.0"
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    author: AuthorConfig = Field(default_factory=AuthorConfig)
    template: TemplateConfig = Field(default_factory=TemplateConfig)
    agents: list[AgentConfig] = Field(default_factory=list)
    settings: SettingsConfig = Field(default_factory=SettingsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)

    def assign_missing_colors(self) -> None:
        for index, agent in enumerate(self.agents):
            if not agent.color:
                agent.color = DEFAULT_COLORS[index % len(DEFAULT_COLORS)]

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            self.model_dump(mode="json"),
            sort_keys=False,
            allow_unicode=True,
        )


class TemplateRoster(BaseModel):
    name: str
    tags: list[str] = Field(default_factory=list)
    agents: list[AgentConfig] = Field(default_factory=list)

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_IGNORES = ["tests/", "migrations/", "node_modules/"]
DEFAULT_COLORS = [
    "#C9A227",
    "#4A90E2",
    "#D97B66",
    "#6ABF9F",
    "#B084F5",
    "#E8B86D",
]


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


class AgentConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    role: str
    persona: str
    system_prompt: str
    model: str = "claude-sonnet-4-5"
    color: str = "#C9A227"


class SettingsConfig(BaseModel):
    max_turns: int = 10
    sequential: bool = True
    user_can_interject: bool = True
    conversation_style: Literal["collaborative", "debate", "socratic"] = "collaborative"


class CouncilFile(BaseModel):
    council_version: str = "1.0.0"
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    author: AuthorConfig = Field(default_factory=AuthorConfig)
    template: TemplateConfig = Field(default_factory=TemplateConfig)
    agents: list[AgentConfig] = Field(default_factory=list)
    settings: SettingsConfig = Field(default_factory=SettingsConfig)

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


def load_council_file(path: str | Path = "council.yaml") -> CouncilFile:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    council = CouncilFile.model_validate(data)
    council.assign_missing_colors()
    return council


def save_council_file(council: CouncilFile, path: str | Path = "council.yaml") -> Path:
    path = Path(path)
    council.assign_missing_colors()
    path.write_text(council.to_yaml(), encoding="utf-8")
    return path


def teams_dir() -> Path:
    directory = Path.home() / ".council" / "teams"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def cache_dir() -> Path:
    directory = Path.home() / ".council" / "cache"
    directory.mkdir(parents=True, exist_ok=True)
    return directory

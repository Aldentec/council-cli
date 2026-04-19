from __future__ import annotations

import getpass
from importlib import resources
from pathlib import Path

import questionary
import yaml
from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from council.models import (
    AgentConfig,
    AuthorConfig,
    ContextConfig,
    CouncilFile,
    DEFAULT_COLORS,
    ProjectConfig,
    SettingsConfig,
    TemplateConfig,
    TemplateRoster,
    load_council_file,
    save_council_file,
)
from council.orchestrator import AnthropicFacade

console = Console()


def _template_files() -> list:
    template_root = resources.files("council").joinpath("templates")
    preferred_order = {
        "startup-board.yaml": 0,
        "creative-agency.yaml": 1,
        "engineering-review.yaml": 2,
        "product-launch.yaml": 3,
        "debate-panel.yaml": 4,
        "war-room.yaml": 5,
    }
    return sorted(
        [item for item in template_root.iterdir() if item.name.endswith(".yaml")],
        key=lambda item: (preferred_order.get(item.name, 999), item.name),
    )


def load_template_rosters() -> list[TemplateRoster]:
    rosters: list[TemplateRoster] = []
    for item in _template_files():
        data = yaml.safe_load(item.read_text(encoding="utf-8")) or {}
        rosters.append(TemplateRoster.model_validate(data))
    return rosters


def choose_template() -> TemplateRoster:
    rosters = load_template_rosters()
    table = Table(title="Council Templates", header_style="bold #C9A227")
    table.add_column("#", style="#F0EDE6")
    table.add_column("Name", style="#F0EDE6")
    table.add_column("Tags", style="#8B8680")
    for index, roster in enumerate(rosters, start=1):
        table.add_row(str(index), roster.name, ", ".join(roster.tags))
    console.print(table)
    choice = IntPrompt.ask("Choose a starting template", default=1)
    return rosters[max(1, min(choice, len(rosters))) - 1]


def ensure_env_file(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        env_path.write_text("ANTHROPIC_API_KEY=\n", encoding="utf-8")


def ensure_env_gitignored(gitignore_path: str | Path = ".gitignore") -> None:
    gitignore = Path(gitignore_path)
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    lines = existing.splitlines()
    if ".env" not in lines:
        text = (existing.rstrip() + "\n.env\n").lstrip("\n")
        gitignore.write_text(text, encoding="utf-8")


def _pick_model(models: list[str], default: str) -> str:
    default_choice = default if default in models else models[0]
    result = questionary.select(
        "Model",
        choices=models,
        default=default_choice,
        style=questionary.Style([
            ("selected", "fg:#C9A227 bold"),
            ("pointer", "fg:#C9A227 bold"),
            ("highlighted", "fg:#C9A227"),
        ]),
    ).ask()
    return result or default_choice


def build_agent_from_prompt(
    project_name: str,
    project_description: str,
    index: int,
    default_name: str = "",
    default_role: str = "",
    default_persona: str = "",
    ai: AnthropicFacade | None = None,
    models: list[str] | None = None,
) -> AgentConfig:
    ai = ai or AnthropicFacade()
    name = Prompt.ask(f"Agent {index + 1} name", default=default_name or f"Advisor {index + 1}")
    role = Prompt.ask("Role", default=default_role or "Strategist")
    persona = Prompt.ask("Short persona", default=default_persona or "clear-eyed and direct")
    model_default = "claude-sonnet-4-6" if index < 2 else "claude-haiku-4-5-20251001"
    available = models or ai.fetch_models()
    model = _pick_model(available, model_default)
    system_prompt = ai.expand_persona(name, role, persona, project_name, project_description)
    color = DEFAULT_COLORS[index % len(DEFAULT_COLORS)]
    return AgentConfig(
        name=name,
        role=role,
        persona=persona,
        system_prompt=system_prompt,
        model=model,
        color=color,
    )


def run_init_wizard(config_path: str | Path = "council.yaml") -> Path:
    console.print("[bold #C9A227]Council[/bold #C9A227] — assemble the room")
    path = Path(config_path)
    if path.exists() and not Confirm.ask("A council.yaml already exists. Overwrite it?", default=False):
        raise SystemExit(1)

    ai = AnthropicFacade()
    template = choose_template()

    project_name = Prompt.ask("Project name", default="My Startup")
    project_description = Prompt.ask(
        "Project description",
        default="A tool or company idea that needs sharp feedback",
    )
    industry = Prompt.ask("Industry", default="Technology")
    stage = Prompt.ask("Stage", default="Pre-seed")

    directories = Prompt.ask("Context directories (comma-separated)", default=".")
    files = Prompt.ask("Extra context files (comma-separated, optional)", default="")
    author_name = Prompt.ask("Your name", default=getpass.getuser())
    github_handle = Prompt.ask("GitHub handle", default="")
    use_template_agents = Confirm.ask("Use the template roster as defaults?", default=True)
    default_count = len(template.agents) if use_template_agents else 3
    agent_count = IntPrompt.ask("How many agents?", default=min(max(default_count, 2), 6))

    available_models = ai.fetch_models()
    agents: list[AgentConfig] = []
    for index in range(agent_count):
        default_agent = template.agents[index] if use_template_agents and index < len(template.agents) else None
        agents.append(
            build_agent_from_prompt(
                project_name=project_name,
                project_description=project_description,
                index=index,
                default_name=default_agent.name if default_agent else "",
                default_role=default_agent.role if default_agent else "",
                default_persona=default_agent.persona if default_agent else "",
                ai=ai,
                models=available_models,
            )
        )

    preview = Table(title="Generated Council", header_style="bold #C9A227")
    preview.add_column("Name")
    preview.add_column("Role")
    preview.add_column("Persona")
    for agent in agents:
        preview.add_row(agent.name, agent.role, agent.persona)
    console.print(preview)

    if not Confirm.ask("Write council.yaml and .env now?", default=True):
        raise SystemExit(1)

    council = CouncilFile(
        project=ProjectConfig(
            name=project_name,
            description=project_description,
            industry=industry,
            stage=stage,
        ),
        context=ContextConfig(
            directories=[item.strip() for item in directories.split(",") if item.strip()],
            files=[item.strip() for item in files.split(",") if item.strip()],
        ),
        author=AuthorConfig(name=author_name, github=github_handle),
        template=TemplateConfig(name=template.name, tags=template.tags),
        agents=agents,
        settings=SettingsConfig(),
    )
    save_council_file(council, path)
    ensure_env_file()
    ensure_env_gitignored()
    console.print("[bold #6ABF9F]Council file created.[/bold #6ABF9F]")
    console.print("Next steps: [bold]council start[/bold]")
    return path


def add_agent_to_existing(config_path: str | Path = "council.yaml") -> CouncilFile:
    council = load_council_file(config_path)
    ai = AnthropicFacade()
    agent = build_agent_from_prompt(
        project_name=council.project.name,
        project_description=council.project.description,
        index=len(council.agents),
        ai=ai,
        models=ai.fetch_models(),
    )
    council.agents.append(agent)
    save_council_file(council, config_path)
    return council

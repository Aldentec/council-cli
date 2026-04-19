from __future__ import annotations

import getpass
import os
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from council.application.council_service import CouncilService
from council.application.wizard.model_wizard import build_agent_from_prompt
from council.domain.models.config import (
    AgentConfig,
    AuthorConfig,
    ContextConfig,
    CouncilFile,
    ProjectConfig,
    ProvidersConfig,
    SettingsConfig,
    TemplateConfig,
    TemplateRoster,
)
from council.domain.templates.registry import load_template_rosters
from council.infrastructure.config.loader import save_council_file

console = Console()


def _pick_provider() -> str:
    has_anthropic_key = bool(os.getenv("ANTHROPIC_API_KEY", "").strip().strip('"').strip("'"))
    default_choice = 2 if has_anthropic_key else 1

    console.print("\n[bold #C9A227]AI Provider[/bold #C9A227]")
    console.print("  1. [bold]Ollama[/bold] — 100% local, free, requires [dim]ollama serve[/dim]")
    console.print("  2. [bold]Anthropic[/bold] — cloud API, requires API key")

    raw = IntPrompt.ask("Choose provider", default=default_choice)
    if raw == 2:
        return "anthropic"
    return "ollama"


def ensure_env_file(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        env_path.write_text(
            "ANTHROPIC_API_KEY=\n"
            "OLLAMA_BASE_URL=http://localhost:11434\n"
            "OLLAMA_DEFAULT_MODEL=llama3.2\n",
            encoding="utf-8",
        )


def ensure_env_gitignored(gitignore_path: str | Path = ".gitignore") -> None:
    gitignore = Path(gitignore_path)
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    lines = existing.splitlines()
    additions = [entry for entry in [".env", ".council/"] if entry not in lines]
    if additions:
        text = (existing.rstrip() + "\n" + "\n".join(additions) + "\n").lstrip("\n")
        gitignore.write_text(text, encoding="utf-8")


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


def run_init_wizard(config_path: str | Path = "council.yaml") -> Path:
    console.print("[bold #C9A227]Council[/bold #C9A227] — assemble the room")
    path = Path(config_path)
    if path.exists() and not Confirm.ask("A council.yaml already exists. Overwrite it?", default=False):
        raise SystemExit(1)

    default_provider = _pick_provider()

    providers_cfg = ProvidersConfig(
        default_provider=default_provider,
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_default_model=os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.2"),
    )

    tmp_council = CouncilFile(providers=providers_cfg)
    ai = CouncilService(tmp_council)

    ok, status_msg = ai.ping()
    color = "#6ABF9F" if ok else "bold red"
    console.print(f"[{color}]{status_msg}[/{color}]")
    if not ok and default_provider == "ollama":
        console.print("[dim]Tip: run [bold]ollama serve[/bold] in another terminal, then restart council init.[/dim]")

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
                default_provider=default_provider,
            )
        )

    preview = Table(title="Generated Council", header_style="bold #C9A227")
    preview.add_column("Name")
    preview.add_column("Role")
    preview.add_column("Persona")
    preview.add_column("Model")
    for agent in agents:
        preview.add_row(agent.name, agent.role, agent.persona, agent.model)
    console.print(preview)

    console.print(
        f"\n[dim]Large files (over {ContextConfig().summarize_threshold} tokens) can be AI-summarized to "
        "save context space. Useful for cloud models; less important for local.[/dim]"
    )
    enable_summarize = Confirm.ask("Summarize large files?", default=True)

    console.print(
        "\n[dim]Session memory saves each meeting to [bold].council/sessions/[/bold] so future sessions "
        "remember past decisions. Each session is summarized before being injected into context.[/dim]"
    )
    enable_sessions = Confirm.ask("Enable session memory?", default=False)

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
            summarize=enable_summarize,
        ),
        author=AuthorConfig(name=author_name, github=github_handle),
        template=TemplateConfig(name=template.name, tags=template.tags),
        agents=agents,
        settings=SettingsConfig(persist_sessions=enable_sessions),
        providers=providers_cfg,
    )
    save_council_file(council, path)
    ensure_env_file()
    ensure_env_gitignored()
    console.print("[bold #6ABF9F]Council file created.[/bold #6ABF9F]")
    console.print("Next steps: [bold]council start[/bold]")
    return path

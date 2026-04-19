from __future__ import annotations

import getpass
import os
from importlib import resources
from pathlib import Path

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
    ProvidersConfig,
    SettingsConfig,
    TemplateConfig,
    TemplateRoster,
    load_council_file,
    save_council_file,
)
from council.orchestrator import CouncilAI

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


def _pick_provider() -> str:
    """Ask the user which provider to default to. Defaults to ollama unless ANTHROPIC_API_KEY is set."""
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
    if ".env" not in lines:
        text = (existing.rstrip() + "\n.env\n").lstrip("\n")
        gitignore.write_text(text, encoding="utf-8")


def _pick_model(models: list[str], default: str) -> str:
    default_choice = default if default in models else models[0]
    try:
        import questionary
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
    except ImportError:
        for idx, m in enumerate(models, 1):
            marker = " (default)" if m == default_choice else ""
            console.print(f"  {idx}. {m}{marker}")
        raw = Prompt.ask("Model number", default=str(models.index(default_choice) + 1))
        try:
            return models[int(raw) - 1]
        except (ValueError, IndexError):
            return default_choice


def _default_model_for(provider: str, models: list[str], index: int) -> str:
    if provider == "anthropic":
        preferred = "claude-sonnet-4-6" if index < 2 else "claude-haiku-4-5-20251001"
        return preferred if preferred in models else (models[0] if models else "claude-sonnet-4-6")
    # ollama: prefer the first available model
    return models[0] if models else "llama3.2"


def build_agent_from_prompt(
    project_name: str,
    project_description: str,
    index: int,
    default_name: str = "",
    default_role: str = "",
    default_persona: str = "",
    ai: CouncilAI | None = None,
    models: list[str] | None = None,
    default_provider: str = "ollama",
) -> AgentConfig:
    ai = ai or CouncilAI()
    name = Prompt.ask(f"Agent {index + 1} name", default=default_name or f"Advisor {index + 1}")
    role = Prompt.ask("Role", default=default_role or "Strategist")
    persona = Prompt.ask("Short persona", default=default_persona or "clear-eyed and direct")
    available = models or ai.fetch_models()
    model_default = _default_model_for(default_provider, available, index)
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

    default_provider = _pick_provider()

    providers_cfg = ProvidersConfig(
        default_provider=default_provider,
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        ollama_default_model=os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.2"),
    )

    # Build a temporary CouncilFile with just the providers config so CouncilAI can use it
    tmp_council = CouncilFile(providers=providers_cfg)
    ai = CouncilAI(tmp_council)

    # Verify connectivity before proceeding
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
        settings=SettingsConfig(),
        providers=providers_cfg,
    )
    save_council_file(council, path)
    ensure_env_file()
    ensure_env_gitignored()
    console.print("[bold #6ABF9F]Council file created.[/bold #6ABF9F]")
    console.print("Next steps: [bold]council start[/bold]")
    return path


def run_model_wizard(config_path: str | Path = "council.yaml", quick_model: str | None = None) -> CouncilFile:
    """Interactively switch models (and optionally provider) for all agents."""
    from council.providers import detect_provider

    council = load_council_file(config_path)

    # Show current state
    table = Table(title="Current Models", header_style="bold #C9A227")
    table.add_column("Agent")
    table.add_column("Role")
    table.add_column("Model")
    table.add_column("Provider", style="dim")
    for agent in council.agents:
        prov = detect_provider(agent.model, agent.provider)
        table.add_row(agent.name, agent.role, agent.model, prov)
    console.print(table)

    # Quick non-interactive path: apply a specific model to all agents
    if quick_model:
        for agent in council.agents:
            agent.model = quick_model
        _auto_update_default_provider(council, quick_model)
        save_council_file(council, config_path)
        console.print(f"[bold #6ABF9F]All agents updated to:[/bold #6ABF9F] {quick_model}")
        return council

    # Ask if they want to switch provider
    current_provider = council.providers.default_provider
    new_provider = _pick_provider_switch(current_provider)
    if new_provider != current_provider:
        council.providers.default_provider = new_provider

    # Fetch models from the chosen provider
    tmp_council = CouncilFile(providers=council.providers)
    ai = CouncilAI(tmp_council)
    ok, status_msg = ai.ping()
    color = "#6ABF9F" if ok else "bold red"
    console.print(f"[{color}]{status_msg}[/{color}]")

    available = ai.fetch_models()

    # Ask scope: same model for all, or per-agent
    all_at_once = Confirm.ask("\nApply the same model to all agents?", default=True)

    if all_at_once:
        current_first = council.agents[0].model if council.agents else ""
        model_default = current_first if current_first in available else available[0]
        chosen = _pick_model(available, model_default)
        for agent in council.agents:
            agent.model = chosen
        _auto_update_default_provider(council, chosen)
    else:
        for agent in council.agents:
            console.print(f"\n[bold]  {agent.name}[/bold] — {agent.role}  [dim](currently {agent.model})[/dim]")
            default = agent.model if agent.model in available else available[0]
            agent.model = _pick_model(available, default)
        # Update default_provider to match the majority of agents
        providers_used = [detect_provider(a.model, a.provider) for a in council.agents]
        majority = max(set(providers_used), key=providers_used.count)
        council.providers.default_provider = majority

    save_council_file(council, config_path)
    console.print("[bold #6ABF9F]Models saved.[/bold #6ABF9F]")
    return council


def _pick_provider_switch(current: str) -> str:
    console.print(f"\n[bold #C9A227]Provider[/bold #C9A227] [dim](current: {current})[/dim]")
    console.print("  1. Ollama — local, free")
    console.print("  2. Anthropic — cloud API")
    default = 2 if current == "anthropic" else 1
    raw = IntPrompt.ask("Provider", default=default)
    return "anthropic" if raw == 2 else "ollama"


def _auto_update_default_provider(council: CouncilFile, model: str) -> None:
    from council.providers import detect_provider
    council.providers.default_provider = detect_provider(model)


def add_agent_to_existing(config_path: str | Path = "council.yaml") -> CouncilFile:
    council = load_council_file(config_path)
    ai = CouncilAI(council)
    available = ai.fetch_models()
    agent = build_agent_from_prompt(
        project_name=council.project.name,
        project_description=council.project.description,
        index=len(council.agents),
        ai=ai,
        models=available,
        default_provider=council.providers.default_provider,
    )
    council.agents.append(agent)
    save_council_file(council, config_path)
    return council

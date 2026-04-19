from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from council.domain.models.agent import AgentConfig
from council.domain.models.config import CouncilFile
from council.infrastructure.config.loader import load_council_file, save_council_file
from council.providers import detect_provider
from council.shared.constants import DEFAULT_COLORS

console = Console()


def _default_model_for(provider: str, models: list[str], index: int) -> str:
    if provider == "anthropic":
        preferred = "claude-sonnet-4-6" if index < 2 else "claude-haiku-4-5-20251001"
        return preferred if preferred in models else (models[0] if models else "claude-sonnet-4-6")
    return models[0] if models else "llama3.2"


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


def build_agent_from_prompt(
    project_name: str,
    project_description: str,
    index: int,
    default_name: str = "",
    default_role: str = "",
    default_persona: str = "",
    ai: object | None = None,
    models: list[str] | None = None,
    default_provider: str = "ollama",
) -> AgentConfig:
    from council.application.council_service import CouncilService

    ai = ai or CouncilService()
    name = Prompt.ask(f"Agent {index + 1} name", default=default_name or f"Advisor {index + 1}")
    role = Prompt.ask("Role", default=default_role or "Strategist")
    persona = Prompt.ask("Short persona", default=default_persona or "clear-eyed and direct")
    available = models or ai.fetch_models()  # type: ignore[attr-defined]
    model_default = _default_model_for(default_provider, available, index)
    model = _pick_model(available, model_default)
    system_prompt = ai.expand_persona(name, role, persona, project_name, project_description)  # type: ignore[attr-defined]
    color = DEFAULT_COLORS[index % len(DEFAULT_COLORS)]
    return AgentConfig(
        name=name,
        role=role,
        persona=persona,
        system_prompt=system_prompt,
        model=model,
        color=color,
    )


def _pick_provider_switch(current: str) -> str:
    console.print(f"\n[bold #C9A227]Provider[/bold #C9A227] [dim](current: {current})[/dim]")
    console.print("  1. Ollama — local, free")
    console.print("  2. Anthropic — cloud API")
    default = 2 if current == "anthropic" else 1
    raw = IntPrompt.ask("Provider", default=default)
    return "anthropic" if raw == 2 else "ollama"


def _auto_update_default_provider(council: CouncilFile, model: str) -> None:
    council.providers.default_provider = detect_provider(model)


def run_model_wizard(
    config_path: str | Path = "council.yaml",
    quick_model: str | None = None,
) -> CouncilFile:
    from council.application.council_service import CouncilService

    council = load_council_file(config_path)

    table = Table(title="Current Models", header_style="bold #C9A227")
    table.add_column("Agent")
    table.add_column("Role")
    table.add_column("Model")
    table.add_column("Provider", style="dim")
    for agent in council.agents:
        prov = detect_provider(agent.model, agent.provider)
        table.add_row(agent.name, agent.role, agent.model, prov)
    console.print(table)

    if quick_model:
        for agent in council.agents:
            agent.model = quick_model
        _auto_update_default_provider(council, quick_model)
        save_council_file(council, config_path)
        console.print(f"[bold #6ABF9F]All agents updated to:[/bold #6ABF9F] {quick_model}")
        return council

    current_provider = council.providers.default_provider
    new_provider = _pick_provider_switch(current_provider)
    if new_provider != current_provider:
        council.providers.default_provider = new_provider

    tmp_council = CouncilFile(providers=council.providers)
    ai = CouncilService(tmp_council)
    ok, status_msg = ai.ping()
    color = "#6ABF9F" if ok else "bold red"
    console.print(f"[{color}]{status_msg}[/{color}]")

    available = ai.fetch_models()

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
        providers_used = [detect_provider(a.model, a.provider) for a in council.agents]
        majority = max(set(providers_used), key=providers_used.count)
        council.providers.default_provider = majority

    save_council_file(council, config_path)
    console.print("[bold #6ABF9F]Models saved.[/bold #6ABF9F]")
    return council


def add_agent_to_existing(config_path: str | Path = "council.yaml") -> CouncilFile:
    from council.application.council_service import CouncilService

    council = load_council_file(config_path)
    ai = CouncilService(council)
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

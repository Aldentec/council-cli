from __future__ import annotations

from rich.console import Console

from council.domain.models.config import CouncilFile
from council.infrastructure.context.cache import ContextBuildResult

console = Console()


def context_preview(result: ContextBuildResult) -> str:
    names = result.included_files[:2]
    preview = ", ".join(names) if names else "No context files"
    if len(result.summarized_files) > 0:
        preview += f" [+{len(result.summarized_files)} summarized]"
    return preview


def print_startup_summary(
    council: CouncilFile,
    result: ContextBuildResult,
    mode: str = "TUI",
    api_status: tuple[bool, str] | None = None,
) -> None:
    divider = "-" * 37
    console.print("[bold #6ABF9F]Council ready[/bold #6ABF9F]")
    console.print(divider)
    console.print(f"Project:   {council.project.name}")
    console.print(f"Mode:      {mode}")
    if api_status is not None:
        ok, label = api_status
        color = "#6ABF9F" if ok else "bold red"
        console.print(f"API:       [{color}]{label}[/{color}]")
    console.print(f"Agents:    {', '.join(f'{agent.name} ({agent.role})' for agent in council.agents)}")
    console.print(f"Context:   {context_preview(result)}")
    console.print(f"Tokens:    ~{result.tokens_estimated:,} estimated / {council.context.max_tokens:,} budget")
    if result.dropped_files:
        console.print(f"Dropped:   {result.dropped_files[0]}")
    console.print(f"Cache:     {result.cache_status}")
    console.print(divider)

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from council.context import ContextBuildResult
from council.models import CouncilFile
from council.orchestrator import CouncilAI, MeetingOrchestrator

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


def run_tui(council: CouncilFile, result: ContextBuildResult, api_status: tuple[bool, str] | None = None) -> None:
    ai = CouncilAI(council)
    orchestrator = MeetingOrchestrator(council, result.content, ai)

    print_startup_summary(council, result, mode="TUI", api_status=api_status)
    roster = Table(title="Advisors", header_style="bold #C9A227")
    roster.add_column("Name")
    roster.add_column("Role")
    roster.add_column("Persona")
    for agent in council.agents:
        roster.add_row(agent.name, agent.role, agent.persona)
    console.print(roster)
    console.print("[bold #C9A227]Commands:[/bold #C9A227] /end for summary, /quit to leave")

    warned_about_fallback = False

    while True:
        try:
            message = console.input("\n[bold #C9A227]You[/bold #C9A227] > ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[#8B8680]Meeting closed.[/#8B8680]")
            if orchestrator.history:
                console.print("[#8B8680]Run [bold]/end[/bold] next time, or type [bold]/summary[/bold] to get your meeting notes.[/#8B8680]")
            break

        if not message:
            continue
        if message.lower() in {"/quit", "quit", "exit"}:
            console.print("[#8B8680]Meeting closed.[/#8B8680]")
            break
        if message.lower() in {"/end", "/summary"}:
            console.print("\n[bold #C9A227]Meeting Summary[/bold #C9A227]")
            console.print(Markdown(orchestrator.end_meeting()))
            break

        console.print(Panel.fit(message, title="You", border_style="#C9A227"))
        orchestrator.history.append({"speaker": "You", "role": "User", "content": message})

        for agent in orchestrator._ordered_agents(message):
            console.print(f"\n[bold {agent.color}]{agent.name}[/bold {agent.color}] [#8B8680]— {agent.role}[/#8B8680]")
            full_response = ""
            for token in ai.stream_reply(agent, council, result.content, orchestrator.history):
                full_response += token
                console.print(token, end="", style=agent.color, highlight=False, soft_wrap=True)
            console.print("")
            if ai.last_error and not warned_about_fallback:
                console.print("[#8B8680]AI request failed — Council is using built-in fallback voices for this session.[/#8B8680]")
                warned_about_fallback = True
            orchestrator.history.append(
                {
                    "speaker": agent.name,
                    "role": agent.role,
                    "content": full_response.strip(),
                }
            )

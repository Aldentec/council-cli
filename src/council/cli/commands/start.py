from __future__ import annotations

import webbrowser
from pathlib import Path

import typer
import uvicorn
from rich.console import Console

from council.application.council_service import CouncilService
from council.application.session_memory import build_past_sessions_block
from council.infrastructure.config.env import load_council_env
from council.infrastructure.config.loader import load_council_file
from council.infrastructure.context.builder import ContextBuilder
from council.ui.tui.display import print_startup_summary
from council.ui.tui.session import run_tui
from council.ui.web.server import create_app

console = Console()

app = typer.Typer()


def _require_config(path: str | Path = "council.yaml") -> Path:
    config = Path(path)
    if not config.exists():
        console.print("[bold red]No council.yaml found.[/bold red] Run [bold]council init[/bold] first.")
        raise typer.Exit(1)
    return config


@app.callback(invoke_without_command=True)
def start_server(
    web: bool = typer.Option(False, "--web", help="Launch the optional web room instead of the terminal UI"),
    host: str = typer.Option("127.0.0.1", help="Host to bind for web mode"),
    port: int = typer.Option(4000, help="Port to bind for web mode"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open the browser automatically in web mode"),
) -> None:
    """Launch the meeting room in the terminal by default."""
    cwd = Path.cwd()
    load_council_env(cwd)
    config_path = _require_config()

    with console.status("[#8B8680]Loading config...[/#8B8680]", spinner="dots") as status:
        council = load_council_file(config_path)
        service = CouncilService(council)

        status.update("[#8B8680]Scanning project context...[/#8B8680]")
        context_result = ContextBuilder(
            council,
            cwd,
            summarizer=service.summarize_file,
            on_progress=lambda msg: status.update(f"[#8B8680]{msg}[/#8B8680]"),
        ).build()

        # Append past-session memory block if enabled
        past_block = ""
        meeting_number = 1
        if council.settings.persist_sessions:
            status.update("[#8B8680]Loading past sessions...[/#8B8680]")
            past_block, prior_meeting_count = build_past_sessions_block(council, cwd, summarizer=service.summarize_file)
            meeting_number = prior_meeting_count + 1

        status.update("[#8B8680]Checking connection...[/#8B8680]")
        api_status = service.ping()

    if past_block:
        context_result.content = context_result.content.rstrip() + "\n\n" + past_block
        console.print(f"[dim]Loaded {council.settings.max_sessions_loaded} past session(s) into context.[/dim]")

    if council.settings.persist_sessions:
        memory_line = (
            "## Team Memory\n"
            f"This is team meeting #{meeting_number}. "
            "On early meetings, ask clarifying questions and avoid pretending prior product familiarity. "
            "As meeting count grows, build on validated historical decisions and act as deeper product experts."
        )
        context_result.content = context_result.content.rstrip() + "\n\n" + memory_line

    if web:
        print_startup_summary(council, context_result, mode="Web", api_status=api_status)
        console.print(f"Opening http://{host}:{port}")
        if open_browser:
            webbrowser.open(f"http://{host}:{port}")
        app_instance = create_app(council, context_result, workspace=cwd)
        uvicorn.run(app_instance, host=host, port=port, log_level="warning")
        return

    run_tui(council, context_result, workspace=cwd, api_status=api_status)

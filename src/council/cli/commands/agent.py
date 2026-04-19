from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from council.application.wizard.model_wizard import add_agent_to_existing
from council.infrastructure.config.loader import load_council_file

console = Console()
app = typer.Typer()


def _require_config(path: str | Path = "council.yaml") -> Path:
    config = Path(path)
    if not config.exists():
        console.print("[bold red]No council.yaml found.[/bold red] Run [bold]council init[/bold] first.")
        raise typer.Exit(1)
    return config


@app.command("add-agent")
def add_agent() -> None:
    """Add a new advisor to the current Council file."""
    _require_config()
    council = add_agent_to_existing()
    console.print(f"[bold #6ABF9F]Added agent.[/bold #6ABF9F] Team now has {len(council.agents)} advisors.")


@app.command("list")
def list_agents() -> None:
    """List configured agents in the current Council file."""
    council = load_council_file(_require_config())
    table = Table(title=f"{council.project.name} — Council Roster", header_style="bold #C9A227")
    table.add_column("Name")
    table.add_column("Role")
    table.add_column("Model")
    table.add_column("Persona")
    for agent in council.agents:
        table.add_row(agent.name, agent.role, agent.model, agent.persona)
    console.print(table)

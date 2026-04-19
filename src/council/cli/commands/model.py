from __future__ import annotations

from pathlib import Path

import typer

from council.application.wizard.model_wizard import run_model_wizard
from council.infrastructure.config.env import load_council_env

app = typer.Typer()


def _require_config(path: str | Path = "council.yaml") -> Path:
    from rich.console import Console
    console = Console()
    config = Path(path)
    if not config.exists():
        console.print("[bold red]No council.yaml found.[/bold red] Run [bold]council init[/bold] first.")
        raise typer.Exit(1)
    return config


@app.callback(invoke_without_command=True)
def set_model(
    model_name: str | None = typer.Argument(None, help="Model name to apply to all agents immediately"),
) -> None:
    """Switch AI models for your advisors without re-running init."""
    load_council_env(Path.cwd())
    _require_config()
    run_model_wizard(quick_model=model_name)

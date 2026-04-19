from __future__ import annotations

import typer

from council.application.wizard.init_wizard import run_init_wizard

app = typer.Typer()


@app.callback(invoke_without_command=True)
def init() -> None:
    """Interactive wizard that creates council.yaml and .env."""
    run_init_wizard()

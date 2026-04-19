from __future__ import annotations

import shutil
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.table import Table

from council.domain.models.config import CouncilFile
from council.domain.templates.registry import load_template_rosters
from council.infrastructure.config.loader import load_council_file, save_council_file
from council.infrastructure.teams.store import teams_dir

console = Console()
app = typer.Typer()


def _require_config(path: str | Path = "council.yaml") -> Path:
    config = Path(path)
    if not config.exists():
        console.print("[bold red]No council.yaml found.[/bold red] Run [bold]council init[/bold] first.")
        raise typer.Exit(1)
    return config


def _raw_github_url(url: str) -> str:
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    return url


@app.command("teams")
def list_teams() -> None:
    """List saved teams in ~/.council/teams."""
    directory = teams_dir()
    entries = sorted(directory.glob("*.yaml"))
    if not entries:
        console.print("No saved teams yet.")
        return
    for item in entries:
        console.print(f"- {item.stem}")


@app.command("save")
def save(name: str = typer.Argument(..., help="Team name")) -> None:
    """Save the current Council file as a named team."""
    config = _require_config()
    destination = teams_dir() / f"{name}.yaml"
    shutil.copyfile(config, destination)
    console.print(f"[bold #6ABF9F]Saved team:[/bold #6ABF9F] {name}")


@app.command("use")
def use(name: str = typer.Argument(..., help="Saved team name")) -> None:
    """Load a saved team into the current directory."""
    source = teams_dir() / f"{name}.yaml"
    if not source.exists():
        console.print(f"[bold red]Unknown team:[/bold red] {name}")
        raise typer.Exit(1)
    shutil.copyfile(source, Path("council.yaml"))
    council = load_council_file("council.yaml")
    save_council_file(council, "council.yaml")
    console.print(f"[bold #6ABF9F]Loaded team:[/bold #6ABF9F] {name}")


@app.command("delete")
def delete(name: str = typer.Argument(..., help="Saved team name")) -> None:
    """Remove a saved team."""
    target = teams_dir() / f"{name}.yaml"
    if not target.exists():
        console.print(f"[bold red]Unknown team:[/bold red] {name}")
        raise typer.Exit(1)
    target.unlink()
    console.print(f"[bold red]Deleted team:[/bold red] {name}")


@app.command("switch")
def switch() -> None:
    """Interactively pick a saved team or built-in template and load it into the current directory."""
    saved = sorted(teams_dir().glob("*.yaml"))
    templates = load_template_rosters()

    if not saved and not templates:
        console.print("No teams or templates available.")
        raise typer.Exit(1)

    table = Table(header_style="bold #C9A227", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Name")
    table.add_column("Type", style="dim")

    idx = 1
    for item in saved:
        table.add_row(str(idx), item.stem, "saved team")
        idx += 1
    for roster in templates:
        table.add_row(str(idx), roster.name, "template")
        idx += 1

    console.print(table)

    raw = typer.prompt("Enter number")
    try:
        choice = int(raw)
        if not 1 <= choice <= idx - 1:
            raise ValueError
    except ValueError:
        console.print("[bold red]Invalid selection.[/bold red]")
        raise typer.Exit(1)

    if choice <= len(saved):
        selected = saved[choice - 1]
        shutil.copyfile(selected, Path("council.yaml"))
        council = load_council_file("council.yaml")
        save_council_file(council, "council.yaml")
        console.print(f"[bold #6ABF9F]Loaded team:[/bold #6ABF9F] {selected.stem}")
    else:
        roster = templates[choice - len(saved) - 1]
        council = load_council_file("council.yaml") if Path("council.yaml").exists() else CouncilFile()
        council.agents = roster.agents
        council.template.name = roster.name
        council.template.tags = roster.tags
        save_council_file(council, "council.yaml")
        console.print(f"[bold #6ABF9F]Loaded template:[/bold #6ABF9F] {roster.name}")


@app.command("import")
def import_council(url: str = typer.Argument(..., help="GitHub URL to a shared council file")) -> None:
    """Import a shared Council file from GitHub."""
    raw_url = _raw_github_url(url)
    response = httpx.get(raw_url, timeout=20.0)
    response.raise_for_status()
    Path("council.yaml").write_text(response.text, encoding="utf-8")
    _ = load_council_file("council.yaml")
    console.print("[bold #6ABF9F]Imported council.yaml[/bold #6ABF9F]")


@app.command("reset")
def reset(force: bool = typer.Option(False, "--force", help="Skip confirmation")) -> None:
    """Wipe the current Council file."""
    config = _require_config()
    if force or typer.confirm("Delete the current council.yaml?"):
        config.unlink(missing_ok=True)
        console.print("[bold red]Council reset.[/bold red] Run [bold]council init[/bold] to begin again.")

from __future__ import annotations

import shutil
import webbrowser
from pathlib import Path

import httpx
import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from council.context import ContextBuilder
from council.env_utils import load_council_env
from council.models import CouncilFile, cache_dir, load_council_file, save_council_file, teams_dir
from council.wizard import load_template_rosters
from council.orchestrator import CouncilAI
from council.server import create_app
from council.tui import print_startup_summary, run_tui
from council.wizard import add_agent_to_existing, run_init_wizard, run_model_wizard

app = typer.Typer(help="Council: a local meeting room for AI advisors.", no_args_is_help=True)
console = Console()


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


@app.command()
def init() -> None:
    """Interactive wizard that creates council.yaml and .env."""
    run_init_wizard()


@app.command("start")
def start_server(
    web: bool = typer.Option(False, "--web", help="Launch the optional web room instead of the terminal UI"),
    host: str = typer.Option("127.0.0.1", help="Host to bind for web mode"),
    port: int = typer.Option(4000, help="Port to bind for web mode"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open the browser automatically in web mode"),
) -> None:
    """Launch the meeting room in the terminal by default."""
    load_council_env(Path.cwd())
    config_path = _require_config()

    with console.status("[#8B8680]Loading config...[/#8B8680]", spinner="dots") as status:
        council = load_council_file(config_path)
        ai = CouncilAI(council)

        status.update("[#8B8680]Scanning project context...[/#8B8680]")
        context_result = ContextBuilder(
            council,
            Path.cwd(),
            summarizer=ai.summarize_file,
            on_progress=lambda msg: status.update(f"[#8B8680]{msg}[/#8B8680]"),
        ).build()

        status.update("[#8B8680]Checking connection...[/#8B8680]")
        api_status = ai.ping()

    if web:
        print_startup_summary(council, context_result, mode="Web", api_status=api_status)
        console.print(f"Opening http://{host}:{port}")
        if open_browser:
            webbrowser.open(f"http://{host}:{port}")
        app_instance = create_app(council, context_result)
        uvicorn.run(app_instance, host=host, port=port, log_level="warning")
        return

    run_tui(council, context_result, api_status=api_status)


@app.command("add-agent")
def add_agent() -> None:
    """Add a new advisor to the current Council file."""
    _require_config()
    council = add_agent_to_existing()
    console.print(f"[bold #6ABF9F]Added agent.[/bold #6ABF9F] Team now has {len(council.agents)} advisors.")


@app.command("model")
def set_model(
    model_name: str | None = typer.Argument(None, help="Model name to apply to all agents immediately"),
) -> None:
    """Switch AI models for your advisors without re-running init."""
    load_council_env(Path.cwd())
    _require_config()
    run_model_wizard(quick_model=model_name)


@app.command()
def list() -> None:
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


context_app = typer.Typer(help="Manage project context sources.", no_args_is_help=False)
app.add_typer(context_app, name="context")


@context_app.callback(invoke_without_command=True)
def show_context(ctx: typer.Context) -> None:
    """Show included files, scanned dirs, and ignore patterns. Sub-commands: add, remove, ignore, clear-cache."""
    if ctx.invoked_subcommand is not None:
        return
    load_council_env(Path.cwd())
    config_path = _require_config()
    council = load_council_file(config_path)

    with console.status("[#8B8680]Scanning project context...[/#8B8680]", spinner="dots") as status:
        result = ContextBuilder(
            council,
            Path.cwd(),
            on_progress=lambda msg: status.update(f"[#8B8680]{msg}[/#8B8680]"),
        ).build()

    dirs = council.context.directories or ["."]
    console.print(f"\n[bold #C9A227]Scanned directories:[/bold #C9A227] {', '.join(dirs)}")
    if council.context.files:
        console.print(f"[bold #C9A227]Extra files:[/bold #C9A227] {', '.join(council.context.files)}")
    if council.context.ignore:
        console.print(f"[dim]Ignored patterns:[/dim] {', '.join(council.context.ignore)}")
    console.print(f"[dim]Cache:[/dim] {result.cache_status}\n")

    if result.included_files:
        table = Table(title="Included Files", header_style="bold #6ABF9F", show_lines=False)
        table.add_column("File")
        table.add_column("Note", style="dim")
        for f in result.included_files:
            note = "summarized" if f in result.summarized_files else ""
            table.add_row(f, note)
        console.print(table)

    if result.dropped_files:
        console.print(f"\n[dim]Dropped (over token budget):[/dim]")
        for f in result.dropped_files:
            console.print(f"  [dim]- {f}[/dim]")

    console.print(f"\n[dim]Estimated tokens:[/dim] {result.tokens_estimated} / {council.context.max_tokens}")
    console.print("[dim]Sub-commands: council context add <path>  |  remove <path>  |  ignore <pattern>  |  clear-cache[/dim]")


@context_app.command("add")
def context_add(
    path: str = typer.Argument(..., help="Directory or file path to add to context"),
) -> None:
    """Add a directory or file to the project context."""
    config_path = _require_config()
    council = load_council_file(config_path)
    resolved = Path(path)
    if resolved.is_dir() or not resolved.suffix:
        if path in council.context.directories:
            console.print(f"[dim]{path} is already in context directories.[/dim]")
            raise typer.Exit()
        council.context.directories.append(path)
        save_council_file(council, config_path)
        console.print(f"[bold #6ABF9F]Added directory:[/bold #6ABF9F] {path}")
    else:
        if path in council.context.files:
            console.print(f"[dim]{path} is already in context files.[/dim]")
            raise typer.Exit()
        council.context.files.append(path)
        save_council_file(council, config_path)
        console.print(f"[bold #6ABF9F]Added file:[/bold #6ABF9F] {path}")


@context_app.command("remove")
def context_remove(
    path: str = typer.Argument(..., help="Directory or file path to remove from context"),
) -> None:
    """Remove a directory or file from the project context."""
    config_path = _require_config()
    council = load_council_file(config_path)
    removed = False
    if path in council.context.directories:
        council.context.directories.remove(path)
        removed = True
    if path in council.context.files:
        council.context.files.remove(path)
        removed = True
    if removed:
        save_council_file(council, config_path)
        console.print(f"[bold red]Removed from context:[/bold red] {path}")
    else:
        console.print(f"[dim]{path} not found in context directories or files.[/dim]")


@context_app.command("ignore")
def context_ignore(
    pattern: str = typer.Argument(..., help="Glob pattern to ignore (e.g. 'tests/' or '*.lock')"),
    remove: bool = typer.Option(False, "--remove", help="Remove this pattern instead of adding it"),
) -> None:
    """Add or remove a glob ignore pattern."""
    config_path = _require_config()
    council = load_council_file(config_path)
    if remove:
        if pattern not in council.context.ignore:
            console.print(f"[dim]{pattern} is not in the ignore list.[/dim]")
            raise typer.Exit()
        council.context.ignore.remove(pattern)
        save_council_file(council, config_path)
        console.print(f"[bold #6ABF9F]Removed ignore pattern:[/bold #6ABF9F] {pattern}")
    else:
        if pattern in council.context.ignore:
            console.print(f"[dim]{pattern} is already ignored.[/dim]")
            raise typer.Exit()
        council.context.ignore.append(pattern)
        save_council_file(council, config_path)
        console.print(f"[bold #6ABF9F]Added ignore pattern:[/bold #6ABF9F] {pattern}")


@context_app.command("clear-cache")
def context_clear_cache() -> None:
    """Delete the context cache, forcing a full re-scan on next start."""
    shutil.rmtree(cache_dir(), ignore_errors=True)
    cache_dir()  # recreate empty
    console.print("[bold #6ABF9F]Context cache cleared.[/bold #6ABF9F] Next [bold]council start[/bold] will re-scan.")


@app.command("import")
def import_council(url: str = typer.Argument(..., help="GitHub URL to a shared council file")) -> None:
    """Import a shared Council file from GitHub."""
    raw_url = _raw_github_url(url)
    response = httpx.get(raw_url, timeout=20.0)
    response.raise_for_status()
    Path("council.yaml").write_text(response.text, encoding="utf-8")
    _ = load_council_file("council.yaml")
    console.print("[bold #6ABF9F]Imported council.yaml[/bold #6ABF9F]")


@app.command()
def reset(force: bool = typer.Option(False, "--force", help="Skip confirmation")) -> None:
    """Wipe the current Council file."""
    config = _require_config()
    if force or typer.confirm("Delete the current council.yaml?"):
        config.unlink(missing_ok=True)
        console.print("[bold red]Council reset.[/bold red] Run [bold]council init[/bold] to begin again.")


@app.command()
def teams() -> None:
    """List saved teams in ~/.council/teams."""
    directory = teams_dir()
    entries = sorted(directory.glob("*.yaml"))
    if not entries:
        console.print("No saved teams yet.")
        return
    for item in entries:
        console.print(f"- {item.stem}")


@app.command()
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


@app.command()
def save(name: str = typer.Argument(..., help="Team name")) -> None:
    """Save the current Council file as a named team."""
    config = _require_config()
    destination = teams_dir() / f"{name}.yaml"
    shutil.copyfile(config, destination)
    console.print(f"[bold #6ABF9F]Saved team:[/bold #6ABF9F] {name}")


@app.command()
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


@app.command()
def delete(name: str = typer.Argument(..., help="Saved team name")) -> None:
    """Remove a saved team."""
    target = teams_dir() / f"{name}.yaml"
    if not target.exists():
        console.print(f"[bold red]Unknown team:[/bold red] {name}")
        raise typer.Exit(1)
    target.unlink()
    console.print(f"[bold red]Deleted team:[/bold red] {name}")


if __name__ == "__main__":
    app()

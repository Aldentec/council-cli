from __future__ import annotations

import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from council.infrastructure.config.env import load_council_env
from council.infrastructure.config.loader import load_council_file, save_council_file
from council.infrastructure.context.builder import ContextBuilder
from council.infrastructure.teams.store import cache_dir

console = Console()
app = typer.Typer(help="Manage project context sources.", no_args_is_help=False)


def _require_config(path: str | Path = "council.yaml") -> Path:
    config = Path(path)
    if not config.exists():
        console.print("[bold red]No council.yaml found.[/bold red] Run [bold]council init[/bold] first.")
        raise typer.Exit(1)
    return config


@app.callback(invoke_without_command=True)
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
    console.print(
        "[dim]Sub-commands: council context add <path>  |  remove <path>  |  ignore <pattern>  |  clear-cache[/dim]"
    )


@app.command("add")
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


@app.command("remove")
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


@app.command("ignore")
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


@app.command("clear-cache")
def context_clear_cache() -> None:
    """Delete the context cache, forcing a full re-scan on next start."""
    shutil.rmtree(cache_dir(), ignore_errors=True)
    cache_dir()
    console.print("[bold #6ABF9F]Context cache cleared.[/bold #6ABF9F] Next [bold]council start[/bold] will re-scan.")

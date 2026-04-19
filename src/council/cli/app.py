from __future__ import annotations

import typer

from council.cli.commands import context as context_cmd
from council.cli.commands.agent import add_agent, list_agents
from council.cli.commands.init import init
from council.cli.commands.model import set_model
from council.cli.commands.start import start_server
from council.cli.commands.teams import (
    delete,
    import_council,
    list_teams,
    reset,
    save,
    switch,
    use,
)

app = typer.Typer(help="Council: a local meeting room for AI advisors.", no_args_is_help=True)

app.command("init")(init)
app.command("start")(start_server)
app.command("add-agent")(add_agent)
app.command("list")(list_agents)
app.command("model")(set_model)
app.command("teams")(list_teams)
app.command("save")(save)
app.command("use")(use)
app.command("delete")(delete)
app.command("switch")(switch)
app.command("import")(import_council)
app.command("reset")(reset)
app.add_typer(context_cmd.app, name="context")

if __name__ == "__main__":
    app()

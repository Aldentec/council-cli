from typer.testing import CliRunner

from council.cli import app

runner = CliRunner()


def test_start_help_shows_tui_first():
    result = runner.invoke(app, ["start", "--help"])

    assert result.exit_code == 0
    assert "--web" in result.stdout
    assert "terminal" in result.stdout.lower() or "tui" in result.stdout.lower()

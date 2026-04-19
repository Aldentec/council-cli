from pathlib import Path

from typer.testing import CliRunner

from council.cli import app
from council.domain.models.agent import AgentConfig
from council.domain.models.config import CouncilFile, ProjectConfig
from council.infrastructure.config.loader import save_council_file

runner = CliRunner()


def _sample_council() -> CouncilFile:
    return CouncilFile(
        project=ProjectConfig(name="Council Test", description="CLI flow"),
        agents=[
            AgentConfig(
                name="Alex",
                role="CEO",
                persona="Direct and strategic",
                system_prompt="You are Alex.",
                model="claude-sonnet-4-6",
                color="#C9A227",
            )
        ],
    )


def test_list_command(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    save_council_file(_sample_council(), tmp_path / "council.yaml")

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "Council Test" in result.stdout
    assert "Alex" in result.stdout


def test_team_save_use_delete_flow(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    save_council_file(_sample_council(), tmp_path / "council.yaml")

    save_result = runner.invoke(app, ["save", "demo-team"])
    use_result = runner.invoke(app, ["use", "demo-team"])
    delete_result = runner.invoke(app, ["delete", "demo-team"])

    assert save_result.exit_code == 0
    assert use_result.exit_code == 0
    assert delete_result.exit_code == 0

from typer.testing import CliRunner

from app.chao import cli


def test_repositories_list_outputs_configured_repositories():
    result = CliRunner().invoke(cli.app, ["repositories-list", "--json"])

    assert result.exit_code == 0
    assert "chao-platform" in result.output
    assert "git@github.com:bruceli0305/chao-platform.git" in result.output
    assert "codex/" in result.output


def test_repository_show_outputs_default_repository():
    result = CliRunner().invoke(cli.app, ["repository-show"])

    assert result.exit_code == 0
    assert '"name": "chao-platform"' in result.output
    assert '"default_branch": "main"' in result.output


def test_repository_show_rejects_unknown_repository():
    result = CliRunner().invoke(cli.app, ["repository-show", "missing"])

    assert result.exit_code == 1
    assert "unsupported repository: missing" in result.output


def test_repositories_validate_passes_default_config():
    result = CliRunner().invoke(cli.app, ["repositories-validate", "--json"])

    assert result.exit_code == 0
    assert '"status": "success"' in result.output
    assert '"errors": []' in result.output

from typer.testing import CliRunner

from app.chao import cli


def test_agents_list_outputs_registry():
    result = CliRunner().invoke(cli.app, ["agents-list", "--json"])

    assert result.exit_code == 0
    assert '"name": "gongbu"' in result.output
    assert '"branch": "six-ministries"' in result.output
    assert '"required_for_self_upgrade": true' in result.output


def test_agents_validate_passes_for_committed_registry():
    result = CliRunner().invoke(cli.app, ["agents-validate", "--json"])

    assert result.exit_code == 0
    assert '"status": "success"' in result.output
    assert '"errors": []' in result.output

from typer.testing import CliRunner

from app.chao import cli


def test_skills_list_outputs_manifest_registry():
    result = CliRunner().invoke(cli.app, ["skills-list", "--json"])

    assert result.exit_code == 0
    assert "bugfix" in result.output
    assert ".ai-agents/skills/bugfix/SKILL.md" in result.output
    assert "gongbu" in result.output
    assert "manual_validation" in result.output


def test_skills_validate_passes_for_committed_manifests():
    result = CliRunner().invoke(cli.app, ["skills-validate", "--json"])

    assert result.exit_code == 0
    assert '"status": "success"' in result.output
    assert '"errors": []' in result.output

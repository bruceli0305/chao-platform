from typer.testing import CliRunner

from app.chao import cli


def test_llm_provider_doctor_reports_missing_key_without_exposing_secret(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    result = CliRunner().invoke(cli.app, ["llm-provider-doctor"])

    assert result.exit_code == 0
    assert '"status": "missing_api_key"' in result.output
    assert '"api_key_env": "DEEPSEEK_API_KEY"' in result.output
    assert "api_key_set" in result.output


def test_llm_provider_doctor_can_require_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    result = CliRunner().invoke(cli.app, ["llm-provider-doctor", "--require-key"])

    assert result.exit_code == 1
    assert '"status": "missing_api_key"' in result.output


def test_llm_provider_doctor_detects_key_without_printing_it(monkeypatch):
    secret_value = "test" + "-deepseek" + "-key"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret_value)

    result = CliRunner().invoke(cli.app, ["llm-provider-doctor"])

    assert result.exit_code == 0
    assert '"status": "configured"' in result.output
    assert secret_value not in result.output

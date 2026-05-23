from typer.testing import CliRunner

from app.chao import cli


def test_doctor_outputs_json_and_exits_zero_when_ready(monkeypatch):
    monkeypatch.setattr(
        cli,
        "run_chao_doctor",
        lambda: {
            "status": "ready",
            "ready": True,
            "checks": [
                {
                    "name": "command:uv",
                    "ready": True,
                    "severity": "required",
                    "summary": "uv is available",
                    "details": {},
                }
            ],
        },
    )

    result = CliRunner().invoke(cli.app, ["doctor", "--json"])

    assert result.exit_code == 0
    assert '"status": "ready"' in result.output
    assert '"command:uv"' in result.output


def test_doctor_exits_nonzero_when_blocked(monkeypatch):
    monkeypatch.setattr(
        cli,
        "run_chao_doctor",
        lambda: {
            "status": "blocked",
            "ready": False,
            "checks": [
                {
                    "name": "database:schema",
                    "ready": False,
                    "severity": "required",
                    "summary": "schema check failed",
                    "details": {},
                }
            ],
        },
    )

    result = CliRunner().invoke(cli.app, ["doctor"])

    assert result.exit_code == 1
    assert "Chao First-Run Doctor" in result.output
    assert "schema check failed" in result.output

from typer.testing import CliRunner

from app.chao import cli


def _task(*, artifacts=None):
    return {
        "id": "task-1",
        "task_code": "TASK-1",
        "title": "Governed task",
        "task_level": "L3",
        "status": "DESIGNING",
        "route_result": {"required_confirmation": "A"},
        "artifacts": artifacts or [],
    }


def test_governance_check_records_success(monkeypatch):
    calls = {"events": [], "tool_calls": []}
    monkeypatch.setattr(
        cli,
        "get_task_detail",
        lambda _task_code: _task(
            artifacts=[{"artifact_type": "l3_design_plan", "artifact_uri": "design.md"}]
        ),
    )
    monkeypatch.setattr(
        cli,
        "record_task_event",
        lambda **kwargs: calls["events"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "record_tool_call",
        lambda **kwargs: calls["tool_calls"].append(kwargs),
    )

    result = CliRunner().invoke(
        cli.app,
        ["governance-check", "TASK-1", "--agent", "menxia", "--json"],
    )

    assert result.exit_code == 0
    assert '"status": "passed"' in result.output
    assert calls["events"][0]["event_type"] == "menxia_governance_passed"
    assert calls["tool_calls"][0]["tool_name"] == "cli.governance_check"
    assert calls["tool_calls"][0]["result_status"] == "success"


def test_governance_check_exits_nonzero_when_blocked(monkeypatch):
    calls = {"events": [], "tool_calls": []}
    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: _task())
    monkeypatch.setattr(
        cli,
        "record_task_event",
        lambda **kwargs: calls["events"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "record_tool_call",
        lambda **kwargs: calls["tool_calls"].append(kwargs),
    )

    result = CliRunner().invoke(
        cli.app,
        ["governance-check", "TASK-1", "--agent", "hubu", "--json"],
    )

    assert result.exit_code == 1
    assert '"status": "blocked"' in result.output
    assert "l3_design_plan" in result.output
    assert calls["events"][0]["event_type"] == "hubu_governance_blocked"
    assert calls["tool_calls"][0]["result_status"] == "blocked"

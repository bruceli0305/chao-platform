from typer.testing import CliRunner

from app.chao import cli


def test_runner_validate_records_success(monkeypatch):
    calls = {
        "events": [],
        "tool_calls": [],
    }
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "task_level": "L1",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "none"},
    }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(
        cli,
        "execute_runner_validation_commands",
        lambda gates, timeout_seconds=120: {
            "quality": "deliverable",
            "checks": gates,
            "plan": [],
            "command_results": [],
            "deliverable": True,
            "note": "passed",
        },
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
        [
            "runner-validate",
            "TASK-1",
            "--gate",
            "compile",
            "--timeout",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert calls["events"][0]["event_type"] == "runner_validation_passed"
    assert calls["tool_calls"][0]["tool_name"] == "cli.runner_validate"
    assert calls["tool_calls"][0]["permission_policy"] == "controlled-runner-validation"
    assert calls["tool_calls"][0]["result_status"] == "success"


def test_runner_validate_exits_nonzero_for_failed_validation(monkeypatch):
    calls = {
        "events": [],
        "tool_calls": [],
    }
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "task_level": "L1",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "none"},
    }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(
        cli,
        "execute_runner_validation_commands",
        lambda gates, timeout_seconds=120: {
            "quality": "failed",
            "checks": gates,
            "plan": [],
            "command_results": [
                {
                    "gate": "manual_validation",
                    "command": "manual validation evidence required",
                    "status": "failed",
                    "exit_code": 1,
                    "output_summary": "manual gate",
                }
            ],
            "deliverable": False,
            "note": "failed",
        },
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
        [
            "runner-validate",
            "TASK-1",
            "--gate",
            "manual_validation",
        ],
    )

    assert result.exit_code == 1
    assert calls["events"][0]["event_type"] == "runner_validation_failed"
    assert calls["tool_calls"][0]["result_status"] == "failed"

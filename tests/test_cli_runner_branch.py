from typer.testing import CliRunner

from app.chao import cli


def test_runner_branch_dry_run_records_event_and_tool_call(monkeypatch):
    calls = {
        "events": [],
        "tool_calls": [],
    }
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "title": "Patch demo",
        "task_level": "L2",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "B"},
    }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(
        cli,
        "create_runner_branch",
        lambda branch_plan, dry_run=True: {
            "branch_required": True,
            "branch_name": branch_plan["branch_name"],
            "base_ref": branch_plan["base_ref"],
            "create_command": branch_plan["create_command"],
            "current_branch": "main",
            "branch_exists": False,
            "created": False,
            "dry_run": dry_run,
            "errors": [],
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

    result = CliRunner().invoke(cli.app, ["runner-branch", "TASK-1", "--base-ref", "main"])

    assert result.exit_code == 0
    assert calls["events"][0]["event_type"] == "runner_branch_dry_run"
    assert calls["tool_calls"][0]["tool_name"] == "cli.runner_branch"
    assert calls["tool_calls"][0]["permission_policy"] == "controlled-runner-branch"
    assert '"created": false' in result.output


def test_runner_branch_apply_records_created_event(monkeypatch):
    calls = {
        "events": [],
        "tool_calls": [],
    }
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "title": "Patch demo",
        "task_level": "L2",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "B"},
    }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)

    def fake_create_runner_branch(branch_plan, dry_run=True):
        assert dry_run is False
        return {
            "branch_required": True,
            "branch_name": branch_plan["branch_name"],
            "base_ref": branch_plan["base_ref"],
            "create_command": branch_plan["create_command"],
            "current_branch": "main",
            "branch_exists": False,
            "created": True,
            "dry_run": False,
            "errors": [],
        }

    monkeypatch.setattr(cli, "create_runner_branch", fake_create_runner_branch)
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

    result = CliRunner().invoke(cli.app, ["runner-branch", "TASK-1", "--apply"])

    assert result.exit_code == 0
    assert calls["events"][0]["event_type"] == "runner_branch_created"
    assert calls["tool_calls"][0]["result_status"] == "success"
    assert '"created": true' in result.output

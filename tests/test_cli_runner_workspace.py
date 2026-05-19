from typer.testing import CliRunner

from app.chao import cli


def test_runner_workspace_dry_run_records_event_and_tool_call(monkeypatch):
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
        "create_runner_workspace",
        lambda workspace_plan, dry_run=True: {
            "workspace_required": True,
            "workspace_path": workspace_plan["workspace_path"],
            "branch_name": workspace_plan["branch_name"],
            "base_ref": workspace_plan["base_ref"],
            "create_command": workspace_plan["create_command"],
            "workspace_exists": False,
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

    result = CliRunner().invoke(cli.app, ["runner-workspace", "TASK-1", "--base-ref", "main"])

    assert result.exit_code == 0
    assert calls["events"][0]["event_type"] == "runner_workspace_dry_run"
    assert calls["tool_calls"][0]["tool_name"] == "cli.runner_workspace"
    assert calls["tool_calls"][0]["permission_policy"] == "controlled-runner-workspace"
    assert '"created": false' in result.output


def test_runner_workspace_apply_records_created_event(monkeypatch):
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

    def fake_create_runner_workspace(workspace_plan, dry_run=True):
        assert dry_run is False
        return {
            "workspace_required": True,
            "workspace_path": workspace_plan["workspace_path"],
            "branch_name": workspace_plan["branch_name"],
            "base_ref": workspace_plan["base_ref"],
            "create_command": workspace_plan["create_command"],
            "workspace_exists": False,
            "branch_exists": False,
            "created": True,
            "dry_run": False,
            "errors": [],
        }

    monkeypatch.setattr(cli, "create_runner_workspace", fake_create_runner_workspace)
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

    result = CliRunner().invoke(cli.app, ["runner-workspace", "TASK-1", "--apply"])

    assert result.exit_code == 0
    assert calls["events"][0]["event_type"] == "runner_workspace_created"
    assert calls["tool_calls"][0]["result_status"] == "success"
    assert '"created": true' in result.output

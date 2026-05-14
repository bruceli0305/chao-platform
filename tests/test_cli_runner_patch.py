from typer.testing import CliRunner

from app.chao import cli


def test_runner_patch_dry_run_records_event_and_tool_call(monkeypatch):
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
        "apply_text_patch_operations",
        lambda operations, dry_run=True: {
            "summary": "Validated 1 controlled text patch operation(s).",
            "changed_files": [operations[0]["path"]],
            "operations": [],
            "applied": not dry_run,
            "dry_run": dry_run,
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
            "runner-patch",
            "TASK-1",
            "app/chao/demo.txt",
            "--old-text",
            "old",
            "--new-text",
            "new",
        ],
    )

    assert result.exit_code == 0
    assert calls["events"][0]["event_type"] == "runner_patch_dry_run"
    assert calls["tool_calls"][0]["tool_name"] == "cli.runner_patch"
    assert calls["tool_calls"][0]["permission_policy"] == "controlled-runner-text-patch"
    assert '"applied": false' in result.output


def test_runner_patch_apply_records_apply_event(monkeypatch):
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

    def fake_apply_text_patch_operations(operations, dry_run=True):
        assert dry_run is False
        return {
            "summary": "Applied 1 controlled text patch operation(s).",
            "changed_files": [operations[0]["path"]],
            "operations": [],
            "applied": True,
            "dry_run": False,
        }

    monkeypatch.setattr(cli, "apply_text_patch_operations", fake_apply_text_patch_operations)
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
            "runner-patch",
            "TASK-1",
            "app/chao/demo.txt",
            "--old-text",
            "old",
            "--new-text",
            "new",
            "--apply",
        ],
    )

    assert result.exit_code == 0
    assert calls["events"][0]["event_type"] == "runner_patch_applied"
    assert calls["tool_calls"][0]["result_status"] == "success"
    assert '"applied": true' in result.output


def test_runner_patch_rejects_l4_task(monkeypatch):
    monkeypatch.setattr(
        cli,
        "get_task_detail",
        lambda _task_code: {
            "id": "task-1",
            "task_code": "TASK-1",
            "task_level": "L4",
            "status": "MILESTONE_PLANNING",
            "route_result": {"required_confirmation": "A"},
        },
    )

    result = CliRunner().invoke(
        cli.app,
        [
            "runner-patch",
            "TASK-1",
            "app/chao/demo.txt",
            "--old-text",
            "old",
            "--new-text",
            "new",
        ],
    )

    assert result.exit_code == 1
    assert "L4 tasks cannot execute runner patches" in result.output

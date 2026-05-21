from typer.testing import CliRunner

from app.chao import cli
from app.chao.repositories import RepositoryConfig


def _repository_config(
    *,
    name: str = "chao-platform",
    workspace_path: str = ".",
):
    return RepositoryConfig(
        name=name,
        git_url="git@github.com:example/repo.git",
        default_branch="main",
        workspace_path=workspace_path,
        sandbox_root=".chao/sandboxes",
        branch_prefix="codex/",
        enabled=True,
    )


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
    monkeypatch.setattr(cli, "get_repository_config", lambda _name=None: _repository_config())
    monkeypatch.setattr(
        cli,
        "apply_text_patch_operations",
        lambda operations, dry_run=True, **_kwargs: {
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
    assert "repository=chao-platform" in calls["tool_calls"][0]["arguments_summary"]
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
    monkeypatch.setattr(cli, "get_repository_config", lambda _name=None: _repository_config())

    def fake_apply_text_patch_operations(operations, dry_run=True, **_kwargs):
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


def test_runner_patch_uses_explicit_repository_config(monkeypatch):
    calls = {
        "events": [],
        "tool_calls": [],
        "patch_kwargs": None,
    }
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "task_level": "L1",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "none"},
    }
    repository = _repository_config(
        name="server-repo",
        workspace_path="/opt/chao/workspaces/server-repo",
    )

    def fake_apply_text_patch_operations(operations, **kwargs):
        calls["patch_kwargs"] = kwargs
        return {
            "summary": "Validated 1 controlled text patch operation(s).",
            "changed_files": [operations[0]["path"]],
            "operations": [],
            "applied": False,
            "dry_run": kwargs["dry_run"],
        }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(cli, "get_repository_config", lambda _name=None: repository)
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
            "--repository",
            "server-repo",
        ],
    )

    assert result.exit_code == 0
    assert calls["patch_kwargs"]["repo_root"] == "/opt/chao/workspaces/server-repo"
    assert "repository=server-repo" in calls["tool_calls"][0]["arguments_summary"]
    assert '"name": "server-repo"' in result.output

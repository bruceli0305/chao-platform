import pytest
from typer.testing import CliRunner

from app.chao import cli
from app.chao.repositories import RepositoryConfig


def _repository_config(
    *,
    name: str = "chao-platform",
    default_branch: str = "main",
    workspace_path: str = ".",
    sandbox_root: str = ".chao/sandboxes",
    branch_prefix: str = "codex/",
):
    return RepositoryConfig(
        name=name,
        git_url="git@github.com:example/repo.git",
        default_branch=default_branch,
        workspace_path=workspace_path,
        sandbox_root=sandbox_root,
        branch_prefix=branch_prefix,
        enabled=True,
    )


@pytest.fixture(autouse=True)
def allow_runner_preflight(monkeypatch):
    monkeypatch.setattr(
        cli,
        "_require_runner_repository_preflight",
        lambda *_args, **_kwargs: None,
    )


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
    monkeypatch.setattr(cli, "get_repository_config", lambda _name=None: _repository_config())
    monkeypatch.setattr(
        cli,
        "create_runner_branch",
        lambda branch_plan, dry_run=True, **_kwargs: {
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
    assert "repository=chao-platform" in calls["tool_calls"][0]["arguments_summary"]
    assert "base_ref=main" in calls["tool_calls"][0]["arguments_summary"]
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
    monkeypatch.setattr(cli, "get_repository_config", lambda _name=None: _repository_config())

    def fake_create_runner_branch(branch_plan, dry_run=True, **_kwargs):
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


def test_runner_branch_uses_explicit_repository_config(monkeypatch):
    calls = {
        "branch_plan": None,
        "branch_kwargs": None,
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
    repository = _repository_config(
        name="server-repo",
        default_branch="origin/main",
        workspace_path="/opt/chao/workspaces/server-repo",
        branch_prefix="server/",
    )

    def fake_create_runner_branch(branch_plan, **kwargs):
        calls["branch_plan"] = branch_plan
        calls["branch_kwargs"] = kwargs
        return {
            "branch_required": True,
            "branch_name": branch_plan["branch_name"],
            "base_ref": branch_plan["base_ref"],
            "create_command": branch_plan["create_command"],
            "current_branch": "main",
            "branch_exists": False,
            "created": False,
            "dry_run": kwargs["dry_run"],
            "errors": [],
        }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(cli, "get_repository_config", lambda name=None: repository)
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

    result = CliRunner().invoke(
        cli.app,
        ["runner-branch", "TASK-1", "--repository", "server-repo"],
    )

    assert result.exit_code == 0
    assert calls["branch_plan"]["base_ref"] == "origin/main"
    assert calls["branch_plan"]["branch_name"].startswith("server/")
    assert calls["branch_kwargs"]["repo_root"] == "/opt/chao/workspaces/server-repo"
    assert "repository=server-repo" in calls["tool_calls"][0]["arguments_summary"]

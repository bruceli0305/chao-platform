from dataclasses import dataclass

import pytest

from app.chao.runner_policy import build_runner_workspace_plan
from app.chao.runner_workspace import create_runner_workspace, inspect_runner_workspace


@dataclass
class FakeCompletedProcess:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def test_inspect_runner_workspace_reports_dry_run_plan(tmp_path):
    commands = []
    plan = build_runner_workspace_plan(
        task_code="TASK-20260511-191300-226866",
        title="Patch demo",
        task_level="L2",
        base_ref="main",
    )

    def fake_runner(command, **_kwargs):
        commands.append(command)
        if command[:3] == ["git", "show-ref", "--verify"]:
            return FakeCompletedProcess(returncode=1)
        raise AssertionError(command)

    result = inspect_runner_workspace(plan, repo_root=tmp_path, command_runner=fake_runner)

    assert result["workspace_required"] is True
    expected_workspace_path = ".chao/sandboxes/codex-task-20260511-191300-226866-patch-demo"
    assert result["workspace_path"] == expected_workspace_path
    assert result["branch_name"] == "codex/task-20260511-191300-226866-patch-demo"
    assert result["workspace_exists"] is False
    assert result["branch_exists"] is False
    assert result["created"] is False
    assert result["dry_run"] is True
    assert result["errors"] == []
    assert commands == [
        [
            "git",
            "show-ref",
            "--verify",
            "--quiet",
            "refs/heads/codex/task-20260511-191300-226866-patch-demo",
        ],
    ]


def test_create_runner_workspace_runs_git_worktree_command_when_apply_enabled(tmp_path):
    commands = []
    plan = build_runner_workspace_plan(
        task_code="TASK-20260511-191300-226866",
        title="Patch demo",
        task_level="L2",
        base_ref="main",
    )

    def fake_runner(command, **_kwargs):
        commands.append(command)
        if command[:3] == ["git", "show-ref", "--verify"]:
            return FakeCompletedProcess(returncode=1)
        if command == plan["create_command"]:
            return FakeCompletedProcess(returncode=0)
        raise AssertionError(command)

    result = create_runner_workspace(
        plan,
        repo_root=tmp_path,
        dry_run=False,
        command_runner=fake_runner,
    )

    assert result["created"] is True
    assert result["dry_run"] is False
    assert commands[-1] == plan["create_command"]


def test_create_runner_workspace_rejects_existing_workspace(tmp_path):
    plan = build_runner_workspace_plan(
        task_code="TASK-20260511-191300-226866",
        title="Patch demo",
        task_level="L2",
        base_ref="main",
    )
    workspace = tmp_path / ".chao" / "sandboxes" / "codex-task-20260511-191300-226866-patch-demo"
    workspace.mkdir(parents=True)

    def fake_runner(command, **_kwargs):
        if command[:3] == ["git", "show-ref", "--verify"]:
            return FakeCompletedProcess(returncode=1)
        raise AssertionError(command)

    with pytest.raises(ValueError, match="Runner workspace already exists"):
        create_runner_workspace(
            plan,
            repo_root=tmp_path,
            dry_run=False,
            command_runner=fake_runner,
        )


def test_create_runner_workspace_allows_configured_external_sandbox_root(tmp_path):
    repo_root = tmp_path / "repo"
    sandbox_root = tmp_path / "sandboxes"
    repo_root.mkdir()
    sandbox_root.mkdir()
    plan = {
        "workspace_required": True,
        "workspace_path": str(sandbox_root / "codex-task-demo"),
        "branch_name": "codex/task-demo",
        "base_ref": "main",
        "create_command": [
            "git",
            "worktree",
            "add",
            "-b",
            "codex/task-demo",
            str(sandbox_root / "codex-task-demo"),
            "main",
        ],
        "reason": "test",
    }

    def fake_runner(command, **_kwargs):
        if command[:3] == ["git", "show-ref", "--verify"]:
            return FakeCompletedProcess(returncode=1)
        raise AssertionError(command)

    result = create_runner_workspace(
        plan,
        repo_root=repo_root,
        allowed_workspace_root=sandbox_root,
        dry_run=True,
        command_runner=fake_runner,
    )

    assert result["errors"] == []
    assert result["workspace_exists"] is False


def test_create_runner_workspace_skips_l4_plan(tmp_path):
    plan = build_runner_workspace_plan(
        task_code="TASK-20260511-191300-226866",
        title="Roadmap",
        task_level="L4",
        base_ref="main",
    )

    def fake_runner(command, **_kwargs):
        raise AssertionError(command)

    result = create_runner_workspace(
        plan,
        repo_root=tmp_path,
        dry_run=False,
        command_runner=fake_runner,
    )

    assert result["workspace_required"] is False
    assert result["created"] is False

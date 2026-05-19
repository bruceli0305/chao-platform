from dataclasses import dataclass

import pytest

from app.chao.runner_branch import create_runner_branch, inspect_runner_branch
from app.chao.runner_policy import build_runner_branch_plan


@dataclass
class FakeCompletedProcess:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def test_inspect_runner_branch_reports_dry_run_plan():
    commands = []
    plan = build_runner_branch_plan(
        task_code="TASK-20260511-191300-226866",
        title="Patch demo",
        task_level="L2",
        base_ref="main",
    )

    def fake_runner(command, **_kwargs):
        commands.append(command)
        if command == ["git", "branch", "--show-current"]:
            return FakeCompletedProcess(returncode=0, stdout="main\n")
        if command[:3] == ["git", "show-ref", "--verify"]:
            return FakeCompletedProcess(returncode=1)
        raise AssertionError(command)

    result = inspect_runner_branch(plan, command_runner=fake_runner)

    assert result["branch_required"] is True
    assert result["branch_name"] == "codex/task-20260511-191300-226866-patch-demo"
    assert result["current_branch"] == "main"
    assert result["branch_exists"] is False
    assert result["created"] is False
    assert result["dry_run"] is True
    assert result["errors"] == []
    assert commands == [
        ["git", "branch", "--show-current"],
        [
            "git",
            "show-ref",
            "--verify",
            "--quiet",
            "refs/heads/codex/task-20260511-191300-226866-patch-demo",
        ],
    ]


def test_create_runner_branch_runs_git_create_command_when_apply_enabled():
    commands = []
    plan = build_runner_branch_plan(
        task_code="TASK-20260511-191300-226866",
        title="Patch demo",
        task_level="L2",
        base_ref="main",
    )

    def fake_runner(command, **_kwargs):
        commands.append(command)
        if command == ["git", "branch", "--show-current"]:
            return FakeCompletedProcess(returncode=0, stdout="main\n")
        if command[:3] == ["git", "show-ref", "--verify"]:
            return FakeCompletedProcess(returncode=1)
        if command == [
            "git",
            "checkout",
            "-b",
            "codex/task-20260511-191300-226866-patch-demo",
            "main",
        ]:
            return FakeCompletedProcess(returncode=0)
        raise AssertionError(command)

    result = create_runner_branch(plan, dry_run=False, command_runner=fake_runner)

    assert result["created"] is True
    assert result["dry_run"] is False
    assert commands[-1] == plan["create_command"]


def test_create_runner_branch_rejects_existing_branch_on_apply():
    plan = build_runner_branch_plan(
        task_code="TASK-20260511-191300-226866",
        title="Patch demo",
        task_level="L2",
        base_ref="main",
    )

    def fake_runner(command, **_kwargs):
        if command == ["git", "branch", "--show-current"]:
            return FakeCompletedProcess(returncode=0, stdout="main\n")
        if command[:3] == ["git", "show-ref", "--verify"]:
            return FakeCompletedProcess(returncode=0)
        raise AssertionError(command)

    with pytest.raises(ValueError, match="Runner 分支已存在"):
        create_runner_branch(plan, dry_run=False, command_runner=fake_runner)


def test_create_runner_branch_skips_l4_plan():
    plan = build_runner_branch_plan(
        task_code="TASK-20260511-191300-226866",
        title="Roadmap",
        task_level="L4",
        base_ref="main",
    )

    def fake_runner(command, **_kwargs):
        if command == ["git", "branch", "--show-current"]:
            return FakeCompletedProcess(returncode=0, stdout="main\n")
        raise AssertionError(command)

    result = create_runner_branch(plan, dry_run=False, command_runner=fake_runner)

    assert result["branch_required"] is False
    assert result["created"] is False

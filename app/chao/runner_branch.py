import subprocess
from pathlib import Path
from typing import Any, Protocol, TypedDict

from app.chao.runner_policy import RunnerBranchPlan, is_valid_runner_branch_name


class CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


class RunnerBranchExecution(TypedDict):
    branch_required: bool
    branch_name: str | None
    base_ref: str
    create_command: list[str] | None
    current_branch: str
    branch_exists: bool
    created: bool
    dry_run: bool
    errors: list[str]


def _run_command(
    command: list[str],
    *,
    repo_root: Path | str,
    command_runner: Any,
) -> CommandResult:
    return command_runner(
        command,
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def inspect_runner_branch(
    branch_plan: RunnerBranchPlan,
    *,
    repo_root: Path | str = ".",
    command_runner: Any = subprocess.run,
) -> RunnerBranchExecution:
    branch_name = branch_plan["branch_name"]
    current_result = _run_command(
        ["git", "branch", "--show-current"],
        repo_root=repo_root,
        command_runner=command_runner,
    )
    current_branch = current_result.stdout.strip()
    errors: list[str] = []

    if not branch_plan["branch_required"]:
        return {
            "branch_required": False,
            "branch_name": branch_name,
            "base_ref": branch_plan["base_ref"],
            "create_command": branch_plan["create_command"],
            "current_branch": current_branch,
            "branch_exists": False,
            "created": False,
            "dry_run": True,
            "errors": [],
        }

    if branch_name is None or not is_valid_runner_branch_name(branch_name):
        errors.append(f"非法 Runner 分支名：{branch_name}")
        branch_exists = False
    else:
        exists_result = _run_command(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
            repo_root=repo_root,
            command_runner=command_runner,
        )
        branch_exists = exists_result.returncode == 0

        if branch_exists:
            errors.append(f"Runner 分支已存在：{branch_name}")

        if current_branch == branch_name:
            errors.append(f"当前已经位于 Runner 分支：{branch_name}")

    return {
        "branch_required": True,
        "branch_name": branch_name,
        "base_ref": branch_plan["base_ref"],
        "create_command": branch_plan["create_command"],
        "current_branch": current_branch,
        "branch_exists": branch_exists,
        "created": False,
        "dry_run": True,
        "errors": errors,
    }


def create_runner_branch(
    branch_plan: RunnerBranchPlan,
    *,
    repo_root: Path | str = ".",
    dry_run: bool = True,
    command_runner: Any = subprocess.run,
) -> RunnerBranchExecution:
    inspection = inspect_runner_branch(
        branch_plan,
        repo_root=repo_root,
        command_runner=command_runner,
    )
    inspection["dry_run"] = dry_run

    if not branch_plan["branch_required"] or dry_run:
        return inspection

    if inspection["errors"]:
        raise ValueError("; ".join(inspection["errors"]))

    create_command = branch_plan["create_command"]
    if create_command is None:
        raise ValueError("Runner 分支计划缺少创建命令。")

    result = _run_command(
        create_command,
        repo_root=repo_root,
        command_runner=command_runner,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git branch creation failed"
        raise RuntimeError(message)

    return {
        **inspection,
        "created": True,
        "dry_run": False,
    }

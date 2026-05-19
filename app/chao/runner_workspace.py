import subprocess
from pathlib import Path
from typing import Any, Protocol, TypedDict

from app.chao.runner_policy import RunnerWorkspacePlan, is_valid_runner_branch_name


class CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


class RunnerWorkspaceExecution(TypedDict):
    workspace_required: bool
    workspace_path: str | None
    branch_name: str | None
    base_ref: str
    create_command: list[str] | None
    workspace_exists: bool
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


def _resolve_workspace_path(repo_root: Path | str, workspace_path: str) -> Path:
    root = Path(repo_root).resolve()
    path = (root / workspace_path).resolve()

    if root != path and root not in path.parents:
        raise ValueError(f"Runner workspace path escapes repository: {workspace_path}")

    return path


def inspect_runner_workspace(
    workspace_plan: RunnerWorkspacePlan,
    *,
    repo_root: Path | str = ".",
    command_runner: Any = subprocess.run,
) -> RunnerWorkspaceExecution:
    workspace_path = workspace_plan["workspace_path"]
    branch_name = workspace_plan["branch_name"]
    errors: list[str] = []

    if not workspace_plan["workspace_required"]:
        return {
            "workspace_required": False,
            "workspace_path": workspace_path,
            "branch_name": branch_name,
            "base_ref": workspace_plan["base_ref"],
            "create_command": workspace_plan["create_command"],
            "workspace_exists": False,
            "branch_exists": False,
            "created": False,
            "dry_run": True,
            "errors": [],
        }

    if workspace_path is None:
        raise ValueError("Runner workspace plan missing workspace_path.")

    resolved_workspace = _resolve_workspace_path(repo_root, workspace_path)
    workspace_exists = resolved_workspace.exists()
    if workspace_exists:
        errors.append(f"Runner workspace already exists: {workspace_path}")

    if branch_name is None or not is_valid_runner_branch_name(branch_name):
        errors.append(f"Invalid runner branch name: {branch_name}")
        branch_exists = False
    else:
        exists_result = _run_command(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
            repo_root=repo_root,
            command_runner=command_runner,
        )
        branch_exists = exists_result.returncode == 0
        if branch_exists:
            errors.append(f"Runner branch already exists: {branch_name}")

    return {
        "workspace_required": True,
        "workspace_path": workspace_path,
        "branch_name": branch_name,
        "base_ref": workspace_plan["base_ref"],
        "create_command": workspace_plan["create_command"],
        "workspace_exists": workspace_exists,
        "branch_exists": branch_exists,
        "created": False,
        "dry_run": True,
        "errors": errors,
    }


def create_runner_workspace(
    workspace_plan: RunnerWorkspacePlan,
    *,
    repo_root: Path | str = ".",
    dry_run: bool = True,
    command_runner: Any = subprocess.run,
) -> RunnerWorkspaceExecution:
    inspection = inspect_runner_workspace(
        workspace_plan,
        repo_root=repo_root,
        command_runner=command_runner,
    )
    inspection["dry_run"] = dry_run

    if not workspace_plan["workspace_required"] or dry_run:
        return inspection

    if inspection["errors"]:
        raise ValueError("; ".join(inspection["errors"]))

    create_command = workspace_plan["create_command"]
    if create_command is None:
        raise ValueError("Runner workspace plan missing create_command.")

    result = _run_command(
        create_command,
        repo_root=repo_root,
        command_runner=command_runner,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git worktree add failed"
        raise RuntimeError(message)

    return {
        **inspection,
        "created": True,
        "dry_run": False,
    }

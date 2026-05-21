import subprocess
from pathlib import Path
from typing import Any, Literal, Protocol, TypedDict

from app.chao.repositories import RepositoryConfig

RepositorySyncMode = Literal["fetch", "pull-ff-only"]


class CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


class RepositorySyncResult(TypedDict):
    repository: str
    git_url: str
    workspace_path: str
    default_branch: str
    action: str
    commands: list[list[str]]
    workspace_exists: bool
    is_git_repository: bool
    dry_run: bool
    executed: bool
    errors: list[str]


class RepositoryStatusResult(TypedDict):
    repository: str
    workspace_path: str
    default_branch: str
    workspace_exists: bool
    is_git_repository: bool
    current_branch: str | None
    head_commit: str | None
    remote_url: str | None
    dirty: bool
    status_lines: list[str]
    ahead: int | None
    behind: int | None
    errors: list[str]


def _run_command(
    command: list[str],
    *,
    command_runner: Any,
) -> CommandResult:
    return command_runner(
        command,
        capture_output=True,
        text=True,
        check=False,
    )


def build_repository_sync_plan(
    repository: RepositoryConfig,
    *,
    mode: RepositorySyncMode = "fetch",
) -> RepositorySyncResult:
    if mode not in {"fetch", "pull-ff-only"}:
        raise ValueError(f"unsupported repository sync mode: {mode}")

    workspace = Path(repository.workspace_path).expanduser()
    workspace_exists = workspace.exists()
    is_git_repository = (workspace / ".git").exists()
    errors: list[str] = []
    commands: list[list[str]] = []
    action = "none"

    if workspace_exists and not workspace.is_dir():
        errors.append(f"repository workspace path is not a directory: {repository.workspace_path}")
    elif not workspace_exists:
        action = "clone"
        commands.append(["git", "clone", repository.git_url, str(workspace)])
    elif not is_git_repository:
        errors.append(f"repository workspace is not a git repository: {repository.workspace_path}")
    else:
        action = mode
        if mode == "pull-ff-only":
            commands.append(
                [
                    "git",
                    "-C",
                    str(workspace),
                    "pull",
                    "--ff-only",
                    "origin",
                    repository.default_branch,
                ]
            )
        else:
            commands.append(
                [
                    "git",
                    "-C",
                    str(workspace),
                    "fetch",
                    "origin",
                    repository.default_branch,
                ]
            )

    return {
        "repository": repository.name,
        "git_url": repository.git_url,
        "workspace_path": str(workspace),
        "default_branch": repository.default_branch,
        "action": action,
        "commands": commands,
        "workspace_exists": workspace_exists,
        "is_git_repository": is_git_repository,
        "dry_run": True,
        "executed": False,
        "errors": errors,
    }


def execute_repository_sync(
    repository: RepositoryConfig,
    *,
    mode: RepositorySyncMode = "fetch",
    dry_run: bool = True,
    command_runner: Any = subprocess.run,
) -> RepositorySyncResult:
    result = build_repository_sync_plan(repository, mode=mode)
    result["dry_run"] = dry_run

    if result["errors"] or dry_run:
        return result

    workspace = Path(result["workspace_path"])
    if result["action"] == "clone":
        workspace.parent.mkdir(parents=True, exist_ok=True)

    for command in result["commands"]:
        completed: CommandResult = command_runner(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "git command failed"
            result["errors"].append(message)
            break

    result["executed"] = not result["errors"]
    return result


def inspect_repository_status(
    repository: RepositoryConfig,
    *,
    command_runner: Any = subprocess.run,
) -> RepositoryStatusResult:
    workspace = Path(repository.workspace_path).expanduser()
    workspace_exists = workspace.exists()
    is_git_repository = (workspace / ".git").exists()
    errors: list[str] = []
    status_lines: list[str] = []
    current_branch = None
    head_commit = None
    remote_url = None
    ahead = None
    behind = None

    if workspace_exists and not workspace.is_dir():
        errors.append(f"repository workspace path is not a directory: {repository.workspace_path}")
    elif workspace_exists and not is_git_repository:
        errors.append(f"repository workspace is not a git repository: {repository.workspace_path}")

    if workspace_exists and is_git_repository and not errors:
        git_prefix = ["git", "-C", str(workspace)]
        commands = {
            "current_branch": [*git_prefix, "branch", "--show-current"],
            "head_commit": [*git_prefix, "rev-parse", "HEAD"],
            "remote_url": [*git_prefix, "config", "--get", "remote.origin.url"],
            "status": [*git_prefix, "status", "--short"],
            "divergence": [
                *git_prefix,
                "rev-list",
                "--left-right",
                "--count",
                f"HEAD...origin/{repository.default_branch}",
            ],
        }

        for key, command in commands.items():
            completed = _run_command(command, command_runner=command_runner)
            output = completed.stdout.strip()

            if completed.returncode != 0:
                if key == "divergence":
                    continue
                message = completed.stderr.strip() or output or f"git {key} failed"
                errors.append(message)
                continue

            if key == "current_branch":
                current_branch = output or None
            elif key == "head_commit":
                head_commit = output or None
            elif key == "remote_url":
                remote_url = output or None
            elif key == "status":
                status_lines = output.splitlines() if output else []
            elif key == "divergence":
                parts = output.split()
                if len(parts) == 2:
                    ahead = int(parts[0])
                    behind = int(parts[1])

    return {
        "repository": repository.name,
        "workspace_path": str(workspace),
        "default_branch": repository.default_branch,
        "workspace_exists": workspace_exists,
        "is_git_repository": is_git_repository,
        "current_branch": current_branch,
        "head_commit": head_commit,
        "remote_url": remote_url,
        "dirty": bool(status_lines),
        "status_lines": status_lines,
        "ahead": ahead,
        "behind": behind,
        "errors": errors,
    }

import subprocess
from pathlib import Path
from typing import Any, Protocol, TypedDict

from app.chao.repositories import RepositoryConfig
from app.chao.runner_policy import normalize_repo_path, require_change_scope_allowed


class CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


class SelfUpgradeDeliveryResult(TypedDict):
    repository: str
    workspace_path: str
    changed_files: list[str]
    commit_message: str
    status_lines: list[str]
    dry_run: bool
    committed: bool
    pushed: bool
    commit_sha: str | None
    commands: list[list[str]]
    errors: list[str]


def execute_self_upgrade_delivery(
    repository: RepositoryConfig,
    *,
    changed_files: list[str],
    commit_message: str,
    dry_run: bool = True,
    push: bool = False,
    command_runner: Any = subprocess.run,
) -> SelfUpgradeDeliveryResult:
    normalized_files = _normalize_changed_files(changed_files)
    message = _normalize_commit_message(commit_message)
    workspace = Path(repository.workspace_path).expanduser()
    commands = _build_delivery_commands(workspace, normalized_files, message, push=push)

    result: SelfUpgradeDeliveryResult = {
        "repository": repository.name,
        "workspace_path": str(workspace),
        "changed_files": normalized_files,
        "commit_message": message,
        "status_lines": [],
        "dry_run": dry_run,
        "committed": False,
        "pushed": False,
        "commit_sha": None,
        "commands": commands,
        "errors": [],
    }

    status_result = _run_git(
        ["git", "-C", str(workspace), "status", "--short", "--", *normalized_files],
        command_runner=command_runner,
    )
    if status_result.returncode != 0:
        result["errors"].append(_command_error(status_result, "git status failed"))
        return result

    result["status_lines"] = status_result.stdout.rstrip("\r\n").splitlines()
    if not result["status_lines"]:
        result["errors"].append("no self-upgrade changes to commit")
        return result

    if dry_run:
        return result

    for command in commands:
        completed = _run_git(command, command_runner=command_runner)
        if completed.returncode != 0:
            result["errors"].append(_command_error(completed, "git delivery command failed"))
            return result

        if command[3:4] == ["commit"]:
            result["committed"] = True
        elif command[3:4] == ["push"]:
            result["pushed"] = True

    rev_parse = _run_git(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        command_runner=command_runner,
    )
    if rev_parse.returncode == 0:
        result["commit_sha"] = rev_parse.stdout.strip() or None
    else:
        result["errors"].append(_command_error(rev_parse, "git rev-parse failed"))

    return result


def _normalize_changed_files(changed_files: list[str]) -> list[str]:
    if not changed_files:
        raise ValueError("self-upgrade delivery requires changed files")

    normalized_files: list[str] = []
    for path in changed_files:
        normalized = normalize_repo_path(path)
        if normalized not in normalized_files:
            normalized_files.append(normalized)

    require_change_scope_allowed(normalized_files)
    return normalized_files


def _normalize_commit_message(commit_message: str) -> str:
    message = " ".join(commit_message.strip().split())
    if not message:
        raise ValueError("self-upgrade delivery requires commit_message")
    if len(message) > 160:
        raise ValueError("self-upgrade commit_message must be 160 characters or fewer")

    lowered = message.lower()
    sensitive_tokens = (
        "token" + "=",
        "api" + "_" + "key=",
        "apikey" + "=",
        "password" + "=",
        "secret" + "=",
    )
    for token in sensitive_tokens:
        if token in lowered:
            raise ValueError("self-upgrade commit_message must not contain sensitive fields")

    return message


def _build_delivery_commands(
    workspace: Path,
    changed_files: list[str],
    commit_message: str,
    *,
    push: bool,
) -> list[list[str]]:
    commands = [
        ["git", "-C", str(workspace), "add", "--", *changed_files],
        ["git", "-C", str(workspace), "commit", "-m", commit_message],
    ]
    if push:
        commands.append(["git", "-C", str(workspace), "push", "-u", "origin", "HEAD"])

    return commands


def _run_git(command: list[str], *, command_runner: Any) -> CommandResult:
    return command_runner(
        command,
        capture_output=True,
        text=True,
        check=False,
    )


def _command_error(result: CommandResult, fallback: str) -> str:
    return result.stderr.strip() or result.stdout.strip() or fallback

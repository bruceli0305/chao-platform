import re
import subprocess
from pathlib import Path
from typing import Any, Protocol, TypedDict

from app.chao.repositories import RepositoryConfig


class CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


class GitHubPullRequestResult(TypedDict):
    repository: str
    workspace_path: str
    title: str
    body: str
    base_ref: str
    head_ref: str | None
    dry_run: bool
    created: bool
    url: str | None
    external_id: str | None
    commands: list[list[str]]
    errors: list[str]


def build_self_upgrade_pr_body(
    *,
    task_code: str,
    summary: str,
    changed_files: list[str],
    validation_gates: list[str],
) -> str:
    changed_file_lines = "\n".join(f"- {path}" for path in changed_files) or "- none"
    validation_gate_lines = "\n".join(f"- {gate}" for gate in validation_gates) or "- none"

    return (
        f"Task Code: {task_code}\n\n"
        "## Summary\n"
        f"{summary}\n\n"
        "## Changed Files\n"
        f"{changed_file_lines}\n\n"
        "## Validation Gates\n"
        f"{validation_gate_lines}\n"
    )


def execute_github_pr_create(
    repository: RepositoryConfig,
    *,
    title: str,
    body: str,
    base_ref: str,
    head_ref: str | None = None,
    dry_run: bool = True,
    command_runner: Any = subprocess.run,
) -> GitHubPullRequestResult:
    workspace = Path(repository.workspace_path).expanduser()
    errors: list[str] = []
    resolved_head_ref = head_ref or _current_branch(
        workspace,
        command_runner=command_runner,
        errors=errors,
    )
    commands: list[list[str]] = []

    if resolved_head_ref:
        commands.append(
            [
                "gh",
                "pr",
                "create",
                "--base",
                base_ref,
                "--head",
                resolved_head_ref,
                "--title",
                _normalize_title(title),
                "--body",
                body,
            ]
        )

    result: GitHubPullRequestResult = {
        "repository": repository.name,
        "workspace_path": str(workspace),
        "title": _normalize_title(title),
        "body": body,
        "base_ref": base_ref,
        "head_ref": resolved_head_ref,
        "dry_run": dry_run,
        "created": False,
        "url": None,
        "external_id": None,
        "commands": commands,
        "errors": errors,
    }

    if errors or dry_run:
        return result

    completed = _run_command(commands[0], cwd=workspace, command_runner=command_runner)
    if completed.returncode != 0:
        result["errors"].append(_command_error(completed, "gh pr create failed"))
        return result

    url = _extract_pull_request_url(completed.stdout.strip())
    result["created"] = True
    result["url"] = url
    result["external_id"] = _extract_pull_request_number(url) if url else None
    return result


def _current_branch(
    workspace: Path,
    *,
    command_runner: Any,
    errors: list[str],
) -> str | None:
    completed = _run_command(
        ["git", "branch", "--show-current"],
        cwd=workspace,
        command_runner=command_runner,
    )
    if completed.returncode != 0:
        errors.append(_command_error(completed, "git branch lookup failed"))
        return None

    branch = completed.stdout.strip()
    if not branch:
        errors.append("current git branch is empty")
        return None

    return branch


def _normalize_title(title: str) -> str:
    normalized = " ".join(title.strip().split())
    if not normalized:
        raise ValueError("GitHub PR title is required")
    if len(normalized) > 160:
        raise ValueError("GitHub PR title must be 160 characters or fewer")
    return normalized


def _run_command(command: list[str], *, cwd: Path, command_runner: Any) -> CommandResult:
    return command_runner(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _command_error(result: CommandResult, fallback: str) -> str:
    return result.stderr.strip() or result.stdout.strip() or fallback


def _extract_pull_request_url(output: str) -> str | None:
    for token in output.split():
        if "/pull/" in token and token.startswith("http"):
            return token.strip()
    return None


def _extract_pull_request_number(url: str | None) -> str | None:
    if not url:
        return None

    match = re.search(r"/pull/(\d+)", url)
    if not match:
        return None
    return match.group(1)

import json
import subprocess
from pathlib import Path
from typing import Any, Protocol, TypedDict

from app.chao.repositories import RepositoryConfig


class CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


class GitHubCheckRun(TypedDict):
    name: str
    state: str
    link: str | None
    workflow: str | None
    bucket: str | None


class GitHubPRChecksResult(TypedDict):
    repository: str
    workspace_path: str
    pr_ref: str
    status: str
    deliverable: bool
    dry_run: bool
    checks: list[GitHubCheckRun]
    commands: list[list[str]]
    errors: list[str]


SUCCESS_STATES = {"SUCCESS", "SKIPPED", "NEUTRAL", "PASSING"}
FAILURE_STATES = {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}


def execute_github_pr_checks(
    repository: RepositoryConfig,
    *,
    pr_ref: str,
    dry_run: bool = True,
    command_runner: Any = subprocess.run,
) -> GitHubPRChecksResult:
    workspace = Path(repository.workspace_path).expanduser()
    command = [
        "gh",
        "pr",
        "checks",
        pr_ref,
        "--json",
        "name,state,link,bucket,workflow",
    ]
    result: GitHubPRChecksResult = {
        "repository": repository.name,
        "workspace_path": str(workspace),
        "pr_ref": pr_ref,
        "status": "dry_run" if dry_run else "pending",
        "deliverable": False,
        "dry_run": dry_run,
        "checks": [],
        "commands": [command],
        "errors": [],
    }

    if dry_run:
        return result

    completed = command_runner(
        command,
        cwd=str(workspace),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        result["status"] = "failed"
        result["errors"].append(_command_error(completed, "gh pr checks failed"))
        return result

    try:
        checks = _parse_checks(completed.stdout)
    except ValueError as exc:
        result["status"] = "failed"
        result["errors"].append(str(exc))
        return result

    result["checks"] = checks
    result["status"] = _classify_checks(checks)
    result["deliverable"] = result["status"] == "passed"
    return result


def _parse_checks(output: str) -> list[GitHubCheckRun]:
    try:
        raw_checks = json.loads(output or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError(f"gh pr checks output is not valid JSON: {exc.msg}") from exc

    if not isinstance(raw_checks, list):
        raise ValueError("gh pr checks output must be a JSON array")

    checks: list[GitHubCheckRun] = []
    for raw_check in raw_checks:
        if not isinstance(raw_check, dict):
            continue
        checks.append(
            {
                "name": str(raw_check.get("name") or ""),
                "state": str(raw_check.get("state") or "").upper(),
                "link": raw_check.get("link") if isinstance(raw_check.get("link"), str) else None,
                "workflow": (
                    raw_check.get("workflow")
                    if isinstance(raw_check.get("workflow"), str)
                    else None
                ),
                "bucket": (
                    raw_check.get("bucket") if isinstance(raw_check.get("bucket"), str) else None
                ),
            }
        )

    return checks


def _classify_checks(checks: list[GitHubCheckRun]) -> str:
    if not checks:
        return "pending"

    states = {check["state"] for check in checks}
    if states & FAILURE_STATES:
        return "failed"
    if all(state in SUCCESS_STATES for state in states):
        return "passed"
    return "pending"


def _command_error(result: CommandResult, fallback: str) -> str:
    return result.stderr.strip() or result.stdout.strip() or fallback

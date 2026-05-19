import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict

from app.chao.runner_validation import GATE_COMMANDS, NON_EXECUTABLE_GATES

DEFAULT_SANDBOX_IMAGE = "ghcr.io/astral-sh/uv:python3.12-bookworm-slim"


class RunnerSandboxCommand(TypedDict):
    gate: str
    command: str
    docker_command: list[str]


class RunnerSandboxResult(TypedDict):
    workspace_path: str
    image: str
    gates: list[str]
    docker_commands: list[RunnerSandboxCommand]
    command_results: list[dict[str, Any]]
    dry_run: bool
    executed: bool
    deliverable: bool
    errors: list[str]


def _resolve_workspace_path(repo_root: Path | str, workspace_path: str) -> Path:
    root = Path(repo_root).resolve()
    path = (root / workspace_path).resolve()

    if root != path and root not in path.parents:
        raise ValueError(f"Runner sandbox workspace path escapes repository: {workspace_path}")

    return path


def build_runner_sandbox_commands(
    gates: list[str],
    *,
    workspace_path: str = ".",
    image: str = DEFAULT_SANDBOX_IMAGE,
    repo_root: Path | str = ".",
) -> tuple[list[RunnerSandboxCommand], list[str]]:
    resolved_workspace = _resolve_workspace_path(repo_root, workspace_path)
    docker_commands: list[RunnerSandboxCommand] = []
    errors: list[str] = []

    for gate in gates:
        command = GATE_COMMANDS.get(gate)
        if command is None:
            errors.append(f"Unknown runner sandbox gate: {gate}")
            continue

        if gate in NON_EXECUTABLE_GATES:
            errors.append(f"Runner sandbox gate is not executable: {gate}")
            continue

        docker_commands.append(
            {
                "gate": gate,
                "command": command,
                "docker_command": [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{resolved_workspace}:/workspace",
                    "-w",
                    "/workspace",
                    image,
                    "bash",
                    "-lc",
                    command,
                ],
            }
        )

    return docker_commands, errors


def _summarize_output(stdout: str | None, stderr: str | None, limit: int = 2000) -> str:
    output = "\n".join(part for part in [stdout or "", stderr or ""] if part).strip()
    if len(output) <= limit:
        return output

    return output[:limit] + "\n...[truncated]"


def execute_runner_sandbox_commands(
    gates: list[str],
    *,
    workspace_path: str = ".",
    image: str = DEFAULT_SANDBOX_IMAGE,
    repo_root: Path | str = ".",
    dry_run: bool = True,
    timeout_seconds: int = 120,
    command_runner: Callable[..., Any] = subprocess.run,
) -> RunnerSandboxResult:
    docker_commands, errors = build_runner_sandbox_commands(
        gates,
        workspace_path=workspace_path,
        image=image,
        repo_root=repo_root,
    )

    if errors:
        raise ValueError("; ".join(errors))

    if dry_run:
        return {
            "workspace_path": workspace_path,
            "image": image,
            "gates": gates,
            "docker_commands": docker_commands,
            "command_results": [],
            "dry_run": True,
            "executed": False,
            "deliverable": False,
            "errors": [],
        }

    command_results: list[dict[str, Any]] = []
    for command in docker_commands:
        completed = command_runner(
            command["docker_command"],
            cwd=str(Path(repo_root)),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        exit_code = int(completed.returncode)
        command_results.append(
            {
                "gate": command["gate"],
                "command": " ".join(command["docker_command"]),
                "status": "passed" if exit_code == 0 else "failed",
                "exit_code": exit_code,
                "output_summary": _summarize_output(
                    getattr(completed, "stdout", ""),
                    getattr(completed, "stderr", ""),
                ),
            }
        )

    deliverable = all(result["exit_code"] == 0 for result in command_results)

    return {
        "workspace_path": workspace_path,
        "image": image,
        "gates": gates,
        "docker_commands": docker_commands,
        "command_results": command_results,
        "dry_run": False,
        "executed": True,
        "deliverable": deliverable,
        "errors": [],
    }

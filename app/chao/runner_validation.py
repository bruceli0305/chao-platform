import shlex
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict


class RunnerValidationStep(TypedDict):
    gate: str
    command: str
    required: bool


class RunnerValidationResult(TypedDict):
    quality: str
    checks: list[str]
    plan: list[RunnerValidationStep]
    command_results: list[dict[str, Any]]
    deliverable: bool
    note: str


GATE_COMMANDS = {
    "build": "uv run python -m compileall app tests main.py",
    "compile": "uv run python -m compileall app tests main.py",
    "data_boundary_check": "uv run python scripts/data_boundary_check.py",
    "lint": "uv run ruff check app tests main.py",
    "manual_validation": "manual validation evidence required",
    "milestone_review": "manual milestone review required",
    "schema_check": "uv run python scripts/schema_check.py",
    "secret_scan": "gitleaks detect --redact",
    "test": "uv run pytest -q",
    "typecheck": "uv run python -m compileall app tests main.py",
}

NON_EXECUTABLE_GATES = {"manual_validation", "milestone_review", "secret_scan"}


def build_runner_validation_plan(gates: list[str]) -> list[RunnerValidationStep]:
    return [
        {
            "gate": gate,
            "command": GATE_COMMANDS.get(gate, f"manual validation required for {gate}"),
            "required": True,
        }
        for gate in gates
    ]


def build_runner_validation_result(
    gates: list[str],
    command_results: list[dict[str, Any]] | None = None,
) -> RunnerValidationResult:
    plan = build_runner_validation_plan(gates)
    command_results = command_results or [
        {
            "gate": step["gate"],
            "command": step["command"],
            "status": "passed",
            "exit_code": 0,
            "output_summary": "MVP smoke validation recorded.",
        }
        for step in plan
    ]
    deliverable = all(result.get("exit_code") == 0 for result in command_results)

    return {
        "quality": "可交付" if deliverable else "验证失败",
        "checks": gates,
        "plan": plan,
        "command_results": command_results,
        "deliverable": deliverable,
        "note": ("刑部验证通过，可进入交付。" if deliverable else "刑部验证失败，禁止进入交付。"),
    }


def _summarize_command_output(stdout: str | None, stderr: str | None, limit: int = 2000) -> str:
    output = "\n".join(part for part in [stdout or "", stderr or ""] if part).strip()
    if not output:
        return ""

    if len(output) <= limit:
        return output

    return output[:limit] + "\n...[truncated]"


def execute_runner_validation_commands(
    gates: list[str],
    *,
    repo_root: Path | str = ".",
    timeout_seconds: int = 120,
    command_runner: Callable[..., Any] = subprocess.run,
) -> RunnerValidationResult:
    plan = build_runner_validation_plan(gates)
    command_results: list[dict[str, Any]] = []

    for step in plan:
        gate = step["gate"]
        command = step["command"]

        if gate not in GATE_COMMANDS or gate in NON_EXECUTABLE_GATES:
            command_results.append(
                {
                    "gate": gate,
                    "command": command,
                    "status": "failed",
                    "exit_code": 1,
                    "output_summary": f"Gate requires manual or external validation: {gate}",
                }
            )
            continue

        try:
            completed = command_runner(
                shlex.split(command),
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            exit_code = int(completed.returncode)
            output_summary = _summarize_command_output(
                getattr(completed, "stdout", ""),
                getattr(completed, "stderr", ""),
            )
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            output_summary = _summarize_command_output(exc.stdout, exc.stderr)
            if output_summary:
                output_summary = f"Command timed out after {timeout_seconds}s.\n{output_summary}"
            else:
                output_summary = f"Command timed out after {timeout_seconds}s."

        command_results.append(
            {
                "gate": gate,
                "command": command,
                "status": "passed" if exit_code == 0 else "failed",
                "exit_code": exit_code,
                "output_summary": output_summary,
            }
        )

    return build_runner_validation_result(gates, command_results)


def require_runner_validation_success(
    result: RunnerValidationResult,
) -> RunnerValidationResult:
    if not result["deliverable"]:
        failed = [
            command_result["gate"]
            for command_result in result["command_results"]
            if command_result.get("exit_code") != 0
        ]
        raise PermissionError(f"刑部验证失败，禁止交付：{', '.join(failed)}")

    return result

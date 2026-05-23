import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, TypedDict

from app.chao.repositories import get_repository_config, validate_repository_configs
from app.chao.repository_sync import inspect_repository_status


class CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


class DoctorCheck(TypedDict):
    name: str
    ready: bool
    severity: str
    summary: str
    details: dict[str, Any]


class DoctorReport(TypedDict):
    status: str
    ready: bool
    checks: list[DoctorCheck]


CommandExists = Callable[[str], bool]


def run_chao_doctor(
    *,
    repo_root: Path | str = ".",
    environ: dict[str, str] | None = None,
    command_runner: Any = subprocess.run,
    command_exists: CommandExists | None = None,
) -> DoctorReport:
    env = os.environ if environ is None else environ
    root = Path(repo_root)
    exists = command_exists or (
        lambda command: shutil.which(command, path=env.get("PATH")) is not None
    )

    checks = [
        _check_command("uv", command_exists=exists),
        _check_docker_postgres(
            environ=env,
            command_runner=command_runner,
            command_exists=exists,
        ),
        _check_schema(
            root,
            environ=env,
            command_runner=command_runner,
            command_exists=exists,
        ),
        _check_gh_auth(environ=env, command_runner=command_runner, command_exists=exists),
        _check_deepseek_key(env),
        _check_repository_config(env),
        _check_repository_workspace(environ=env, command_runner=command_runner),
    ]
    ready = all(check["ready"] for check in checks if check["severity"] == "required")

    return {
        "status": "ready" if ready else "blocked",
        "ready": ready,
        "checks": checks,
    }


def _check_command(command: str, *, command_exists: CommandExists) -> DoctorCheck:
    ready = command_exists(command)
    return {
        "name": f"command:{command}",
        "ready": ready,
        "severity": "required",
        "summary": f"{command} is available" if ready else f"{command} is not available on PATH",
        "details": {"command": command},
    }


def _check_docker_postgres(
    *,
    environ: dict[str, str],
    command_runner: Any,
    command_exists: CommandExists,
) -> DoctorCheck:
    container_name = environ.get("CHAO_POSTGRES_CONTAINER", "chao-postgres")
    db_user = environ.get("CHAO_POSTGRES_USER", "chao")
    db_name = environ.get("CHAO_POSTGRES_DB", "chao")

    if not command_exists("docker"):
        return {
            "name": "docker:postgres",
            "ready": False,
            "severity": "required",
            "summary": "docker is not available on PATH",
            "details": {"container": container_name},
        }

    ps_result = _run(
        [
            "docker",
            "ps",
            "--filter",
            f"name={container_name}",
            "--format",
            "{{.Names}}",
        ],
        env=environ,
        command_runner=command_runner,
    )
    if ps_result.returncode != 0 or container_name not in ps_result.stdout.splitlines():
        return {
            "name": "docker:postgres",
            "ready": False,
            "severity": "required",
            "summary": f"{container_name} container is not running",
            "details": {"stderr": ps_result.stderr.strip(), "stdout": ps_result.stdout.strip()},
        }

    ready_result = _run(
        ["docker", "exec", container_name, "pg_isready", "-U", db_user, "-d", db_name],
        env=environ,
        command_runner=command_runner,
    )
    return {
        "name": "docker:postgres",
        "ready": ready_result.returncode == 0,
        "severity": "required",
        "summary": (
            f"{container_name} is running and ready"
            if ready_result.returncode == 0
            else f"{container_name} is running but not ready"
        ),
        "details": {"stdout": ready_result.stdout.strip(), "stderr": ready_result.stderr.strip()},
    }


def _check_schema(
    repo_root: Path,
    *,
    environ: dict[str, str],
    command_runner: Any,
    command_exists: CommandExists,
) -> DoctorCheck:
    if not command_exists("uv"):
        return {
            "name": "database:schema",
            "ready": False,
            "severity": "required",
            "summary": "schema check requires uv",
            "details": {},
        }

    result = _run(
        ["uv", "run", "python", "scripts/schema_check.py"],
        cwd=repo_root,
        env=environ,
        command_runner=command_runner,
    )
    return {
        "name": "database:schema",
        "ready": result.returncode == 0,
        "severity": "required",
        "summary": "schema check passed" if result.returncode == 0 else "schema check failed",
        "details": {"stdout": result.stdout.strip(), "stderr": result.stderr.strip()},
    }


def _check_gh_auth(
    *,
    environ: dict[str, str],
    command_runner: Any,
    command_exists: CommandExists,
) -> DoctorCheck:
    if not command_exists("gh"):
        return {
            "name": "github:auth",
            "ready": False,
            "severity": "required",
            "summary": "gh is not available on PATH",
            "details": {},
        }

    result = _run(["gh", "auth", "status"], env=environ, command_runner=command_runner)
    return {
        "name": "github:auth",
        "ready": result.returncode == 0,
        "severity": "required",
        "summary": "GitHub CLI is authenticated"
        if result.returncode == 0
        else "GitHub CLI is not authenticated",
        "details": {"stdout": result.stdout.strip(), "stderr": result.stderr.strip()},
    }


def _check_deepseek_key(env: dict[str, str]) -> DoctorCheck:
    ready = bool(env.get("DEEPSEEK_API_KEY"))
    return {
        "name": "llm:deepseek_key",
        "ready": ready,
        "severity": "required",
        "summary": "DEEPSEEK_API_KEY is set" if ready else "DEEPSEEK_API_KEY is not set",
        "details": {"env": "DEEPSEEK_API_KEY", "set": ready},
    }


def _check_repository_config(env: dict[str, str]) -> DoctorCheck:
    errors = validate_repository_configs(environ=env)
    return {
        "name": "repository:config",
        "ready": not errors,
        "severity": "required",
        "summary": "repository config is valid" if not errors else "repository config is invalid",
        "details": {"errors": errors},
    }


def _check_repository_workspace(*, environ: dict[str, str], command_runner: Any) -> DoctorCheck:
    try:
        repository = get_repository_config(environ=environ)
        status = inspect_repository_status(repository, command_runner=command_runner)
    except Exception as exc:
        return {
            "name": "repository:workspace",
            "ready": False,
            "severity": "required",
            "summary": "repository workspace check failed",
            "details": {"error": str(exc)},
        }

    ready = (
        status["workspace_exists"]
        and status["is_git_repository"]
        and not status["dirty"]
        and not status["errors"]
    )
    return {
        "name": "repository:workspace",
        "ready": ready,
        "severity": "required",
        "summary": "repository workspace is runner ready"
        if ready
        else "repository workspace is not runner ready",
        "details": status,
    }


def _run(
    command: list[str],
    *,
    command_runner: Any,
    cwd: Path | str | None = None,
    env: dict[str, str] | None = None,
) -> CommandResult:
    return command_runner(
        command,
        cwd=str(cwd) if cwd is not None else None,
        env=dict(env) if env is not None else None,
        capture_output=True,
        text=True,
        check=False,
    )

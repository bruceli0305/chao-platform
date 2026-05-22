from typing import Any, TypedDict

from app.chao.repositories import RepositoryConfig
from app.chao.repository_sync import RepositoryDoctorResult, build_repository_doctor_report


class RunnerPreflightResult(TypedDict):
    task_code: str
    task_level: str
    repository: str
    status: str
    runner_allowed: bool
    repository_ready: bool
    validation_gates: list[str]
    repository_doctor: RepositoryDoctorResult
    errors: list[str]


def build_runner_preflight_result(
    task: dict[str, Any],
    repository: RepositoryConfig,
    validation_gates: list[str],
) -> RunnerPreflightResult:
    repository_doctor = build_repository_doctor_report(repository)
    errors: list[str] = []
    task_level = str(task.get("task_level", ""))
    runner_allowed = task_level != "L4"

    if not runner_allowed:
        errors.append("L4 tasks cannot execute runner commands.")

    if not repository_doctor["runner_ready"]:
        errors.append(f"repository is not runner ready: {repository_doctor['suggested_action']}")

    if not validation_gates:
        errors.append("No validation gates provided or recorded for this task.")

    return {
        "task_code": str(task.get("task_code", "")),
        "task_level": task_level,
        "repository": repository.name,
        "status": "ready" if not errors else "blocked",
        "runner_allowed": runner_allowed,
        "repository_ready": repository_doctor["runner_ready"],
        "validation_gates": validation_gates,
        "repository_doctor": repository_doctor,
        "errors": errors,
    }

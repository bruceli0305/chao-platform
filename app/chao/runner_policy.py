from pathlib import PurePosixPath
from typing import TypedDict

from app.chao.state import TaskLevel


class RunnerBoundaryPolicy(TypedDict):
    execution_environment: str
    workspace_root: str
    sandbox_root: str
    patch_artifact_root: str
    required_branch_prefix: str
    allowed_change_roots: list[str]
    forbidden_change_roots: list[str]
    can_execute: bool


DEFAULT_ALLOWED_CHANGE_ROOTS = [
    ".ai-agents/records/",
    ".ai-agents/templates/",
    ".github/workflows/",
    "app/",
    "db/init/",
    "db/migrations/",
    "docs/",
    "main.py",
    "scripts/",
    "tests/",
]

DEFAULT_FORBIDDEN_CHANGE_ROOTS = [
    ".env",
    ".env.",
    ".venv/",
    "__pycache__/",
    "data/",
    "logs/",
]


def build_runner_boundary_policy(task_level: TaskLevel) -> RunnerBoundaryPolicy:
    return {
        "execution_environment": "branch_or_sandbox",
        "workspace_root": ".",
        "sandbox_root": ".chao/sandboxes",
        "patch_artifact_root": ".ai-agents/records/patches",
        "required_branch_prefix": "codex/",
        "allowed_change_roots": DEFAULT_ALLOWED_CHANGE_ROOTS,
        "forbidden_change_roots": DEFAULT_FORBIDDEN_CHANGE_ROOTS,
        "can_execute": task_level != "L4",
    }


def normalize_repo_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()

    if not normalized:
        raise ValueError("路径不能为空。")

    if normalized.startswith("/"):
        raise ValueError(f"路径必须是仓库相对路径：{path}")

    parts = PurePosixPath(normalized).parts

    if ".." in parts:
        raise ValueError(f"路径不能跳出仓库：{path}")

    if parts and parts[0] == ".":
        parts = parts[1:]

    return "/".join(parts)


def path_matches_scope(path: str, scope: str) -> bool:
    if scope.endswith("/"):
        return path.startswith(scope)
    if scope.endswith("."):
        return path.startswith(scope)
    return path == scope or path.startswith(f"{scope}/")


def path_contains_scope(path: str, scope: str) -> bool:
    scope_name = scope.rstrip("/")

    if "/" in scope_name:
        return path_matches_scope(path, scope)

    return scope_name in PurePosixPath(path).parts


def is_change_path_allowed(
    path: str,
    policy: RunnerBoundaryPolicy | None = None,
) -> bool:
    policy = policy or build_runner_boundary_policy("L2")
    repo_path = normalize_repo_path(path)

    if any(path_contains_scope(repo_path, root) for root in policy["forbidden_change_roots"]):
        return False

    return any(path_matches_scope(repo_path, root) for root in policy["allowed_change_roots"])


def check_change_paths(
    paths: list[str],
    policy: RunnerBoundaryPolicy | None = None,
) -> list[str]:
    policy = policy or build_runner_boundary_policy("L2")
    errors: list[str] = []

    for path in paths:
        try:
            allowed = is_change_path_allowed(path, policy)
        except ValueError as exc:
            errors.append(str(exc))
            continue

        if not allowed:
            errors.append(f"路径不在 Agent Runner 允许修改范围内：{path}")

    return errors

import re
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


class RunnerBranchPlan(TypedDict):
    branch_required: bool
    branch_name: str | None
    base_ref: str
    create_command: list[str] | None
    reason: str


class RunnerWorkspacePlan(TypedDict):
    workspace_required: bool
    workspace_path: str | None
    branch_name: str | None
    base_ref: str
    create_command: list[str] | None
    reason: str


class RunnerScopeDecision(TypedDict):
    allowed: bool
    checked_paths: list[str]
    errors: list[str]
    policy: RunnerBoundaryPolicy


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

RESERVED_BRANCH_NAMES = {"main", "master", "trunk"}

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


def evaluate_change_scope(
    paths: list[str],
    policy: RunnerBoundaryPolicy | None = None,
) -> RunnerScopeDecision:
    policy = policy or build_runner_boundary_policy("L2")
    return {
        "allowed": not check_change_paths(paths, policy),
        "checked_paths": paths,
        "errors": check_change_paths(paths, policy),
        "policy": policy,
    }


def require_change_scope_allowed(
    paths: list[str],
    policy: RunnerBoundaryPolicy | None = None,
) -> RunnerScopeDecision:
    decision = evaluate_change_scope(paths, policy)

    if not decision["allowed"]:
        raise PermissionError("; ".join(decision["errors"]))

    return decision


def normalize_branch_slug(value: str, fallback: str = "task") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def build_runner_branch_name(
    *,
    task_code: str,
    title: str,
    branch_prefix: str = "codex/",
) -> str:
    normalized_task_code = normalize_branch_slug(task_code)
    normalized_title = normalize_branch_slug(title)[:40]
    return f"{branch_prefix}{normalized_task_code}-{normalized_title}"


def is_valid_runner_branch_name(
    branch_name: str,
    branch_prefix: str = "codex/",
) -> bool:
    if not branch_name.startswith(branch_prefix):
        return False

    if branch_name in RESERVED_BRANCH_NAMES:
        return False

    if branch_name.endswith("/") or branch_name.endswith("."):
        return False

    if any(token in branch_name for token in ["..", " ", "\\", "@{"]):
        return False

    return True


def build_runner_branch_plan(
    *,
    task_code: str,
    title: str,
    task_level: TaskLevel,
    base_ref: str = "HEAD",
    branch_prefix: str | None = None,
) -> RunnerBranchPlan:
    policy = build_runner_boundary_policy(task_level)
    runner_branch_prefix = branch_prefix or policy["required_branch_prefix"]

    if not policy["can_execute"]:
        return {
            "branch_required": False,
            "branch_name": None,
            "base_ref": base_ref,
            "create_command": None,
            "reason": f"{task_level} 任务只生成规划，不创建执行分支。",
        }

    branch_name = build_runner_branch_name(
        task_code=task_code,
        title=title,
        branch_prefix=runner_branch_prefix,
    )

    return {
        "branch_required": True,
        "branch_name": branch_name,
        "base_ref": base_ref,
        "create_command": ["git", "checkout", "-b", branch_name, base_ref],
        "reason": "执行型任务必须在 codex/ 前缀分支中运行。",
    }


def build_runner_workspace_plan(
    *,
    task_code: str,
    title: str,
    task_level: TaskLevel,
    base_ref: str = "HEAD",
    branch_prefix: str | None = None,
    sandbox_root: str | None = None,
) -> RunnerWorkspacePlan:
    policy = build_runner_boundary_policy(task_level)
    runner_branch_prefix = branch_prefix or policy["required_branch_prefix"]
    runner_sandbox_root = sandbox_root or policy["sandbox_root"]

    if not policy["can_execute"]:
        return {
            "workspace_required": False,
            "workspace_path": None,
            "branch_name": None,
            "base_ref": base_ref,
            "create_command": None,
            "reason": f"{task_level} 任务只生成规划，不创建隔离工作区。",
        }

    branch_name = build_runner_branch_name(
        task_code=task_code,
        title=title,
        branch_prefix=runner_branch_prefix,
    )
    workspace_slug = normalize_branch_slug(branch_name.replace("/", "-"), fallback="runner")
    workspace_path = f"{runner_sandbox_root.rstrip('/')}/{workspace_slug}"

    return {
        "workspace_required": True,
        "workspace_path": workspace_path,
        "branch_name": branch_name,
        "base_ref": base_ref,
        "create_command": [
            "git",
            "worktree",
            "add",
            "-b",
            branch_name,
            workspace_path,
            base_ref,
        ],
        "reason": "执行型任务应优先在 .chao/sandboxes 下的隔离 worktree 中运行。",
    }

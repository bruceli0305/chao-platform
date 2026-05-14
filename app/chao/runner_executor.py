import hashlib
from pathlib import Path
from typing import Any, TypedDict

from app.chao.runner_policy import normalize_repo_path, require_change_scope_allowed


class RunnerTextPatchOperation(TypedDict):
    path: str
    old_text: str
    new_text: str


class RunnerAppliedOperation(TypedDict):
    path: str
    old_text_hash: str
    new_text_hash: str
    replacement_count: int


class RunnerExecutionResult(TypedDict):
    summary: str
    changed_files: list[str]
    operations: list[RunnerAppliedOperation]
    applied: bool
    dry_run: bool


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _resolve_repo_file(repo_root: Path, repo_path: str) -> Path:
    root = repo_root.resolve()
    path = (root / repo_path).resolve()

    if root != path and root not in path.parents:
        raise PermissionError(f"runner patch path escapes repository: {repo_path}")

    if not path.is_file():
        raise FileNotFoundError(f"runner patch target not found: {repo_path}")

    return path


def apply_text_patch_operations(
    operations: list[RunnerTextPatchOperation],
    *,
    repo_root: Path | str = ".",
    dry_run: bool = False,
) -> RunnerExecutionResult:
    if not operations:
        return {
            "summary": "No runner patch operations were requested.",
            "changed_files": [],
            "operations": [],
            "applied": False,
            "dry_run": dry_run,
        }

    normalized_operations: list[RunnerTextPatchOperation] = []
    changed_files: list[str] = []

    for operation in operations:
        path = normalize_repo_path(operation["path"])
        old_text = operation["old_text"]

        if not old_text:
            raise ValueError(f"runner patch old_text cannot be empty: {path}")

        normalized_operations.append(
            {
                "path": path,
                "old_text": old_text,
                "new_text": operation["new_text"],
            }
        )
        if path not in changed_files:
            changed_files.append(path)

    require_change_scope_allowed(changed_files)

    root = Path(repo_root)
    staged_contents: dict[Path, str] = {}
    applied_operations: list[RunnerAppliedOperation] = []

    for operation in normalized_operations:
        target_path = _resolve_repo_file(root, operation["path"])
        content = staged_contents.get(target_path)
        if content is None:
            content = target_path.read_text(encoding="utf-8")

        replacement_count = content.count(operation["old_text"])

        if replacement_count != 1:
            raise ValueError(
                "runner patch requires old_text to match exactly once: "
                f"{operation['path']} matched {replacement_count} times"
            )

        updated_content = content.replace(
            operation["old_text"],
            operation["new_text"],
            1,
        )
        staged_contents[target_path] = updated_content
        applied_operations.append(
            {
                "path": operation["path"],
                "old_text_hash": _hash_text(operation["old_text"]),
                "new_text_hash": _hash_text(operation["new_text"]),
                "replacement_count": replacement_count,
            }
        )

    if not dry_run:
        for target_path, updated_content in staged_contents.items():
            target_path.write_text(updated_content, encoding="utf-8")

    return {
        "summary": (
            f"Applied {len(applied_operations)} controlled text patch operation(s)."
            if not dry_run
            else f"Validated {len(applied_operations)} controlled text patch operation(s)."
        ),
        "changed_files": changed_files,
        "operations": applied_operations,
        "applied": not dry_run,
        "dry_run": dry_run,
    }


def build_implementation_result_from_execution(
    execution_result: RunnerExecutionResult,
) -> dict[str, Any]:
    return {
        "summary": execution_result["summary"],
        "changed_files": execution_result["changed_files"],
        "risk": "Controlled text patch execution within runner boundary policy.",
        "runner_execution": execution_result,
    }

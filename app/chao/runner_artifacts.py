import json
from pathlib import Path
from typing import Any

from app.chao.runner_policy import RunnerBranchPlan, build_runner_branch_plan

PATCH_RECORDS_DIR = Path(".ai-agents/records/patches")
FAILURE_RECORDS_DIR = Path(".ai-agents/records/failures")


def _format_json(data: Any) -> str:
    return json.dumps(data or {}, ensure_ascii=False, indent=2)


def _format_list(items: list[str]) -> str:
    if not items:
        return "- 无"
    return "\n".join(f"- {item}" for item in items)


def build_patch_artifact_markdown(
    task: dict[str, Any],
    branch_plan: RunnerBranchPlan,
) -> str:
    task_code = task["task_code"]
    implementation_result = task.get("implementation_result", {})
    validation_result = task.get("validation_result", {})
    changed_files = implementation_result.get("changed_files", [])

    lines = [
        f"# {task_code} - Runner Patch Artifact",
        "",
        "## 任务基础信息",
        "",
        "| 字段 | 内容 |",
        "|---|---|",
        f"| 任务编号 | {task_code} |",
        f"| 标题 | {task.get('title', '')} |",
        f"| 任务等级 | {task.get('task_level', '')} |",
        f"| 当前状态 | {task.get('status', '')} |",
        "",
        "## 分支计划",
        "",
        "```json",
        _format_json(branch_plan),
        "```",
        "",
        "## 修改文件",
        "",
        _format_list(changed_files),
        "",
        "## 工部结果",
        "",
        "```json",
        _format_json(implementation_result),
        "```",
        "",
        "## 刑部验证结果",
        "",
        "```json",
        _format_json(validation_result),
        "```",
        "",
        "## Patch 结论",
        "",
        "- 当前 MVP 未生成真实 diff patch。",
        "- 本 artifact 记录执行分支计划、变更范围和验证证据。",
        "- 后续真实 Runner 必须在此基础上附加实际 patch 内容。",
        "",
    ]

    return "\n".join(lines)


def save_patch_artifact(task: dict[str, Any]) -> Path:
    PATCH_RECORDS_DIR.mkdir(parents=True, exist_ok=True)

    task_code = task["task_code"]
    branch_plan = build_runner_branch_plan(
        task_code=task_code,
        title=task.get("title", ""),
        task_level=task.get("task_level", "L1"),
    )
    path = PATCH_RECORDS_DIR / f"{task_code}-patch.md"
    content = build_patch_artifact_markdown(
        task=task,
        branch_plan=branch_plan,
    )
    path.write_text(content, encoding="utf-8")

    return path


def build_failure_feedback_artifact_markdown(
    task: dict[str, Any],
    branch_plan: RunnerBranchPlan,
) -> str:
    task_code = task["task_code"]
    implementation_result = task.get("implementation_result", {})
    validation_result = task.get("validation_result", {})
    failed_results = [
        result
        for result in validation_result.get("command_results", [])
        if result.get("exit_code") != 0
    ]

    lines = [
        f"# {task_code} - Runner Failure Feedback",
        "",
        "## 任务基础信息",
        "",
        "| 字段 | 内容 |",
        "|---|---|",
        f"| 任务编号 | {task_code} |",
        f"| 标题 | {task.get('title', '')} |",
        f"| 任务等级 | {task.get('task_level', '')} |",
        f"| 当前状态 | {task.get('status', '')} |",
        "",
        "## 分支计划",
        "",
        "```json",
        _format_json(branch_plan),
        "```",
        "",
        "## 失败验证项",
        "",
        "```json",
        _format_json(failed_results),
        "```",
        "",
        "## 工部回流建议",
        "",
        "- 当前任务禁止交付。",
        "- 工部必须根据失败 gate、命令和输出摘要修复后重新验证。",
        "- 修复范围仍必须满足 Agent Runner allowed scope。",
        "- 修复后必须生成新的验证证据和 patch artifact。",
        "",
        "## 工部结果",
        "",
        "```json",
        _format_json(implementation_result),
        "```",
        "",
        "## 刑部验证结果",
        "",
        "```json",
        _format_json(validation_result),
        "```",
        "",
    ]

    return "\n".join(lines)


def save_failure_feedback_artifact(task: dict[str, Any]) -> Path:
    FAILURE_RECORDS_DIR.mkdir(parents=True, exist_ok=True)

    task_code = task["task_code"]
    branch_plan = build_runner_branch_plan(
        task_code=task_code,
        title=task.get("title", ""),
        task_level=task.get("task_level", "L1"),
    )
    path = FAILURE_RECORDS_DIR / f"{task_code}-failure-feedback.md"
    content = build_failure_feedback_artifact_markdown(
        task=task,
        branch_plan=branch_plan,
    )
    path.write_text(content, encoding="utf-8")

    return path

from pathlib import Path
from typing import Any

REVIEW_RECORDS_DIR = Path(".ai-agents/records/reviews")


def _format_value(value: Any) -> str:
    if value is None or value == "":
        return "无"
    return str(value)


def build_review_artifact_markdown(
    task: dict[str, Any],
    design_artifact_uri: str,
    reviewer: str = "menxia",
) -> str:
    task_code = task["task_code"]

    lines = [
        f"# {task_code} - 门下省审核",
        "",
        "## 任务基础信息",
        "",
        "| 字段 | 内容 |",
        "|---|---|",
        f"| 任务编号 | {task_code} |",
        f"| 标题 | {_format_value(task.get('title'))} |",
        f"| 任务等级 | {_format_value(task.get('task_level'))} |",
        f"| 当前状态 | {_format_value(task.get('status'))} |",
        f"| 审核角色 | {_format_value(reviewer)} |",
        f"| 方案 artifact | {_format_value(design_artifact_uri)} |",
        "",
        "## 审核边界",
        "",
        "- 本文件记录 L3 / A 级任务的门下省审核框架。",
        "- 审核对象是中书省方案 artifact 与后续实现计划。",
        "- 审核不得写入 Secret、生产数据、个人隐私或未脱敏样例数据。",
        "",
        "## 审核检查项",
        "",
        "- 方案是否匹配原始需求：待审核。",
        "- 风险定级是否充分：待审核。",
        "- 数据边界是否明确：待审核。",
        "- 验证命令是否完整：待审核。",
        "- 回滚方案是否可执行：待审核。",
        "- 是否需要拆分子任务：待审核。",
        "",
        "## 审核结论",
        "",
        "- 状态：PENDING_REVIEW",
        "- 结论：待门下省补充。",
        "",
    ]

    return "\n".join(lines)


def save_review_artifact(
    task: dict[str, Any],
    design_artifact_uri: str,
    reviewer: str = "menxia",
) -> Path:
    REVIEW_RECORDS_DIR.mkdir(parents=True, exist_ok=True)

    task_code = task["task_code"]
    path = REVIEW_RECORDS_DIR / f"{task_code}-review.md"
    content = build_review_artifact_markdown(
        task=task,
        design_artifact_uri=design_artifact_uri,
        reviewer=reviewer,
    )
    path.write_text(content, encoding="utf-8")

    return path

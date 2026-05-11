from pathlib import Path
from typing import Any

HUBU_RECORDS_DIR = Path(".ai-agents/records/hubu")


def _format_value(value: Any) -> str:
    if value is None or value == "":
        return "无"
    return str(value)


def build_hubu_artifact_markdown(
    task: dict[str, Any],
    design_artifact_uri: str,
    review_artifact_uri: str,
    reviewer: str = "hubu",
) -> str:
    task_code = task["task_code"]

    lines = [
        f"# {task_code} - 户部审查",
        "",
        "## 任务基础信息",
        "",
        "| 字段 | 内容 |",
        "|---|---|",
        f"| 任务编号 | {task_code} |",
        f"| 标题 | {_format_value(task.get('title'))} |",
        f"| 任务等级 | {_format_value(task.get('task_level'))} |",
        f"| 当前状态 | {_format_value(task.get('status'))} |",
        f"| 审查角色 | {_format_value(reviewer)} |",
        f"| 方案 artifact | {_format_value(design_artifact_uri)} |",
        f"| 门下省审核 artifact | {_format_value(review_artifact_uri)} |",
        "",
        "## 审查边界",
        "",
        "- 本文件记录 L3 / A 级任务的数据、依赖和 Secret 风险审查框架。",
        "- 审查对象包括存储位置、数据分级、向量化范围、依赖变化和 Secret 注入方式。",
        "- 审查不得写入 Secret、生产数据、个人隐私或未脱敏样例数据。",
        "",
        "## 数据边界检查项",
        "",
        "- 新增存储位置：待审查。",
        "- 数据分级是否明确：待审查。",
        "- 是否允许进入 PostgreSQL：待审查。",
        "- 是否允许进入 Markdown：待审查。",
        "- 是否允许进入 pgvector：待审查。",
        "- 保留周期是否明确：待审查。",
        "",
        "## 依赖与 Secret 检查项",
        "",
        "- 是否新增依赖：待审查。",
        "- 依赖来源是否可信：待审查。",
        "- 是否新增 Secret 注入方式：待审查。",
        "- 是否触及 .env、日志、生产数据或私钥：待审查。",
        "",
        "## 审查结论",
        "",
        "- 状态：PENDING_HUBU_REVIEW",
        "- 结论：待户部补充。",
        "",
    ]

    return "\n".join(lines)


def save_hubu_artifact(
    task: dict[str, Any],
    design_artifact_uri: str,
    review_artifact_uri: str,
    reviewer: str = "hubu",
) -> Path:
    HUBU_RECORDS_DIR.mkdir(parents=True, exist_ok=True)

    task_code = task["task_code"]
    path = HUBU_RECORDS_DIR / f"{task_code}-hubu.md"
    content = build_hubu_artifact_markdown(
        task=task,
        design_artifact_uri=design_artifact_uri,
        review_artifact_uri=review_artifact_uri,
        reviewer=reviewer,
    )
    path.write_text(content, encoding="utf-8")

    return path

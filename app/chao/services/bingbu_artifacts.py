from pathlib import Path
from typing import Any

BINGBU_RECORDS_DIR = Path(".ai-agents/records/bingbu")


def _format_value(value: Any) -> str:
    if value is None or value == "":
        return "无"
    return str(value)


def build_bingbu_artifact_markdown(
    task: dict[str, Any],
    design_artifact_uri: str,
    review_artifact_uri: str,
    hubu_artifact_uri: str,
    reviewer: str = "bingbu",
) -> str:
    task_code = task["task_code"]

    lines = [
        f"# {task_code} - 兵部审查",
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
        f"| 户部审查 artifact | {_format_value(hubu_artifact_uri)} |",
        "",
        "## 审查边界",
        "",
        "- 本文件记录 L3 / A 级任务的部署、CI 和 rollback 审查框架。",
        "- 审查对象包括执行环境、验证命令、CI 门禁、回滚步骤和阻断条件。",
        "- 审查不得写入 Secret、生产数据、个人隐私或未脱敏样例数据。",
        "",
        "## 部署与 CI 检查项",
        "",
        "- 是否需要部署窗口：待审查。",
        "- 是否影响运行环境或 Docker 服务：待审查。",
        "- CI 门禁是否覆盖 ruff、pytest、schema 和 data-boundary：待审查。",
        "- Ubuntu 验证命令是否明确：待审查。",
        "- 是否需要人工复核日志或指标：待审查。",
        "",
        "## Rollback 检查项",
        "",
        "- 回滚入口是否明确：待审查。",
        "- 数据回滚是否可执行：待审查。",
        "- 配置回滚是否可执行：待审查。",
        "- 交付阻断条件是否明确：待审查。",
        "",
        "## 审查结论",
        "",
        "- 状态：PENDING_BINGBU_REVIEW",
        "- 结论：待兵部补充。",
        "",
    ]

    return "\n".join(lines)


def save_bingbu_artifact(
    task: dict[str, Any],
    design_artifact_uri: str,
    review_artifact_uri: str,
    hubu_artifact_uri: str,
    reviewer: str = "bingbu",
) -> Path:
    BINGBU_RECORDS_DIR.mkdir(parents=True, exist_ok=True)

    task_code = task["task_code"]
    path = BINGBU_RECORDS_DIR / f"{task_code}-bingbu.md"
    content = build_bingbu_artifact_markdown(
        task=task,
        design_artifact_uri=design_artifact_uri,
        review_artifact_uri=review_artifact_uri,
        hubu_artifact_uri=hubu_artifact_uri,
        reviewer=reviewer,
    )
    path.write_text(content, encoding="utf-8")

    return path

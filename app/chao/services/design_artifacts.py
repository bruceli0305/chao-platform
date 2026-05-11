from pathlib import Path
from typing import Any

DESIGN_RECORDS_DIR = Path(".ai-agents/records/designs")


def _format_value(value: Any) -> str:
    if value is None or value == "":
        return "无"
    return str(value)


def build_design_artifact_markdown(
    task: dict[str, Any],
    confirmed_by: str,
    note: str = "",
) -> str:
    task_code = task["task_code"]

    lines = [
        f"# {task_code} - 中书省方案",
        "",
        "## 任务基础信息",
        "",
        "| 字段 | 内容 |",
        "|---|---|",
        f"| 任务编号 | {task_code} |",
        f"| 标题 | {_format_value(task.get('title'))} |",
        f"| 任务等级 | {_format_value(task.get('task_level'))} |",
        f"| 当前状态 | {_format_value(task.get('status'))} |",
        f"| 确认人 | {_format_value(confirmed_by)} |",
        f"| 确认说明 | {_format_value(note)} |",
        "",
        "## 原始需求",
        "",
        _format_value(task.get("raw_request")),
        "",
        "## 方案边界",
        "",
        "- 本文件仅记录 L3 / A 级任务进入 DESIGNING 后的方案框架。",
        "- 具体代码变更必须在后续执行阶段完成，并保留验证证据。",
        "- 不得在本文件写入 Secret、生产数据、个人隐私或未脱敏样例数据。",
        "",
        "## 设计检查项",
        "",
        "- 变更目标：待补充。",
        "- 影响范围：待补充。",
        "- 数据边界：待补充。",
        "- 依赖变化：待补充。",
        "- 验证命令：待补充。",
        "- 回滚方案：待补充。",
        "",
        "## 后续治理",
        "",
        "- 门下省审核：待生成审核 artifact。",
        "- 户部审查：待检查数据、依赖和 Secret 风险。",
        "- 兵部审查：待检查部署、CI 和 rollback。",
        "",
    ]

    return "\n".join(lines)


def save_design_artifact(
    task: dict[str, Any],
    confirmed_by: str,
    note: str = "",
) -> Path:
    DESIGN_RECORDS_DIR.mkdir(parents=True, exist_ok=True)

    task_code = task["task_code"]
    path = DESIGN_RECORDS_DIR / f"{task_code}-design.md"
    content = build_design_artifact_markdown(
        task=task,
        confirmed_by=confirmed_by,
        note=note,
    )
    path.write_text(content, encoding="utf-8")

    return path

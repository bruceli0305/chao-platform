from pathlib import Path
from typing import Any

MILESTONE_RECORDS_DIR = Path(".ai-agents/records/milestones")


def _format_value(value: Any) -> str:
    if value is None or value == "":
        return "无"
    return str(value)


def build_milestone_artifact_markdown(task: dict[str, Any]) -> str:
    task_code = task["task_code"]

    lines = [
        f"# {task_code} - L4 里程碑规划",
        "",
        "## 任务基础信息",
        "",
        "| 字段 | 内容 |",
        "|---|---|",
        f"| 任务编号 | {task_code} |",
        f"| 标题 | {_format_value(task.get('title'))} |",
        f"| 任务等级 | {_format_value(task.get('task_level'))} |",
        f"| 当前状态 | {_format_value(task.get('status'))} |",
        "",
        "## 原始需求",
        "",
        _format_value(task.get("raw_request")),
        "",
        "## L4 执行边界",
        "",
        "- L4 任务只生成里程碑规划，不直接进入工部执行。",
        "- 后续实施必须拆分为多个 L2 / L3 子任务，并分别走路由、审批和验证。",
        "- 本文件不得写入 Secret、生产数据、个人隐私或未脱敏样例数据。",
        "",
        "## 里程碑草案",
        "",
        "- M1：范围澄清与验收标准确认。",
        "- M2：方案拆解为 L2 / L3 子任务。",
        "- M3：高风险子任务完成 A 级确认和治理 artifact。",
        "- M4：逐项实施、验证、回滚预案和交付证据归档。",
        "",
        "## 子任务拆解要求",
        "",
        "- 每个子任务必须有独立 task_code。",
        "- 每个 L3 子任务必须生成方案、审核、数据审查和部署审查 artifact。",
        "- 每个子任务必须有明确验证命令和交付证据。",
        "",
        "## 当前结论",
        "",
        "- 状态：MILESTONE_ONLY",
        "- 结论：等待人工确认和后续拆分，不直接执行实现。",
        "",
    ]

    return "\n".join(lines)


def save_milestone_artifact(task: dict[str, Any]) -> Path:
    MILESTONE_RECORDS_DIR.mkdir(parents=True, exist_ok=True)

    task_code = task["task_code"]
    path = MILESTONE_RECORDS_DIR / f"{task_code}-milestones.md"
    content = build_milestone_artifact_markdown(task=task)
    path.write_text(content, encoding="utf-8")

    return path

import json
from pathlib import Path
from typing import Any

TASK_RECORDS_DIR = Path(".ai-agents/records/tasks")


def _format_list(items: list[str]) -> str:
    if not items:
        return "- 无"
    return "\n".join(f"- {item}" for item in items)


def _format_json(data: Any) -> str:
    return json.dumps(data or {}, ensure_ascii=False, indent=2)


def _format_skill_details(skills: list[dict[str, Any]]) -> str:
    if not skills:
        return "- 无"
    return "\n".join(f"- {skill['name']}：{skill['path']}" for skill in skills)


def _format_skill_usage(skill_usage: list[dict[str, Any]]) -> str:
    if not skill_usage:
        return "- none"

    lines = []
    for skill in skill_usage:
        lines.append(
            f"- {skill.get('name', '')}: {skill.get('path', '')}; "
            f"status={skill.get('status', '')}; "
            f"sha256={skill.get('content_sha256', '')}"
        )
    return "\n".join(lines)


def _format_skill_execution_plan(plan: dict[str, Any]) -> str:
    if not plan:
        return "- none"

    lines = [
        f"- status: {plan.get('status', '')}",
        "- combined_gates: " + ", ".join(plan.get("combined_gates", [])),
    ]

    for skill in plan.get("skills", []):
        lines.append(
            f"- {skill.get('name', '')}: gates={', '.join(skill.get('default_gates', []))}; "
            f"status={skill.get('status', '')}; "
            f"sha256={skill.get('content_sha256', '')}"
        )

    return "\n".join(lines)


def save_task_markdown(result: dict[str, Any]) -> Path:
    TASK_RECORDS_DIR.mkdir(parents=True, exist_ok=True)

    task_code = result["task_code"]
    path = TASK_RECORDS_DIR / f"{task_code}.md"

    historian_records = result.get("historian_records", [])

    if historian_records:
        records_md = "\n\n".join(
            [
                "\n".join(
                    [
                        f"### {record.get('type', 'unknown')}",
                        "",
                        f"- 时间：{record.get('created_at', '')}",
                        f"- 内容：{record.get('content', '')}",
                    ]
                )
                for record in historian_records
            ]
        )
    else:
        records_md = "无"

    can_continue = (
        "否，需要皇帝确认"
        if result.get("status") == "NEED_CONFIRMATION"
        else "是，本地 MVP 流程已完成"
    )

    lines = [
        f"# {task_code} - {result.get('title', '')}",
        "",
        "## 任务基础信息",
        "",
        "| 字段 | 内容 |",
        "|---|---|",
        f"| 任务编号 | {task_code} |",
        f"| 标题 | {result.get('title', '')} |",
        f"| 任务等级 | {result.get('task_level', '')} |",
        f"| 当前状态 | {result.get('status', '')} |",
        f"| 确认等级 | {result.get('required_confirmation', '')} |",
        "",
        "## 原始需求",
        "",
        result.get("raw_request", ""),
        "",
        "## 定级依据",
        "",
        result.get("level_reason", ""),
        "",
        "## 风险类型",
        "",
        _format_list(result.get("risk_types", [])),
        "",
        "## 启用角色",
        "",
        _format_list(result.get("required_agents", [])),
        "",
        "## 工程门禁",
        "",
        _format_list(result.get("required_gates", [])),
        "",
        "## Skills",
        "",
        _format_skill_details(result.get("required_skill_details", [])),
        "",
        "## Skill Usage",
        "",
        _format_skill_usage(result.get("skill_usage", [])),
        "",
        "## Skill Execution Plan",
        "",
        _format_skill_execution_plan(result.get("skill_execution_plan", {})),
        "",
        "## 路由结果",
        "",
        "```json",
        _format_json(result.get("route_result")),
        "```",
        "",
        "## 工部结果",
        "",
        "```json",
        _format_json(result.get("implementation_result")),
        "```",
        "",
        "## 刑部验证结果",
        "",
        "```json",
        _format_json(result.get("validation_result")),
        "```",
        "",
        "## 史官记录",
        "",
        records_md,
        "",
        "## 当前结论",
        "",
        f"- 状态：{result.get('status', '')}",
        f"- 是否可继续：{can_continue}",
        (
            "- 说明：当前 MVP 阶段暂不自动修改真实代码，"
            "只验证任务路由、状态流转、记录落库和 Markdown 双写。"
        ),
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path

from typing import Literal, TypedDict

from app.chao.state import TaskLevel

ToolRisk = Literal["low", "medium", "high", "critical"]


class ToolDefinition(TypedDict):
    name: str
    category: str
    risk: ToolRisk
    description: str
    permission_policy: str


class PermissionDecision(TypedDict):
    allowed: bool
    permission_policy: str
    reason: str
    requires_confirmation: bool
    risk_flag: str | None


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "cli.new": {
        "name": "cli.new",
        "category": "postgres.write",
        "risk": "medium",
        "description": "创建任务并写入路由、史官记录和审计链。",
        "permission_policy": "local-cli-task-create",
    },
    "cli.approve": {
        "name": "cli.approve",
        "category": "approval.write",
        "risk": "high",
        "description": "记录 A 级确认并推进任务状态。",
        "permission_policy": "human-approval-required",
    },
    "schema_check": {
        "name": "schema_check",
        "category": "postgres.read",
        "risk": "medium",
        "description": "读取数据库结构并验证 schema 门禁。",
        "permission_policy": "schema-read-validation",
    },
    "data_boundary_check": {
        "name": "data_boundary_check",
        "category": "filesystem.read",
        "risk": "medium",
        "description": "扫描 Git 跟踪文件、边界路径和疑似 Secret。",
        "permission_policy": "data-boundary-validation",
    },
}

ROLE_ALLOWED_TOOLS: dict[str, set[str]] = {
    "shangshu": {"cli.new"},
    "emperor": {"cli.approve"},
    "xingbu": {"schema_check", "data_boundary_check"},
    "hubu": {"data_boundary_check"},
    "menxia": {"schema_check", "data_boundary_check"},
}

LEVEL_ALLOWED_RISKS: dict[TaskLevel, set[ToolRisk]] = {
    "L1": {"low", "medium"},
    "L2": {"low", "medium"},
    "L3": {"low", "medium", "high"},
    "L4": {"low"},
}


def list_tools() -> list[ToolDefinition]:
    return list(TOOL_REGISTRY.values())


def get_tool(tool_name: str) -> ToolDefinition:
    return TOOL_REGISTRY[tool_name]


def evaluate_tool_permission(
    *,
    agent_name: str,
    tool_name: str,
    task_level: TaskLevel,
    required_confirmation: str,
    current_status: str,
) -> PermissionDecision:
    tool = TOOL_REGISTRY.get(tool_name)

    if tool is None:
        return {
            "allowed": False,
            "permission_policy": "unknown-tool",
            "reason": f"工具未登记：{tool_name}",
            "requires_confirmation": True,
            "risk_flag": "UNKNOWN_TOOL",
        }

    if tool_name not in ROLE_ALLOWED_TOOLS.get(agent_name, set()):
        return {
            "allowed": False,
            "permission_policy": "role-tool-denied",
            "reason": f"角色 {agent_name} 未授权调用 {tool_name}。",
            "requires_confirmation": tool["risk"] in {"high", "critical"},
            "risk_flag": "ROLE_TOOL_DENIED",
        }

    if tool["risk"] not in LEVEL_ALLOWED_RISKS[task_level]:
        return {
            "allowed": False,
            "permission_policy": "level-risk-denied",
            "reason": f"{task_level} 不允许调用 {tool['risk']} 风险工具。",
            "requires_confirmation": True,
            "risk_flag": "LEVEL_RISK_DENIED",
        }

    if (
        tool["risk"] == "high"
        and required_confirmation == "A"
        and current_status != "NEED_CONFIRMATION"
    ):
        return {
            "allowed": False,
            "permission_policy": "a-confirmation-required",
            "reason": "高风险工具必须在 A 级确认等待态中由人工确认。",
            "requires_confirmation": True,
            "risk_flag": "A_CONFIRMATION_REQUIRED",
        }

    return {
        "allowed": True,
        "permission_policy": tool["permission_policy"],
        "reason": "工具调用符合角色、等级和确认策略。",
        "requires_confirmation": tool["risk"] in {"high", "critical"},
        "risk_flag": "A_CONFIRMATION" if tool["risk"] == "high" else None,
    }


def require_tool_permission(
    *,
    agent_name: str,
    tool_name: str,
    task_level: TaskLevel,
    required_confirmation: str,
    current_status: str,
) -> PermissionDecision:
    decision = evaluate_tool_permission(
        agent_name=agent_name,
        tool_name=tool_name,
        task_level=task_level,
        required_confirmation=required_confirmation,
        current_status=current_status,
    )

    if not decision["allowed"]:
        raise PermissionError(decision["reason"])

    return decision

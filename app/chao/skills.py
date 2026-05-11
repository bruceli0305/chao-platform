from typing import Literal, TypedDict

from app.chao.state import TaskLevel

SkillName = Literal[
    "bugfix",
    "frontend-feature",
    "api-development",
    "database-migration",
    "security-review",
    "docs-generation",
    "release-validation",
]


class SkillDefinition(TypedDict):
    name: SkillName
    description: str
    path: str
    default_gates: list[str]
    trigger_keywords: list[str]


SKILL_REGISTRY: dict[SkillName, SkillDefinition] = {
    "bugfix": {
        "name": "bugfix",
        "description": "Bug 复现、定位、修复、回归验证。",
        "path": ".ai-agents/skills/bugfix/SKILL.md",
        "default_gates": ["lint", "test", "manual_validation"],
        "trigger_keywords": ["修复", "bug", "Bug", "报错", "失败", "异常", "回归"],
    },
    "frontend-feature": {
        "name": "frontend-feature",
        "description": "前端页面、组件、交互、样式和状态管理开发。",
        "path": ".ai-agents/skills/frontend-feature/SKILL.md",
        "default_gates": ["typecheck", "lint", "build", "manual_validation"],
        "trigger_keywords": ["页面", "前端", "组件", "交互", "样式", "表单", "列表", "弹窗"],
    },
    "api-development": {
        "name": "api-development",
        "description": "API 契约、接口实现、异常路径和接口验证。",
        "path": ".ai-agents/skills/api-development/SKILL.md",
        "default_gates": ["lint", "test", "manual_validation"],
        "trigger_keywords": ["接口", "API", "api", "端点", "请求", "响应"],
    },
    "database-migration": {
        "name": "database-migration",
        "description": "数据库结构、迁移脚本、备份、回滚和验证。",
        "path": ".ai-agents/skills/database-migration/SKILL.md",
        "default_gates": ["schema_check", "test", "manual_validation"],
        "trigger_keywords": [
            "数据库",
            "迁移",
            "数据表",
            "表结构",
            "建表",
            "改表",
            "字段迁移",
            "索引",
            "SQL",
            "schema",
        ],
    },
    "security-review": {
        "name": "security-review",
        "description": "权限、越权、Secret、敏感字段和安全边界审查。",
        "path": ".ai-agents/skills/security-review/SKILL.md",
        "default_gates": ["secret_scan", "data_boundary_check", "manual_validation"],
        "trigger_keywords": ["权限", "鉴权", "认证", "Secret", "密钥", "Token", "安全", "越权"],
    },
    "docs-generation": {
        "name": "docs-generation",
        "description": "README、API 文档、用户说明、发布说明生成。",
        "path": ".ai-agents/skills/docs-generation/SKILL.md",
        "default_gates": ["lint", "manual_validation"],
        "trigger_keywords": ["文档", "README", "说明", "变更记录", "发布说明"],
    },
    "release-validation": {
        "name": "release-validation",
        "description": "发布前检查、构建产物、健康检查和回滚确认。",
        "path": ".ai-agents/skills/release-validation/SKILL.md",
        "default_gates": ["build", "test", "manual_validation"],
        "trigger_keywords": ["发布", "上线", "部署", "CI", "构建", "回滚"],
    },
}

SKILL_LIMITS: dict[TaskLevel, int] = {
    "L1": 1,
    "L2": 3,
    "L3": len(SKILL_REGISTRY),
    "L4": 0,
}


def get_skill(name: SkillName) -> SkillDefinition:
    return SKILL_REGISTRY[name]


def list_skills() -> list[SkillDefinition]:
    return list(SKILL_REGISTRY.values())


def select_required_skills(raw_request: str, task_level: TaskLevel) -> list[SkillName]:
    if task_level == "L4":
        return []

    matched: list[SkillName] = []

    for name, definition in SKILL_REGISTRY.items():
        if any(keyword in raw_request for keyword in definition["trigger_keywords"]):
            matched.append(name)

    if not matched and task_level in {"L1", "L2"}:
        matched.append("bugfix")

    return matched[: SKILL_LIMITS[task_level]]

import tomllib
from pathlib import Path
from typing import TypedDict

from app.chao.permissions import TOOL_REGISTRY
from app.chao.skills import SKILL_REGISTRY

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AGENTS_CONFIG_PATH = REPO_ROOT / "config" / "agents.toml"
SELF_UPGRADE_REQUIRED_SKILLS = [
    "bugfix",
    "security-review",
    "release-validation",
    "docs-generation",
]


class AgentDefinition(TypedDict):
    name: str
    title: str
    branch: str
    department: str
    role_type: str
    runtime_ready: bool
    required_for_self_upgrade: bool
    role_doc: str
    default_tools: list[str]
    owned_skills: list[str]


class AgentRegistry(TypedDict):
    required_self_upgrade_agents: list[str]
    agents: dict[str, AgentDefinition]


def _as_string(value: object, field_name: str, agent_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{agent_name}: {field_name} is required")
    return value


def _as_string_list(value: object, field_name: str, agent_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{agent_name}: {field_name} must be a list of strings")
    return value


def _as_bool(value: object, field_name: str, agent_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{agent_name}: {field_name} must be a boolean")
    return value


def _build_agent_definition(agent_name: str, data: dict[str, object]) -> AgentDefinition:
    return {
        "name": agent_name,
        "title": _as_string(data.get("title"), "title", agent_name),
        "branch": _as_string(data.get("branch"), "branch", agent_name),
        "department": _as_string(data.get("department"), "department", agent_name),
        "role_type": _as_string(data.get("role_type"), "role_type", agent_name),
        "runtime_ready": _as_bool(data.get("runtime_ready"), "runtime_ready", agent_name),
        "required_for_self_upgrade": _as_bool(
            data.get("required_for_self_upgrade"),
            "required_for_self_upgrade",
            agent_name,
        ),
        "role_doc": _as_string(data.get("role_doc"), "role_doc", agent_name),
        "default_tools": _as_string_list(
            data.get("default_tools", []), "default_tools", agent_name
        ),
        "owned_skills": _as_string_list(data.get("owned_skills", []), "owned_skills", agent_name),
    }


def load_agent_registry(config_path: Path | None = None) -> AgentRegistry:
    resolved_path = config_path or DEFAULT_AGENTS_CONFIG_PATH
    data = tomllib.loads(resolved_path.read_text(encoding="utf-8"))
    required_self_upgrade_agents = _as_string_list(
        data.get("required_self_upgrade_agents", []),
        "required_self_upgrade_agents",
        str(resolved_path),
    )
    raw_agents = data.get("agents")
    if not isinstance(raw_agents, dict) or not raw_agents:
        raise ValueError(f"{resolved_path}: agents table is required")

    agents = {}
    for agent_name, agent_data in raw_agents.items():
        if not isinstance(agent_name, str):
            raise ValueError(f"{resolved_path}: agent names must be strings")
        if not isinstance(agent_data, dict):
            raise ValueError(f"{resolved_path}: agents.{agent_name} must be a table")
        agents[agent_name] = _build_agent_definition(agent_name, agent_data)

    return {
        "required_self_upgrade_agents": required_self_upgrade_agents,
        "agents": agents,
    }


def list_agents() -> list[AgentDefinition]:
    return list(load_agent_registry()["agents"].values())


def get_agent(name: str) -> AgentDefinition:
    registry = load_agent_registry()["agents"]
    try:
        return registry[name]
    except KeyError as exc:
        raise ValueError(f"unsupported agent: {name}") from exc


def validate_agent_registry(config_path: Path | None = None) -> list[str]:
    try:
        registry = load_agent_registry(config_path)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return [str(exc)]

    errors = []
    agents = registry["agents"]

    for agent_name in registry["required_self_upgrade_agents"]:
        if agent_name not in agents:
            errors.append(f"missing self-upgrade agent: {agent_name}")

    for agent in agents.values():
        role_doc = REPO_ROOT / agent["role_doc"]
        if not role_doc.is_file():
            errors.append(f"{agent['name']}: role_doc not found: {agent['role_doc']}")
        for tool_name in agent["default_tools"]:
            if tool_name not in TOOL_REGISTRY:
                errors.append(f"{agent['name']}: unknown default tool: {tool_name}")
        for skill_name in agent["owned_skills"]:
            if skill_name not in SKILL_REGISTRY:
                errors.append(f"{agent['name']}: unknown owned skill: {skill_name}")

    return errors


def validate_self_upgrade_readiness() -> list[str]:
    errors = validate_agent_registry()
    if errors:
        return errors

    registry = load_agent_registry()
    agents = registry["agents"]

    for agent_name in registry["required_self_upgrade_agents"]:
        agent = agents[agent_name]
        if not agent["runtime_ready"]:
            errors.append(f"self-upgrade agent is not runtime ready: {agent_name}")
        if not agent["required_for_self_upgrade"]:
            errors.append(f"self-upgrade agent is not marked required: {agent_name}")

    for skill_name in SELF_UPGRADE_REQUIRED_SKILLS:
        skill = SKILL_REGISTRY.get(skill_name)
        if skill is None:
            errors.append(f"missing self-upgrade skill: {skill_name}")
            continue
        if skill["owner_agent"] != "gongbu":
            errors.append(
                f"self-upgrade skill must be owned by gongbu: {skill_name} "
                f"(owner={skill['owner_agent']})"
            )

    return errors

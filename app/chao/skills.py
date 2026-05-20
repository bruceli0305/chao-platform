import tomllib
from pathlib import Path
from typing import TypedDict

from app.chao.state import TaskLevel

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO_ROOT / ".ai-agents" / "skills"
SKILL_MANIFEST_NAME = "skill.toml"

SkillName = str


class SkillDefinition(TypedDict):
    name: str
    description: str
    path: str
    default_gates: list[str]
    trigger_keywords: list[str]
    allowed_task_levels: list[TaskLevel]


def _as_string_list(value: object, field_name: str, manifest_path: Path) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{manifest_path}: {field_name} must be a list of strings")

    return value


def _skill_doc_path(manifest_path: Path) -> str:
    return manifest_path.with_name("SKILL.md").relative_to(REPO_ROOT).as_posix()


def load_skill_manifest(manifest_path: Path) -> SkillDefinition | None:
    data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))

    if data.get("enabled", True) is False:
        return None

    name = data.get("name")
    description = data.get("description")

    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{manifest_path}: name is required")
    if name != manifest_path.parent.name:
        raise ValueError(f"{manifest_path}: name must match skill directory")
    if not isinstance(description, str) or not description.strip():
        raise ValueError(f"{manifest_path}: description is required")

    skill_path = manifest_path.with_name("SKILL.md")
    if not skill_path.is_file():
        raise FileNotFoundError(f"{manifest_path}: SKILL.md is required")

    allowed_task_levels = _as_string_list(
        data.get("allowed_task_levels", ["L1", "L2", "L3"]),
        "allowed_task_levels",
        manifest_path,
    )
    invalid_levels = sorted(set(allowed_task_levels) - {"L1", "L2", "L3", "L4"})
    if invalid_levels:
        raise ValueError(f"{manifest_path}: invalid task levels: {', '.join(invalid_levels)}")

    return {
        "name": name,
        "description": description,
        "path": _skill_doc_path(manifest_path),
        "default_gates": _as_string_list(
            data.get("default_gates", []),
            "default_gates",
            manifest_path,
        ),
        "trigger_keywords": _as_string_list(
            data.get("trigger_keywords", []),
            "trigger_keywords",
            manifest_path,
        ),
        "allowed_task_levels": allowed_task_levels,  # type: ignore[typeddict-item]
    }


def load_skill_registry(skills_root: Path = SKILLS_ROOT) -> dict[str, SkillDefinition]:
    registry = {}

    for manifest_path in sorted(skills_root.glob(f"*/{SKILL_MANIFEST_NAME}")):
        definition = load_skill_manifest(manifest_path)
        if definition is None:
            continue
        registry[definition["name"]] = definition

    return registry


def validate_skill_manifests(skills_root: Path = SKILLS_ROOT) -> list[str]:
    errors = []
    seen_names = set()

    for manifest_path in sorted(skills_root.glob(f"*/{SKILL_MANIFEST_NAME}")):
        try:
            definition = load_skill_manifest(manifest_path)
        except (FileNotFoundError, ValueError, tomllib.TOMLDecodeError) as exc:
            errors.append(str(exc))
            continue

        if definition is None:
            continue

        name = definition["name"]
        if name in seen_names:
            errors.append(f"{manifest_path}: duplicate skill name: {name}")
        seen_names.add(name)

        if not definition["default_gates"]:
            errors.append(f"{manifest_path}: default_gates must not be empty")
        if not definition["trigger_keywords"]:
            errors.append(f"{manifest_path}: trigger_keywords must not be empty")

    if not list(skills_root.glob(f"*/{SKILL_MANIFEST_NAME}")):
        errors.append(f"{skills_root}: no skill manifests found")

    return errors


SKILL_REGISTRY: dict[str, SkillDefinition] = load_skill_registry()

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


def describe_required_skills(skill_names: list[str]) -> list[SkillDefinition]:
    return [SKILL_REGISTRY[name] for name in skill_names if name in SKILL_REGISTRY]


def select_required_skills(raw_request: str, task_level: TaskLevel) -> list[SkillName]:
    if task_level == "L4":
        return []

    matched: list[SkillName] = []

    for name, definition in SKILL_REGISTRY.items():
        if task_level not in definition["allowed_task_levels"]:
            continue
        if any(keyword in raw_request for keyword in definition["trigger_keywords"]):
            matched.append(name)

    if not matched and task_level in {"L1", "L2"} and "bugfix" in SKILL_REGISTRY:
        matched.append("bugfix")

    return matched[: SKILL_LIMITS[task_level]]

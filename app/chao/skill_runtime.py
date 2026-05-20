import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from app.chao.state import ChaoState

REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_HEADINGS = 12


def _normalize_skill_path(path: str) -> Path:
    skill_path = (REPO_ROOT / path).resolve()
    skills_root = (REPO_ROOT / ".ai-agents" / "skills").resolve()

    if not skill_path.is_relative_to(skills_root):
        raise ValueError(f"skill path outside .ai-agents/skills: {path}")

    return skill_path


def _extract_headings(content: str) -> list[str]:
    headings = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            headings.append(stripped)

        if len(headings) >= MAX_HEADINGS:
            break

    return headings


def load_skill_usage(skill: dict[str, Any]) -> dict[str, Any]:
    path = skill["path"]
    skill_path = _normalize_skill_path(path)

    if not skill_path.is_file():
        raise FileNotFoundError(f"required skill file not found: {path}")

    content = skill_path.read_text(encoding="utf-8")

    return {
        "name": skill["name"],
        "path": path,
        "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "content_chars": len(content),
        "headings": _extract_headings(content),
        "loaded_at": datetime.now().isoformat(),
        "status": "loaded",
    }


def build_skill_execution_plan(
    *,
    required_gates: list[str],
    skill_details: list[dict[str, Any]],
    skill_usage: list[dict[str, Any]],
) -> dict[str, Any]:
    usage_by_name = {usage["name"]: usage for usage in skill_usage}
    combined_gates = list(dict.fromkeys(required_gates))
    skill_steps = []

    for skill in skill_details:
        usage = usage_by_name.get(skill["name"], {})
        default_gates = skill.get("default_gates", [])
        combined_gates = list(dict.fromkeys([*combined_gates, *default_gates]))
        skill_steps.append(
            {
                "name": skill["name"],
                "path": skill["path"],
                "status": usage.get("status", "missing"),
                "content_sha256": usage.get("content_sha256"),
                "default_gates": default_gates,
            }
        )

    return {
        "status": "ready" if skill_steps else "not_required",
        "skills": skill_steps,
        "combined_gates": combined_gates,
    }


def prepare_required_skills(state: ChaoState) -> ChaoState:
    skill_details = state.get("required_skill_details", [])

    if not skill_details:
        skill_execution_plan = build_skill_execution_plan(
            required_gates=state.get("required_gates", []),
            skill_details=[],
            skill_usage=[],
        )
        return {
            **state,
            "skill_usage": [],
            "skill_execution_plan": skill_execution_plan,
            "route_result": {
                **state.get("route_result", {}),
                "skill_usage": [],
                "skill_execution_plan": skill_execution_plan,
            },
        }

    skill_usage = [load_skill_usage(skill) for skill in skill_details]
    skill_execution_plan = build_skill_execution_plan(
        required_gates=state.get("required_gates", []),
        skill_details=skill_details,
        skill_usage=skill_usage,
    )
    records = list(state.get("historian_records", []))
    skill_names = ", ".join(skill["name"] for skill in skill_usage)

    records.append(
        {
            "type": "skill_usage",
            "content": f"Loaded required skills before execution: {skill_names}",
            "created_at": datetime.now().isoformat(),
        }
    )

    route_result = {
        **state.get("route_result", {}),
        "skill_usage": skill_usage,
        "skill_execution_plan": skill_execution_plan,
    }

    return {
        **state,
        "route_result": route_result,
        "skill_usage": skill_usage,
        "skill_execution_plan": skill_execution_plan,
        "historian_records": records,
    }

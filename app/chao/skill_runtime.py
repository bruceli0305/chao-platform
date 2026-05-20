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


def prepare_required_skills(state: ChaoState) -> ChaoState:
    skill_details = state.get("required_skill_details", [])

    if not skill_details:
        return {
            **state,
            "skill_usage": [],
        }

    skill_usage = [load_skill_usage(skill) for skill in skill_details]
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
    }

    return {
        **state,
        "route_result": route_result,
        "skill_usage": skill_usage,
        "historian_records": records,
    }

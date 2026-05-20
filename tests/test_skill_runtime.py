import pytest

from app.chao.skill_runtime import load_skill_usage, prepare_required_skills
from app.chao.skills import get_skill


def test_load_skill_usage_reads_skill_file_without_persisting_body():
    usage = load_skill_usage(get_skill("bugfix"))

    assert usage["name"] == "bugfix"
    assert usage["path"] == ".ai-agents/skills/bugfix/SKILL.md"
    assert usage["status"] == "loaded"
    assert len(usage["content_sha256"]) == 64
    assert usage["content_chars"] > 0
    assert "# Skill: bugfix" in usage["headings"]
    assert "content" not in usage


def test_load_skill_usage_rejects_paths_outside_skill_root():
    with pytest.raises(ValueError):
        load_skill_usage(
            {
                "name": "bad",
                "path": "AGENTS.md",
            }
        )


def test_prepare_required_skills_adds_usage_to_state_and_historian_record():
    state = {
        "task_id": "task-1",
        "task_code": "TASK-1",
        "status": "CLASSIFIED",
        "route_result": {"required_skills": ["bugfix"]},
        "required_skill_details": [get_skill("bugfix")],
        "historian_records": [{"type": "raw_request", "content": "fix", "created_at": "now"}],
    }

    result = prepare_required_skills(state)

    assert result["skill_usage"][0]["name"] == "bugfix"
    assert result["route_result"]["skill_usage"][0]["name"] == "bugfix"
    assert result["historian_records"][-1]["type"] == "skill_usage"
    assert "bugfix" in result["historian_records"][-1]["content"]


def test_prepare_required_skills_handles_tasks_without_skills():
    result = prepare_required_skills(
        {
            "task_id": "task-1",
            "task_code": "TASK-1",
            "status": "CLASSIFIED",
            "required_skill_details": [],
            "historian_records": [],
        }
    )

    assert result["skill_usage"] == []
    assert result["historian_records"] == []

from pathlib import Path

from app.chao.skills import SKILL_REGISTRY, get_skill, list_skills, select_required_skills


def test_skill_registry_contains_first_batch_and_skill_files():
    assert set(SKILL_REGISTRY) == {
        "bugfix",
        "frontend-feature",
        "api-development",
        "database-migration",
        "security-review",
        "docs-generation",
        "release-validation",
    }

    for definition in list_skills():
        assert Path(definition["path"]).is_file()
        assert definition["default_gates"]
        assert definition["trigger_keywords"]


def test_get_skill_returns_definition():
    skill = get_skill("database-migration")

    assert skill["name"] == "database-migration"
    assert skill["path"] == ".ai-agents/skills/database-migration/SKILL.md"


def test_select_required_skills_for_frontend_l2():
    assert select_required_skills("新增后台应用管理页面，包含列表和新增弹窗", "L2") == [
        "frontend-feature"
    ]


def test_select_required_skills_for_bugfix_l1():
    assert select_required_skills("修复首页标题文案错误", "L1") == ["bugfix"]


def test_select_required_skills_for_database_l3():
    assert "database-migration" in select_required_skills(
        "给用户表新增 status 字段，并迁移历史数据",
        "L3",
    )


def test_select_required_skills_respects_l2_limit():
    result = select_required_skills(
        "修复前端页面接口权限文档发布问题，包含列表和回滚说明",
        "L2",
    )

    assert len(result) == 3


def test_select_required_skills_returns_none_for_l4():
    assert select_required_skills("大型平台重构", "L4") == []

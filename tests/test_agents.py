from pathlib import Path

from app.chao.agents import (
    SELF_UPGRADE_REQUIRED_SKILLS,
    get_agent,
    list_agents,
    load_agent_registry,
    validate_agent_registry,
    validate_self_upgrade_readiness,
)


def test_agent_registry_contains_three_provinces_and_six_ministries():
    registry = load_agent_registry()

    assert set(registry["agents"]) == {
        "shangshu",
        "zhongshu",
        "menxia",
        "gongbu",
        "xingbu",
        "hubu",
        "bingbu",
        "libu-personnel",
        "libu-rites",
    }
    assert registry["required_self_upgrade_agents"] == [
        "zhongshu",
        "gongbu",
        "xingbu",
        "shangshu",
    ]


def test_agent_registry_validates_docs_tools_and_owned_skills():
    assert validate_agent_registry() == []

    for agent in list_agents():
        assert Path(agent["role_doc"]).is_file()


def test_governance_agents_can_run_governance_check_tool():
    agents = {agent["name"]: agent for agent in list_agents()}

    assert "cli.governance_check" in agents["menxia"]["default_tools"]
    assert "cli.governance_check" in agents["hubu"]["default_tools"]
    assert "cli.governance_check" in agents["bingbu"]["default_tools"]


def test_gongbu_owns_first_batch_skills_for_execution():
    gongbu = get_agent("gongbu")

    assert set(gongbu["owned_skills"]) == {
        "api-development",
        "bugfix",
        "database-migration",
        "docs-generation",
        "frontend-feature",
        "release-validation",
        "security-review",
    }


def test_self_upgrade_readiness_requires_runtime_agents_and_base_skills():
    assert set(SELF_UPGRADE_REQUIRED_SKILLS) == {
        "bugfix",
        "security-review",
        "release-validation",
        "docs-generation",
    }
    assert validate_self_upgrade_readiness() == []

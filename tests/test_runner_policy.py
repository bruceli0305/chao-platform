import pytest

from app.chao.runner_policy import (
    build_runner_boundary_policy,
    build_runner_branch_name,
    build_runner_branch_plan,
    check_change_paths,
    is_change_path_allowed,
    is_valid_runner_branch_name,
    normalize_repo_path,
)


def test_runner_policy_allows_expected_repo_scopes():
    assert is_change_path_allowed("app/chao/runner_policy.py") is True
    assert is_change_path_allowed("tests/test_runner_policy.py") is True
    assert is_change_path_allowed("docs/16-agent-runner-sandbox-boundary-v3.md") is True
    assert is_change_path_allowed(".github/workflows/ci.yml") is True


def test_runner_policy_blocks_forbidden_paths():
    assert is_change_path_allowed(".env") is False
    assert is_change_path_allowed(".env.local") is False
    assert is_change_path_allowed("data/postgres/pgdata") is False
    assert is_change_path_allowed("logs/chao.log") is False
    assert is_change_path_allowed("app/chao/__pycache__/router.pyc") is False


def test_runner_policy_blocks_unknown_paths():
    errors = check_change_paths(["pyproject.toml", "README.md"])

    assert errors == [
        "路径不在 Agent Runner 允许修改范围内：pyproject.toml",
        "路径不在 Agent Runner 允许修改范围内：README.md",
    ]


def test_runner_policy_rejects_path_traversal():
    with pytest.raises(ValueError, match="路径不能跳出仓库"):
        normalize_repo_path("../outside.txt")


def test_l4_runner_policy_cannot_execute():
    policy = build_runner_boundary_policy("L4")

    assert policy["execution_environment"] == "branch_or_sandbox"
    assert policy["required_branch_prefix"] == "codex/"
    assert policy["can_execute"] is False


def test_runner_branch_name_uses_codex_prefix_and_task_code():
    branch_name = build_runner_branch_name(
        task_code="TASK-20260511-191300-226866",
        title="新增后台应用管理页面",
    )

    assert branch_name == "codex/task-20260511-191300-226866-task"
    assert is_valid_runner_branch_name(branch_name) is True


def test_runner_branch_plan_for_l3_requires_branch():
    plan = build_runner_branch_plan(
        task_code="TASK-20260511-191300-226866",
        title="数据库迁移",
        task_level="L3",
        base_ref="main",
    )

    assert plan["branch_required"] is True
    assert plan["branch_name"] == "codex/task-20260511-191300-226866-task"
    assert plan["create_command"] == [
        "git",
        "checkout",
        "-b",
        "codex/task-20260511-191300-226866-task",
        "main",
    ]


def test_runner_branch_plan_for_l4_does_not_create_execution_branch():
    plan = build_runner_branch_plan(
        task_code="TASK-20260511-191300-226866",
        title="平台路线图",
        task_level="L4",
        base_ref="main",
    )

    assert plan["branch_required"] is False
    assert plan["branch_name"] is None
    assert plan["create_command"] is None
    assert "只生成规划" in plan["reason"]


def test_runner_branch_name_rejects_unsafe_names():
    assert is_valid_runner_branch_name("main") is False
    assert is_valid_runner_branch_name("feature/task") is False
    assert is_valid_runner_branch_name("codex/task with space") is False
    assert is_valid_runner_branch_name("codex/task..bad") is False

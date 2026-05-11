import pytest

from app.chao.runner_policy import (
    build_runner_boundary_policy,
    check_change_paths,
    is_change_path_allowed,
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

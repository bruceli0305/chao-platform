from app.chao.repositories import RepositoryConfig
from app.chao.runner_preflight import (
    build_runner_preflight_result,
    require_runner_preflight_ready,
)


def _repository_config() -> RepositoryConfig:
    return RepositoryConfig(
        name="demo",
        git_url="git@github.com:example/demo.git",
        default_branch="main",
        workspace_path=".",
        sandbox_root=".chao/sandboxes",
        branch_prefix="codex/",
        enabled=True,
    )


def _task(task_level: str = "L2") -> dict[str, object]:
    return {
        "task_code": "TASK-1",
        "task_level": task_level,
    }


def _doctor(runner_ready: bool = True, suggested_action: str = "ready") -> dict[str, object]:
    return {
        "repository": "demo",
        "status": "ready" if runner_ready else "blocked",
        "runner_ready": runner_ready,
        "suggested_action": suggested_action,
        "config": {},
        "workspace_status": {
            "repository": "demo",
            "workspace_path": ".",
            "default_branch": "main",
            "workspace_exists": True,
            "is_git_repository": True,
            "current_branch": "main",
            "head_commit": "abc123",
            "remote_url": "git@github.com:example/demo.git",
            "dirty": False,
            "status_lines": [],
            "ahead": 0,
            "behind": 0,
            "errors": [],
        },
        "sync_plan": {},
        "errors": [],
    }


def test_build_runner_preflight_result_marks_ready(monkeypatch):
    monkeypatch.setattr(
        "app.chao.runner_preflight.build_repository_doctor_report",
        lambda _repository: _doctor(),
    )

    result = build_runner_preflight_result(
        _task(),
        _repository_config(),
        ["lint", "test"],
    )

    assert result["status"] == "ready"
    assert result["runner_allowed"] is True
    assert result["repository_ready"] is True
    assert result["errors"] == []


def test_build_runner_preflight_result_blocks_l4(monkeypatch):
    monkeypatch.setattr(
        "app.chao.runner_preflight.build_repository_doctor_report",
        lambda _repository: _doctor(),
    )

    result = build_runner_preflight_result(
        _task("L4"),
        _repository_config(),
        ["milestone_review"],
    )

    assert result["status"] == "blocked"
    assert result["runner_allowed"] is False
    assert "L4 tasks cannot execute runner commands." in result["errors"]


def test_build_runner_preflight_result_blocks_unready_repository(monkeypatch):
    monkeypatch.setattr(
        "app.chao.runner_preflight.build_repository_doctor_report",
        lambda _repository: _doctor(False, "review_local_changes"),
    )

    result = build_runner_preflight_result(
        _task(),
        _repository_config(),
        ["lint"],
    )

    assert result["status"] == "blocked"
    assert result["repository_ready"] is False
    assert "repository is not runner ready: review_local_changes" in result["errors"]


def test_build_runner_preflight_can_skip_validation_gate_requirement(monkeypatch):
    monkeypatch.setattr(
        "app.chao.runner_preflight.build_repository_doctor_report",
        lambda _repository: _doctor(),
    )

    result = build_runner_preflight_result(
        _task(),
        _repository_config(),
        [],
        require_validation_gates=False,
    )

    assert result["status"] == "ready"
    assert result["validation_gates"] == []
    assert result["errors"] == []


def test_require_runner_preflight_ready_raises_for_blocked_result():
    preflight = {
        "task_code": "TASK-1",
        "task_level": "L2",
        "repository": "demo",
        "status": "blocked",
        "runner_allowed": True,
        "repository_ready": False,
        "validation_gates": ["lint"],
        "repository_doctor": _doctor(False, "review_local_changes"),
        "errors": ["repository is not runner ready: review_local_changes"],
    }

    try:
        require_runner_preflight_ready(preflight)
    except PermissionError as exc:
        assert str(exc) == "repository is not runner ready: review_local_changes"
    else:
        raise AssertionError("expected blocked runner preflight to raise")

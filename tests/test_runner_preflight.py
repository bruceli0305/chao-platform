from app.chao.repositories import RepositoryConfig
from app.chao.runner_preflight import build_runner_preflight_result


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

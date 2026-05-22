from typer.testing import CliRunner

from app.chao import cli
from app.chao.repositories import RepositoryConfig


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


def _task() -> dict[str, object]:
    return {
        "id": "task-1",
        "task_code": "TASK-1",
        "title": "Patch demo",
        "task_level": "L2",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "B", "required_gates": ["lint"]},
    }


def test_runner_preflight_outputs_ready_json(monkeypatch):
    calls = []

    def fake_build_runner_preflight_result(task, repository, gates):
        calls.append((task, repository, gates))
        return {
            "task_code": task["task_code"],
            "task_level": task["task_level"],
            "repository": repository.name,
            "status": "ready",
            "runner_allowed": True,
            "repository_ready": True,
            "validation_gates": gates,
            "repository_doctor": {"suggested_action": "ready"},
            "errors": [],
        }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: _task())
    monkeypatch.setattr(cli, "get_repository_config", lambda _name=None: _repository_config())
    monkeypatch.setattr(
        cli,
        "build_runner_preflight_result",
        fake_build_runner_preflight_result,
    )

    result = CliRunner().invoke(cli.app, ["runner-preflight", "TASK-1", "--json"])

    assert result.exit_code == 0
    assert calls[0][2] == ["lint"]
    assert '"status": "ready"' in result.output
    assert '"repository_ready": true' in result.output


def test_runner_preflight_renders_blocked_summary(monkeypatch):
    def fake_build_runner_preflight_result(task, repository, gates):
        return {
            "task_code": task["task_code"],
            "task_level": task["task_level"],
            "repository": repository.name,
            "status": "blocked",
            "runner_allowed": True,
            "repository_ready": False,
            "validation_gates": gates,
            "repository_doctor": {"suggested_action": "review_local_changes"},
            "errors": ["repository is not runner ready: review_local_changes"],
        }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: _task())
    monkeypatch.setattr(cli, "get_repository_config", lambda _name=None: _repository_config())
    monkeypatch.setattr(
        cli,
        "build_runner_preflight_result",
        fake_build_runner_preflight_result,
    )

    result = CliRunner().invoke(cli.app, ["runner-preflight", "TASK-1"])

    assert result.exit_code == 1
    assert "Runner Preflight" in result.output
    assert "review_local_changes" in result.output


def test_runner_preflight_rejects_missing_task(monkeypatch):
    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: None)

    result = CliRunner().invoke(cli.app, ["runner-preflight", "TASK-MISSING"])

    assert result.exit_code == 1
    assert "Task not found" in result.output

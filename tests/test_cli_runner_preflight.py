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
    calls = {"build": [], "events": [], "tool_calls": []}

    def fake_build_runner_preflight_result(task, repository, gates, **_kwargs):
        calls["build"].append((task, repository, gates))
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
    monkeypatch.setattr(
        cli,
        "record_task_event",
        lambda **kwargs: calls["events"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "record_tool_call",
        lambda **kwargs: calls["tool_calls"].append(kwargs),
    )

    result = CliRunner().invoke(cli.app, ["runner-preflight", "TASK-1", "--json"])

    assert result.exit_code == 0
    assert calls["build"][0][2] == ["lint"]
    assert calls["events"][0]["event_type"] == "runner_preflight_ready"
    assert calls["tool_calls"][0]["tool_name"] == "cli.runner_preflight"
    assert calls["tool_calls"][0]["permission_policy"] == "controlled-runner-preflight"
    assert calls["tool_calls"][0]["result_status"] == "success"
    assert '"status": "ready"' in result.output
    assert '"repository_ready": true' in result.output


def test_runner_preflight_renders_blocked_summary(monkeypatch):
    calls = {"events": [], "tool_calls": []}

    def fake_build_runner_preflight_result(task, repository, gates, **_kwargs):
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
    monkeypatch.setattr(
        cli,
        "record_task_event",
        lambda **kwargs: calls["events"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "record_tool_call",
        lambda **kwargs: calls["tool_calls"].append(kwargs),
    )

    result = CliRunner().invoke(cli.app, ["runner-preflight", "TASK-1"])

    assert result.exit_code == 1
    assert calls["events"][0]["event_type"] == "runner_preflight_blocked"
    assert calls["tool_calls"][0]["result_status"] == "failed"
    assert "Runner Preflight" in result.output
    assert "review_local_changes" in result.output


def test_runner_preflight_records_missing_gates_as_blocked(monkeypatch):
    calls = {"build": [], "events": [], "tool_calls": []}
    task = _task()
    task["route_result"] = {"required_confirmation": "B"}

    def fake_build_runner_preflight_result(task, repository, gates, **_kwargs):
        calls["build"].append((task, repository, gates))
        return {
            "task_code": task["task_code"],
            "task_level": task["task_level"],
            "repository": repository.name,
            "status": "blocked",
            "runner_allowed": True,
            "repository_ready": True,
            "validation_gates": gates,
            "repository_doctor": {"suggested_action": "ready"},
            "errors": ["No validation gates provided or recorded for this task."],
        }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(cli, "get_repository_config", lambda _name=None: _repository_config())
    monkeypatch.setattr(
        cli,
        "build_runner_preflight_result",
        fake_build_runner_preflight_result,
    )
    monkeypatch.setattr(
        cli,
        "record_task_event",
        lambda **kwargs: calls["events"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "record_tool_call",
        lambda **kwargs: calls["tool_calls"].append(kwargs),
    )

    result = CliRunner().invoke(cli.app, ["runner-preflight", "TASK-1", "--json"])

    assert result.exit_code == 1
    assert calls["build"][0][2] == []
    assert calls["events"][0]["event_type"] == "runner_preflight_blocked"
    assert calls["tool_calls"][0]["result_status"] == "failed"
    assert '"validation_gates": []' in result.output


def test_require_runner_repository_preflight_records_block_before_raise(monkeypatch):
    calls = {"events": [], "tool_calls": []}

    def fake_build_runner_preflight_result(task, repository, gates, **_kwargs):
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

    monkeypatch.setattr(cli, "build_runner_preflight_result", fake_build_runner_preflight_result)
    monkeypatch.setattr(
        cli,
        "record_task_event",
        lambda **kwargs: calls["events"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "record_tool_call",
        lambda **kwargs: calls["tool_calls"].append(kwargs),
    )

    try:
        cli._require_runner_repository_preflight(
            _task(),
            _repository_config(),
            ["lint"],
            by="gongbu",
        )
    except PermissionError as exc:
        assert str(exc) == "repository is not runner ready: review_local_changes"
    else:
        raise AssertionError("expected blocked preflight to raise")

    assert calls["events"][0]["event_type"] == "runner_preflight_blocked"
    assert "review_local_changes" in calls["events"][0]["summary"]
    assert calls["tool_calls"][0]["tool_name"] == "cli.runner_preflight"
    assert calls["tool_calls"][0]["result_status"] == "failed"


def test_runner_preflight_rejects_missing_task(monkeypatch):
    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: None)

    result = CliRunner().invoke(cli.app, ["runner-preflight", "TASK-MISSING"])

    assert result.exit_code == 1
    assert "Task not found" in result.output

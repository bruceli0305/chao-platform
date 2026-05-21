from typer.testing import CliRunner

from app.chao import cli
from app.chao.repositories import RepositoryConfig


def _repository_config(
    *,
    name: str = "chao-platform",
    workspace_path: str = ".",
):
    return RepositoryConfig(
        name=name,
        git_url="git@github.com:example/repo.git",
        default_branch="main",
        workspace_path=workspace_path,
        sandbox_root=".chao/sandboxes",
        branch_prefix="codex/",
        enabled=True,
    )


def test_resolve_task_validation_gates_prefers_explicit_gates():
    task = {
        "skill_execution_plan": {
            "combined_gates": ["manual_validation", "lint", "test"],
        },
        "route_result": {"required_gates": ["manual_validation"]},
    }

    assert cli._resolve_task_validation_gates(task, ["compile"]) == ["compile"]


def test_runner_validate_records_success(monkeypatch):
    calls = {
        "events": [],
        "tool_calls": [],
    }
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "task_level": "L1",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "none"},
    }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(cli, "get_repository_config", lambda _name=None: _repository_config())
    monkeypatch.setattr(
        cli,
        "execute_runner_validation_commands",
        lambda gates, timeout_seconds=120, **_kwargs: {
            "quality": "deliverable",
            "checks": gates,
            "plan": [],
            "command_results": [],
            "deliverable": True,
            "note": "passed",
        },
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

    result = CliRunner().invoke(
        cli.app,
        [
            "runner-validate",
            "TASK-1",
            "--gate",
            "compile",
            "--timeout",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert calls["events"][0]["event_type"] == "runner_validation_passed"
    assert calls["tool_calls"][0]["tool_name"] == "cli.runner_validate"
    assert calls["tool_calls"][0]["permission_policy"] == "controlled-runner-validation"
    assert calls["tool_calls"][0]["result_status"] == "success"
    assert "repository=chao-platform" in calls["tool_calls"][0]["arguments_summary"]


def test_runner_validate_uses_skill_execution_plan_when_gate_omitted(monkeypatch):
    calls = {
        "events": [],
        "tool_calls": [],
        "validation_gates": [],
    }
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "task_level": "L1",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "none"},
        "skill_execution_plan": {
            "status": "ready",
            "combined_gates": ["manual_validation", "lint", "test"],
            "skills": [],
        },
    }

    def execute_validation(gates, timeout_seconds=120, **_kwargs):
        calls["validation_gates"].extend(gates)
        return {
            "quality": "deliverable",
            "checks": gates,
            "plan": [],
            "command_results": [],
            "deliverable": True,
            "note": "passed",
        }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(cli, "get_repository_config", lambda _name=None: _repository_config())
    monkeypatch.setattr(cli, "execute_runner_validation_commands", execute_validation)
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

    result = CliRunner().invoke(
        cli.app,
        [
            "runner-validate",
            "TASK-1",
            "--timeout",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert calls["validation_gates"] == ["manual_validation", "lint", "test"]
    assert calls["events"][0]["summary"] == (
        "Runner validation success: manual_validation, lint, test"
    )
    assert calls["tool_calls"][0]["arguments_summary"] == (
        "task_code=TASK-1; repository=chao-platform; gates=['manual_validation', 'lint', 'test']"
    )


def test_runner_validate_rejects_missing_recorded_gates(monkeypatch):
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "task_level": "L1",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "none"},
    }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(cli, "get_repository_config", lambda _name=None: _repository_config())

    result = CliRunner().invoke(
        cli.app,
        [
            "runner-validate",
            "TASK-1",
        ],
    )

    assert result.exit_code == 1
    assert "No validation gates provided or recorded for this task." in result.output


def test_runner_validate_exits_nonzero_for_failed_validation(monkeypatch):
    calls = {
        "events": [],
        "tool_calls": [],
    }
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "task_level": "L1",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "none"},
    }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(cli, "get_repository_config", lambda _name=None: _repository_config())
    monkeypatch.setattr(
        cli,
        "execute_runner_validation_commands",
        lambda gates, timeout_seconds=120, **_kwargs: {
            "quality": "failed",
            "checks": gates,
            "plan": [],
            "command_results": [
                {
                    "gate": "manual_validation",
                    "command": "manual validation evidence required",
                    "status": "failed",
                    "exit_code": 1,
                    "output_summary": "manual gate",
                }
            ],
            "deliverable": False,
            "note": "failed",
        },
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

    result = CliRunner().invoke(
        cli.app,
        [
            "runner-validate",
            "TASK-1",
            "--gate",
            "manual_validation",
        ],
    )

    assert result.exit_code == 1
    assert calls["events"][0]["event_type"] == "runner_validation_failed"
    assert calls["tool_calls"][0]["result_status"] == "failed"


def test_runner_validate_uses_explicit_repository_config(monkeypatch):
    calls = {
        "events": [],
        "tool_calls": [],
        "validation_kwargs": None,
    }
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "task_level": "L1",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "none"},
    }
    repository = _repository_config(
        name="server-repo",
        workspace_path="/opt/chao/workspaces/server-repo",
    )

    def execute_validation(gates, **kwargs):
        calls["validation_kwargs"] = kwargs
        return {
            "quality": "deliverable",
            "checks": gates,
            "plan": [],
            "command_results": [],
            "deliverable": True,
            "note": "passed",
        }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(cli, "get_repository_config", lambda _name=None: repository)
    monkeypatch.setattr(cli, "execute_runner_validation_commands", execute_validation)
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

    result = CliRunner().invoke(
        cli.app,
        [
            "runner-validate",
            "TASK-1",
            "--repository",
            "server-repo",
            "--gate",
            "compile",
        ],
    )

    assert result.exit_code == 0
    assert calls["validation_kwargs"]["repo_root"] == "/opt/chao/workspaces/server-repo"
    assert "repository=server-repo" in calls["tool_calls"][0]["arguments_summary"]
    assert '"name": "server-repo"' in result.output

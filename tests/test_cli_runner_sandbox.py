from typer.testing import CliRunner

from app.chao import cli
from app.chao.runner_sandbox import DEFAULT_SANDBOX_IMAGE


def _task():
    return {
        "id": "task-1",
        "task_code": "TASK-1",
        "title": "Patch demo",
        "task_level": "L2",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "B"},
    }


def _task_with_skill_gates():
    task = _task()
    task["skill_execution_plan"] = {
        "status": "ready",
        "combined_gates": ["manual_validation", "lint", "test"],
        "skills": [],
    }
    return task


def _sandbox_result(*, dry_run: bool, deliverable: bool = False):
    return {
        "workspace_path": ".",
        "image": DEFAULT_SANDBOX_IMAGE,
        "gates": ["compile"],
        "docker_commands": [],
        "command_results": [],
        "dry_run": dry_run,
        "executed": not dry_run,
        "deliverable": deliverable,
        "errors": [],
    }


def test_runner_sandbox_dry_run_records_event_and_tool_call(monkeypatch):
    calls = {
        "events": [],
        "tool_calls": [],
    }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: _task())
    monkeypatch.setattr(
        cli,
        "execute_runner_sandbox_commands",
        lambda gates, **kwargs: _sandbox_result(dry_run=kwargs["dry_run"]),
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

    result = CliRunner().invoke(cli.app, ["runner-sandbox", "TASK-1", "--gate", "compile"])

    assert result.exit_code == 0
    assert calls["events"][0]["event_type"] == "runner_sandbox_dry_run"
    assert calls["tool_calls"][0]["tool_name"] == "cli.runner_sandbox"
    assert calls["tool_calls"][0]["permission_policy"] == "controlled-runner-sandbox"
    assert '"dry_run": true' in result.output


def test_runner_sandbox_apply_records_passed_event(monkeypatch):
    calls = {
        "events": [],
        "tool_calls": [],
    }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: _task())
    monkeypatch.setattr(
        cli,
        "execute_runner_sandbox_commands",
        lambda gates, **kwargs: _sandbox_result(dry_run=kwargs["dry_run"], deliverable=True),
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
        ["runner-sandbox", "TASK-1", "--gate", "compile", "--apply"],
    )

    assert result.exit_code == 0
    assert calls["events"][0]["event_type"] == "runner_sandbox_passed"
    assert calls["tool_calls"][0]["result_status"] == "success"
    assert '"executed": true' in result.output


def test_runner_sandbox_apply_exits_nonzero_for_failed_gate(monkeypatch):
    calls = {
        "events": [],
        "tool_calls": [],
    }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: _task())
    monkeypatch.setattr(
        cli,
        "execute_runner_sandbox_commands",
        lambda gates, **kwargs: _sandbox_result(dry_run=kwargs["dry_run"], deliverable=False),
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
        ["runner-sandbox", "TASK-1", "--gate", "compile", "--apply"],
    )

    assert result.exit_code == 1
    assert calls["events"][0]["event_type"] == "runner_sandbox_failed"
    assert calls["tool_calls"][0]["result_status"] == "failed"


def test_runner_sandbox_uses_skill_execution_plan_when_gate_omitted(monkeypatch):
    calls = {
        "events": [],
        "tool_calls": [],
        "sandbox_gates": [],
    }

    def execute_sandbox(gates, **kwargs):
        calls["sandbox_gates"].extend(gates)
        return _sandbox_result(dry_run=kwargs["dry_run"])

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: _task_with_skill_gates())
    monkeypatch.setattr(cli, "execute_runner_sandbox_commands", execute_sandbox)
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

    result = CliRunner().invoke(cli.app, ["runner-sandbox", "TASK-1"])

    assert result.exit_code == 0
    assert calls["sandbox_gates"] == ["manual_validation", "lint", "test"]
    assert calls["events"][0]["event_type"] == "runner_sandbox_dry_run"
    assert calls["tool_calls"][0]["arguments_summary"] == (
        "task_code=TASK-1; gates=['manual_validation', 'lint', 'test']; "
        f"workspace_path=.; image={DEFAULT_SANDBOX_IMAGE}; apply=False"
    )

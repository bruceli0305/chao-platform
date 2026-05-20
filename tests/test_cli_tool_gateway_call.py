from typer.testing import CliRunner

from app.chao import cli


def _task(**overrides):
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "task_level": "L2",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "B"},
    }
    task.update(overrides)
    return task


def test_tool_gateway_call_evaluates_task_scoped_permission(monkeypatch):
    calls = []

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: _task())
    monkeypatch.setattr(
        cli,
        "evaluate_tool_gateway_request",
        lambda request: (
            calls.append(request)
            or {
                "allowed": True,
                "result_status": "allowed",
                "permission_decision": {"permission_policy": "data-boundary-validation"},
                "output": None,
                "error": None,
                "audit": {"tool_name": request["tool_name"]},
            }
        ),
    )

    result = CliRunner().invoke(
        cli.app,
        ["tool-gateway-call", "TASK-1", "data_boundary_check", "--by", "xingbu"],
    )

    assert result.exit_code == 0
    assert calls[0]["protocol"] == "cli"
    assert calls[0]["task_id"] == "task-1"
    assert calls[0]["required_confirmation"] == "B"
    assert "data-boundary-validation" in result.output
    assert "audit_persisted" in result.output


def test_tool_gateway_call_executes_registered_handler(monkeypatch):
    calls = []

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: _task())
    monkeypatch.setattr(
        cli,
        "execute_registered_tool_handler",
        lambda tool_name, arguments: (
            calls.append(("handler", tool_name, arguments)) or {"exit_code": 0}
        ),
    )

    def fake_execute(request, handler):
        calls.append(("execute", request))
        output = handler()
        return {
            "allowed": True,
            "result_status": "success",
            "permission_decision": {"permission_policy": "data-boundary-validation"},
            "output": output,
            "error": None,
            "audit": {"tool_name": request["tool_name"]},
            "audit_persisted": True,
            "audit_completed": True,
        }

    monkeypatch.setattr(cli, "execute_audited_tool_gateway_request", fake_execute)

    result = CliRunner().invoke(
        cli.app,
        [
            "tool-gateway-call",
            "TASK-1",
            "data_boundary_check",
            "--arguments-json",
            '{"pretty": true}',
            "--execute",
        ],
    )

    assert result.exit_code == 0
    assert calls[0][0] == "execute"
    assert calls[1] == ("handler", "data_boundary_check", {"pretty": True})
    assert "audit_completed" in result.output


def test_tool_gateway_call_rejects_non_object_arguments(monkeypatch):
    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: _task())

    result = CliRunner().invoke(
        cli.app,
        [
            "tool-gateway-call",
            "TASK-1",
            "data_boundary_check",
            "--arguments-json",
            '["not-object"]',
        ],
    )

    assert result.exit_code == 1
    assert "Tool arguments JSON must be an object" in result.output


def test_tool_gateway_call_rejects_missing_task(monkeypatch):
    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: None)

    result = CliRunner().invoke(cli.app, ["tool-gateway-call", "TASK-MISSING", "schema_check"])

    assert result.exit_code == 1
    assert "Task not found" in result.output


def test_tool_gateway_reconcile_reports_stale_pending_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli,
        "list_stale_pending_tool_calls",
        lambda max_age_minutes, limit: (
            calls.append((max_age_minutes, limit))
            or [
                {
                    "id": "tool-call-1",
                    "task_id": "task-1",
                    "task_code": "TASK-1",
                    "agent_name": "xingbu",
                    "tool_name": "schema_check",
                    "result_status": "started",
                    "age_minutes": 31,
                }
            ]
        ),
    )

    result = CliRunner().invoke(
        cli.app,
        ["tool-gateway-reconcile", "--max-age-minutes", "15", "--limit", "10"],
    )

    assert result.exit_code == 0
    assert calls == [(15, 10)]
    assert '"dry_run": true' in result.output
    assert '"count": 1' in result.output
    assert "schema_check" in result.output


def test_tool_gateway_reconcile_apply_marks_timed_out_and_records_events(monkeypatch):
    calls = {"reconcile": [], "events": []}
    monkeypatch.setattr(
        cli,
        "mark_stale_pending_tool_calls_timed_out",
        lambda max_age_minutes, limit: (
            calls["reconcile"].append((max_age_minutes, limit))
            or [
                {
                    "id": "tool-call-1",
                    "task_id": "task-1",
                    "task_code": "TASK-1",
                    "agent_name": "xingbu",
                    "tool_name": "schema_check",
                    "result_status": "timed_out",
                    "age_minutes": 31,
                }
            ]
        ),
    )
    monkeypatch.setattr(
        cli,
        "record_task_event",
        lambda **kwargs: calls["events"].append(kwargs),
    )

    result = CliRunner().invoke(
        cli.app,
        ["tool-gateway-reconcile", "--max-age-minutes", "15", "--limit", "10", "--apply"],
    )

    assert result.exit_code == 0
    assert calls["reconcile"] == [(15, 10)]
    assert calls["events"][0]["task_id"] == "task-1"
    assert calls["events"][0]["event_type"] == "tool_call_timed_out"
    assert calls["events"][0]["created_by"] == "xingbu"
    assert '"dry_run": false' in result.output
    assert '"result_status": "timed_out"' in result.output

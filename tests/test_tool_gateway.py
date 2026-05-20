from app.chao.tool_gateway import (
    ToolGatewayRequest,
    evaluate_tool_gateway_request,
    execute_audited_tool_gateway_request,
    execute_tool_gateway_request,
    finish_tool_gateway_audit,
    persist_tool_gateway_audit,
    start_tool_gateway_audit,
)


def _request(**overrides) -> ToolGatewayRequest:
    request: ToolGatewayRequest = {
        "protocol": "mcp",
        "agent_name": "gongbu",
        "tool_name": "cli.runner_patch",
        "task_level": "L2",
        "required_confirmation": "B",
        "current_status": "DELIVERED",
        "arguments_summary": "path=app/chao/demo.py",
        "task_id": "task-1",
    }
    request.update(overrides)
    return request


def test_evaluate_tool_gateway_request_allows_registered_tool():
    response = evaluate_tool_gateway_request(_request())

    assert response["allowed"] is True
    assert response["result_status"] == "allowed"
    assert response["permission_decision"]["permission_policy"] == "controlled-runner-text-patch"
    assert response["audit"]["protocol"] == "mcp"
    assert response["audit"]["task_id"] == "task-1"


def test_execute_tool_gateway_request_calls_handler_when_allowed():
    calls = []

    response = execute_tool_gateway_request(
        _request(),
        lambda: calls.append("called") or {"ok": True},
    )

    assert calls == ["called"]
    assert response["allowed"] is True
    assert response["result_status"] == "success"
    assert response["output"] == {"ok": True}
    assert response["audit"]["result_status"] == "success"
    assert response["audit"]["permission_policy"] == "controlled-runner-text-patch"


def test_execute_tool_gateway_request_blocks_handler_when_denied():
    calls = []

    response = execute_tool_gateway_request(
        _request(agent_name="menxia"),
        lambda: calls.append("called"),
    )

    assert calls == []
    assert response["allowed"] is False
    assert response["result_status"] == "denied"
    assert response["error"] == "角色 menxia 未授权调用 cli.runner_patch。"
    assert response["audit"]["permission_policy"] == "role-tool-denied"


def test_execute_tool_gateway_request_reports_handler_failure():
    def raise_error():
        raise RuntimeError("tool failed")

    response = execute_tool_gateway_request(_request(), raise_error)

    assert response["allowed"] is True
    assert response["result_status"] == "failed"
    assert response["output"] is None
    assert response["error"] == "tool failed"
    assert response["audit"]["result_status"] == "failed"
    assert response["audit"]["output_summary"] == "tool failed"


def test_persist_tool_gateway_audit_records_tool_call():
    calls = []
    response = execute_tool_gateway_request(
        _request(),
        lambda: {"ok": True},
    )

    persisted = persist_tool_gateway_audit(
        response["audit"],
        recorder=lambda **kwargs: calls.append(kwargs),
    )

    assert persisted is True
    assert calls[0]["task_id"] == "task-1"
    assert calls[0]["tool_name"] == "cli.runner_patch"
    assert calls[0]["permission_policy"] == "controlled-runner-text-patch"
    assert calls[0]["result_status"] == "success"
    assert calls[0]["permission_decision"]["allowed"] is True


def test_persist_tool_gateway_audit_skips_missing_task_id():
    calls = []
    response = execute_tool_gateway_request(
        _request(task_id=None),
        lambda: {"ok": True},
    )

    persisted = persist_tool_gateway_audit(
        response["audit"],
        recorder=lambda **kwargs: calls.append(kwargs),
    )

    assert persisted is False
    assert calls == []


def test_start_and_finish_tool_gateway_audit_use_two_phase_records():
    started = []
    finished = []
    response = evaluate_tool_gateway_request(_request())

    tool_call_id = start_tool_gateway_audit(
        response["audit"],
        starter=lambda **kwargs: started.append(kwargs) or "tool-call-1",
    )
    completed = finish_tool_gateway_audit(
        tool_call_id,
        response["audit"],
        finisher=lambda *args, **kwargs: finished.append((args, kwargs)),
    )

    assert tool_call_id == "tool-call-1"
    assert completed is True
    assert started[0]["task_id"] == "task-1"
    assert started[0]["tool_name"] == "cli.runner_patch"
    assert finished[0][0] == ("tool-call-1",)
    assert finished[0][1]["result_status"] == "allowed"


def test_execute_audited_tool_gateway_request_starts_audit_before_handler(monkeypatch):
    calls = []

    monkeypatch.setattr(
        "app.chao.tool_gateway.start_tool_gateway_audit",
        lambda audit: calls.append(("start", audit["result_status"])) or "tool-call-1",
    )
    monkeypatch.setattr(
        "app.chao.tool_gateway.finish_tool_gateway_audit",
        lambda tool_call_id, audit: (
            calls.append(("finish", tool_call_id, audit["result_status"])) or True
        ),
    )

    def handler():
        assert calls == [("start", "allowed")]
        calls.append(("handler",))
        return {"ok": True}

    result = execute_audited_tool_gateway_request(_request(), handler)

    assert result["result_status"] == "success"
    assert result["audit_persisted"] is True
    assert result["audit_completed"] is True
    assert calls == [
        ("start", "allowed"),
        ("handler",),
        ("finish", "tool-call-1", "success"),
    ]


def test_execute_audited_tool_gateway_request_records_denied_without_handler(monkeypatch):
    calls = []

    monkeypatch.setattr(
        "app.chao.tool_gateway.start_tool_gateway_audit",
        lambda audit: calls.append(("start", audit["result_status"])) or "tool-call-1",
    )
    monkeypatch.setattr(
        "app.chao.tool_gateway.finish_tool_gateway_audit",
        lambda tool_call_id, audit: (
            calls.append(("finish", tool_call_id, audit["result_status"])) or True
        ),
    )

    result = execute_audited_tool_gateway_request(
        _request(agent_name="menxia"),
        lambda: calls.append(("handler",)),
    )

    assert result["result_status"] == "denied"
    assert result["audit_persisted"] is True
    assert result["audit_completed"] is True
    assert calls == [
        ("start", "denied"),
        ("finish", "tool-call-1", "denied"),
    ]

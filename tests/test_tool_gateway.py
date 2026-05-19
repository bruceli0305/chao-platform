from app.chao.tool_gateway import (
    ToolGatewayRequest,
    evaluate_tool_gateway_request,
    execute_tool_gateway_request,
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

import json
from io import StringIO

from app.chao.mcp_server import (
    handle_mcp_message,
    list_mcp_tools,
    parse_mcp_line,
    serve_mcp,
)


def _arguments(**overrides):
    arguments = {
        "agent_name": "xingbu",
        "task_level": "L2",
        "required_confirmation": "B",
        "current_status": "DELIVERED",
        "arguments_summary": "gate=data_boundary_check",
        "task_id": "task-1",
    }
    arguments.update(overrides)
    return arguments


def test_handle_mcp_message_initialize():
    response = handle_mcp_message({"jsonrpc": "2.0", "id": 1, "method": "initialize"})

    assert response["result"]["capabilities"] == {"tools": {}}
    assert response["result"]["serverInfo"]["name"] == "chao-tool-gateway"


def test_handle_mcp_message_ignores_initialized_notification():
    response = handle_mcp_message(
        {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
    )

    assert response is None


def test_list_mcp_tools_exposes_input_schema():
    tools = list_mcp_tools()
    data_boundary = next(tool for tool in tools if tool["name"] == "data_boundary_check")

    assert data_boundary["inputSchema"]["required"] == [
        "agent_name",
        "task_level",
        "required_confirmation",
        "current_status",
        "arguments_summary",
    ]


def test_handle_mcp_message_tools_list():
    response = handle_mcp_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

    assert {tool["name"] for tool in response["result"]["tools"]} >= {
        "schema_check",
        "data_boundary_check",
        "cli.runner_validate",
    }


def test_handle_mcp_message_tools_call_executes_registered_handler(monkeypatch):
    audits = []

    def fake_execute(tool_name, arguments):
        return {
            "tool_name": tool_name,
            "arguments": arguments,
            "exit_code": 0,
            "stdout": "ok",
            "stderr": "",
        }

    monkeypatch.setattr("app.chao.mcp_server.execute_registered_tool_handler", fake_execute)
    monkeypatch.setattr(
        "app.chao.tool_gateway.start_tool_gateway_audit",
        lambda audit: audits.append(("start", audit)) or "tool-call-1",
    )
    monkeypatch.setattr(
        "app.chao.tool_gateway.finish_tool_gateway_audit",
        lambda tool_call_id, audit: audits.append(("finish", tool_call_id, audit)) or True,
    )

    response = handle_mcp_message(
        {
            "jsonrpc": "2.0",
            "id": "call-1",
            "method": "tools/call",
            "params": {
                "name": "data_boundary_check",
                "arguments": _arguments(arguments={"pretty": True}),
            },
        }
    )

    result = response["result"]
    structured = result["structuredContent"]

    assert result["isError"] is False
    assert structured["result_status"] == "success"
    assert structured["audit_persisted"] is True
    assert structured["audit_completed"] is True
    assert structured["output"]["arguments"] == {"pretty": True}
    assert json.loads(result["content"][0]["text"]) == structured
    assert audits[0][1]["task_id"] == "task-1"
    assert audits[1][2]["result_status"] == "success"


def test_handle_mcp_message_tools_call_marks_denied_as_error(monkeypatch):
    audits = []
    monkeypatch.setattr(
        "app.chao.tool_gateway.start_tool_gateway_audit",
        lambda audit: audits.append(("start", audit)) or "tool-call-1",
    )
    monkeypatch.setattr(
        "app.chao.tool_gateway.finish_tool_gateway_audit",
        lambda tool_call_id, audit: audits.append(("finish", tool_call_id, audit)) or True,
    )

    response = handle_mcp_message(
        {
            "jsonrpc": "2.0",
            "id": "denied",
            "method": "tools/call",
            "params": {
                "name": "data_boundary_check",
                "arguments": _arguments(agent_name="gongbu"),
            },
        }
    )

    assert response["result"]["isError"] is True
    assert response["result"]["structuredContent"]["result_status"] == "denied"
    assert response["result"]["structuredContent"]["audit_persisted"] is True
    assert response["result"]["structuredContent"]["audit_completed"] is True
    assert audits[0][1]["result_status"] == "denied"
    assert audits[1][2]["result_status"] == "denied"


def test_parse_mcp_line_reports_parse_error():
    response = parse_mcp_line("{not-json")

    assert response["error"]["code"] == -32700


def test_serve_mcp_skips_notifications_and_writes_responses():
    input_stream = StringIO(
        "\n".join(
            [
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}),
                json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            ]
        )
        + "\n"
    )
    output_stream = StringIO()

    exit_code = serve_mcp(input_stream, output_stream)
    responses = [json.loads(line) for line in output_stream.getvalue().splitlines()]

    assert exit_code == 0
    assert len(responses) == 1
    assert responses[0]["result"]["serverInfo"]["name"] == "chao-tool-gateway"

import json
from io import StringIO

from app.chao.tool_gateway_server import (
    handle_tool_gateway_message,
    parse_gateway_line,
    serve_tool_gateway,
)


def _request(**overrides):
    request = {
        "protocol": "jsonl",
        "agent_name": "xingbu",
        "tool_name": "data_boundary_check",
        "task_level": "L2",
        "required_confirmation": "B",
        "current_status": "DELIVERED",
        "arguments_summary": "gate=data_boundary_check",
        "task_id": "task-1",
    }
    request.update(overrides)
    return request


def test_handle_tool_gateway_message_health():
    response = handle_tool_gateway_message({"jsonrpc": "2.0", "id": 1, "method": "health"})

    assert response == {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "status": "ok",
            "server": "chao-tool-gateway",
        },
    }


def test_handle_tool_gateway_message_evaluates_permission():
    response = handle_tool_gateway_message(
        {
            "jsonrpc": "2.0",
            "id": "eval-1",
            "method": "tool.evaluate",
            "params": {"request": _request()},
        }
    )

    result = response["result"]

    assert response["id"] == "eval-1"
    assert result["allowed"] is True
    assert result["permission_decision"]["permission_policy"] == "data-boundary-validation"
    assert result["audit"]["protocol"] == "jsonl"


def test_handle_tool_gateway_message_lists_registered_handlers():
    response = handle_tool_gateway_message({"jsonrpc": "2.0", "id": 2, "method": "tools.list"})

    tool_names = {tool["tool_name"] for tool in response["result"]["tools"]}
    assert {"schema_check", "data_boundary_check"} <= tool_names


def test_handle_tool_gateway_message_executes_registered_handler(monkeypatch):
    def fake_execute(tool_name, arguments):
        return {
            "tool_name": tool_name,
            "arguments": arguments,
            "exit_code": 0,
            "stdout": "ok",
            "stderr": "",
        }

    monkeypatch.setattr(
        "app.chao.tool_gateway_server.execute_registered_tool_handler",
        fake_execute,
    )

    response = handle_tool_gateway_message(
        {
            "jsonrpc": "2.0",
            "id": "exec-1",
            "method": "tool.execute",
            "params": {
                "request": _request(),
                "arguments": {"pretty": True},
            },
        }
    )

    result = response["result"]

    assert result["allowed"] is True
    assert result["result_status"] == "success"
    assert result["output"]["tool_name"] == "data_boundary_check"
    assert result["output"]["arguments"] == {"pretty": True}


def test_handle_tool_gateway_message_rejects_non_object_arguments():
    response = handle_tool_gateway_message(
        {
            "jsonrpc": "2.0",
            "id": "bad-args",
            "method": "tool.execute",
            "params": {
                "request": _request(),
                "arguments": ["not", "an", "object"],
            },
        }
    )

    assert response["error"]["code"] == "invalid_params"


def test_handle_tool_gateway_message_reports_unregistered_allowed_handler():
    response = handle_tool_gateway_message(
        {
            "jsonrpc": "2.0",
            "id": "unregistered",
            "method": "tool.execute",
            "params": {
                "request": _request(
                    agent_name="gongbu",
                    tool_name="cli.runner_patch",
                    arguments_summary="path=app/chao/demo.py",
                ),
            },
        }
    )

    result = response["result"]

    assert result["allowed"] is True
    assert result["result_status"] == "failed"
    assert result["error"] == "no handler registered for tool: cli.runner_patch"


def test_handle_tool_gateway_message_execute_echo_blocks_denied_request():
    response = handle_tool_gateway_message(
        {
            "jsonrpc": "2.0",
            "id": "deny-1",
            "method": "tool.execute.echo",
            "params": {
                "request": _request(agent_name="gongbu"),
                "payload": {"should_not_execute": True},
            },
        }
    )

    result = response["result"]

    assert result["allowed"] is False
    assert result["result_status"] == "denied"
    assert result["output"] is None
    assert result["audit"]["permission_policy"] == "role-tool-denied"


def test_parse_gateway_line_reports_parse_error():
    response = parse_gateway_line("{not-json")

    assert response["error"]["code"] == "parse_error"


def test_serve_tool_gateway_reads_json_lines_and_writes_responses():
    input_stream = StringIO(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "health"}) + "\n")
    output_stream = StringIO()

    exit_code = serve_tool_gateway(input_stream, output_stream)
    responses = [json.loads(line) for line in output_stream.getvalue().splitlines()]

    assert exit_code == 0
    assert responses[0]["result"]["status"] == "ok"

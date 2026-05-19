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
    assert result["permission_decision"]["permission_policy"] == "controlled-runner-text-patch"
    assert result["audit"]["protocol"] == "jsonl"


def test_handle_tool_gateway_message_execute_echo_blocks_denied_request():
    response = handle_tool_gateway_message(
        {
            "jsonrpc": "2.0",
            "id": "deny-1",
            "method": "tool.execute.echo",
            "params": {
                "request": _request(agent_name="menxia"),
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

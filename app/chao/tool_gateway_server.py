import json
import sys
from typing import Any, TextIO

from app.chao.tool_gateway import (
    ToolGatewayRequest,
    evaluate_tool_gateway_request,
    execute_tool_gateway_request,
    persist_tool_gateway_audit,
)
from app.chao.tool_gateway_handlers import (
    execute_registered_tool_handler,
    list_tool_handlers,
)

SERVER_NAME = "chao-tool-gateway"


def _success(message_id: Any, result: Any) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "result": result,
    }


def _error(message_id: Any, code: str, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


def _request_from_params(params: dict[str, Any]) -> ToolGatewayRequest:
    request = params.get("request", params)

    if not isinstance(request, dict):
        raise ValueError("request must be an object")

    return {
        "protocol": str(request["protocol"]),
        "agent_name": str(request["agent_name"]),
        "tool_name": str(request["tool_name"]),
        "task_level": request["task_level"],
        "required_confirmation": str(request["required_confirmation"]),
        "current_status": str(request["current_status"]),
        "arguments_summary": str(request["arguments_summary"]),
        **({"task_id": str(request["task_id"])} if request.get("task_id") is not None else {}),
    }


def _execute_and_persist_tool_gateway_request(
    request: ToolGatewayRequest,
    handler,
) -> dict[str, Any]:
    result = execute_tool_gateway_request(request, handler)
    result["audit_persisted"] = persist_tool_gateway_audit(result["audit"])
    return result


def handle_tool_gateway_message(message: dict[str, Any]) -> dict[str, Any]:
    message_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}

    if not isinstance(params, dict):
        return _error(message_id, "invalid_params", "params must be an object")

    try:
        if method == "health":
            return _success(message_id, {"status": "ok", "server": SERVER_NAME})

        if method == "tool.evaluate":
            request = _request_from_params(params)
            return _success(message_id, evaluate_tool_gateway_request(request))

        if method == "tools.list":
            return _success(message_id, {"tools": list_tool_handlers()})

        if method == "tool.execute":
            request = _request_from_params(params)
            arguments = params.get("arguments") or {}
            if not isinstance(arguments, dict):
                return _error(message_id, "invalid_params", "arguments must be an object")
            return _success(
                message_id,
                _execute_and_persist_tool_gateway_request(
                    request,
                    lambda: execute_registered_tool_handler(
                        request["tool_name"],
                        arguments,
                    ),
                ),
            )

        if method == "tool.execute.echo":
            request = _request_from_params(params)
            payload = params.get("payload")
            return _success(
                message_id,
                _execute_and_persist_tool_gateway_request(
                    request,
                    lambda: {"echo": payload},
                ),
            )

        return _error(message_id, "method_not_found", f"unknown method: {method}")
    except KeyError as exc:
        return _error(message_id, "invalid_params", f"missing required field: {exc.args[0]}")
    except Exception as exc:
        return _error(message_id, "internal_error", str(exc))


def parse_gateway_line(line: str) -> dict[str, Any]:
    try:
        message = json.loads(line)
    except json.JSONDecodeError as exc:
        return _error(None, "parse_error", str(exc))

    if not isinstance(message, dict):
        return _error(None, "invalid_request", "message must be an object")

    return handle_tool_gateway_message(message)


def serve_tool_gateway(
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> int:
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout

    for line in input_stream:
        line = line.strip()
        if not line:
            continue

        response = parse_gateway_line(line)
        output_stream.write(json.dumps(response, ensure_ascii=False) + "\n")
        output_stream.flush()

    return 0

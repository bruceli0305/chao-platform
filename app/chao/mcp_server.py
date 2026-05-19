import json
import sys
from typing import Any, TextIO

from app.chao.mcp_sdk import get_mcp_sdk_status
from app.chao.tool_gateway import ToolGatewayRequest, execute_tool_gateway_request
from app.chao.tool_gateway_handlers import (
    execute_registered_tool_handler,
    list_tool_handlers,
)

MCP_PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "chao-tool-gateway"
SERVER_VERSION = "0.1.0"


def _success(message_id: Any, result: Any) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "result": result,
    }


def _error(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


def _tool_input_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "protocol": {"type": "string", "default": "mcp"},
            "agent_name": {"type": "string"},
            "task_level": {"type": "string", "enum": ["L1", "L2", "L3", "L4"]},
            "required_confirmation": {"type": "string"},
            "current_status": {"type": "string"},
            "arguments_summary": {"type": "string"},
            "task_id": {"type": "string"},
            "arguments": {"type": "object"},
        },
        "required": [
            "agent_name",
            "task_level",
            "required_confirmation",
            "current_status",
            "arguments_summary",
        ],
        "additionalProperties": True,
    }


def list_mcp_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": tool["tool_name"],
            "description": tool["description"],
            "inputSchema": _tool_input_schema(),
        }
        for tool in list_tool_handlers()
    ]


def _request_from_tool_call(tool_name: str, arguments: dict[str, Any]) -> ToolGatewayRequest:
    return {
        "protocol": str(arguments.get("protocol", "mcp")),
        "agent_name": str(arguments["agent_name"]),
        "tool_name": tool_name,
        "task_level": arguments["task_level"],
        "required_confirmation": str(arguments["required_confirmation"]),
        "current_status": str(arguments["current_status"]),
        "arguments_summary": str(arguments["arguments_summary"]),
        **({"task_id": str(arguments["task_id"])} if arguments.get("task_id") is not None else {}),
    }


def _mcp_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(result, ensure_ascii=False),
            }
        ],
        "structuredContent": result,
        "isError": result["result_status"] != "success",
    }


def handle_mcp_message(message: dict[str, Any]) -> dict[str, Any] | None:
    message_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}

    if method == "notifications/initialized":
        return None

    if not isinstance(params, dict):
        return _error(message_id, -32602, "params must be an object")

    try:
        if method == "initialize":
            return _success(
                message_id,
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": SERVER_NAME,
                        "version": SERVER_VERSION,
                    },
                    "sdk": get_mcp_sdk_status(),
                },
            )

        if method == "tools/list":
            return _success(message_id, {"tools": list_mcp_tools()})

        if method == "tools/call":
            tool_name = str(params["name"])
            arguments = params.get("arguments") or {}
            if not isinstance(arguments, dict):
                return _error(message_id, -32602, "arguments must be an object")

            request = _request_from_tool_call(tool_name, arguments)
            handler_arguments = arguments.get("arguments") or {}
            if not isinstance(handler_arguments, dict):
                return _error(message_id, -32602, "arguments.arguments must be an object")

            result = execute_tool_gateway_request(
                request,
                lambda: execute_registered_tool_handler(tool_name, handler_arguments),
            )
            return _success(message_id, _mcp_tool_result(result))

        return _error(message_id, -32601, f"unknown method: {method}")
    except KeyError as exc:
        return _error(message_id, -32602, f"missing required field: {exc.args[0]}")
    except Exception as exc:
        return _error(message_id, -32603, str(exc))


def parse_mcp_line(line: str) -> dict[str, Any] | None:
    try:
        message = json.loads(line)
    except json.JSONDecodeError as exc:
        return _error(None, -32700, str(exc))

    if not isinstance(message, dict):
        return _error(None, -32600, "message must be an object")

    return handle_mcp_message(message)


def serve_mcp(
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> int:
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout

    for line in input_stream:
        line = line.strip()
        if not line:
            continue

        response = parse_mcp_line(line)
        if response is None:
            continue

        output_stream.write(json.dumps(response, ensure_ascii=False) + "\n")
        output_stream.flush()

    return 0

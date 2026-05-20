import importlib
import importlib.metadata
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def get_mcp_sdk_status() -> dict[str, Any]:
    try:
        version = importlib.metadata.version("mcp")
    except importlib.metadata.PackageNotFoundError:
        return {
            "installed": False,
            "package": "mcp",
            "version": None,
            "module": None,
        }

    module = importlib.import_module("mcp")

    return {
        "installed": True,
        "package": "mcp",
        "version": version,
        "module": module.__name__,
    }


def _sdk_object_to_dict(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")

    if isinstance(value, dict):
        return value

    if isinstance(value, list | tuple):
        return [_sdk_object_to_dict(item) for item in value]

    return value


def _tool_to_summary(tool: Any) -> dict[str, Any]:
    payload = _sdk_object_to_dict(tool)

    if isinstance(payload, dict):
        return {
            "name": payload.get("name"),
            "description": payload.get("description"),
            "annotations": payload.get("annotations"),
        }

    return {
        "name": getattr(tool, "name", None),
        "description": getattr(tool, "description", None),
        "annotations": getattr(tool, "annotations", None),
    }


def _result_to_jsonable(value: Any) -> Any:
    payload = _sdk_object_to_dict(value)

    try:
        json.dumps(payload)
    except TypeError:
        return str(value)

    return payload


async def run_mcp_sdk_client_smoke(
    *,
    call_tool: str | None = None,
    tool_arguments: dict[str, Any] | None = None,
    command: str | None = None,
    args: list[str] | None = None,
    cwd: str | Path | None = None,
) -> dict[str, Any]:
    sdk_status = get_mcp_sdk_status()

    if not sdk_status["installed"]:
        return {
            "status": "failed",
            "sdk": sdk_status,
            "error": "Official MCP Python SDK is not installed.",
        }

    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except Exception as exc:
        return {
            "status": "failed",
            "sdk": sdk_status,
            "error": f"Official MCP Python SDK import failed: {exc}",
        }

    server_command = command or sys.executable
    server_args = args or ["main.py", "mcp-serve"]
    server_cwd = str(cwd or ROOT)
    server_parameters = StdioServerParameters(
        command=server_command,
        args=server_args,
        cwd=server_cwd,
    )

    try:
        async with stdio_client(server_parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                initialize_result = await session.initialize()
                tools_result = await session.list_tools()
                tools = [_tool_to_summary(tool) for tool in tools_result.tools]

                call_result = None
                if call_tool:
                    call_result = await session.call_tool(call_tool, tool_arguments or {})

        return {
            "status": "success",
            "sdk": sdk_status,
            "server": {
                "command": server_command,
                "args": server_args,
                "cwd": server_cwd,
            },
            "initialize": _result_to_jsonable(initialize_result),
            "tool_count": len(tools),
            "tools": tools,
            "call_tool": call_tool,
            "call_result": _result_to_jsonable(call_result) if call_result is not None else None,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "sdk": sdk_status,
            "server": {
                "command": server_command,
                "args": server_args,
                "cwd": server_cwd,
            },
            "error": str(exc),
        }


def run_mcp_sdk_client_smoke_sync(
    *,
    call_tool: str | None = None,
    tool_arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import asyncio

    return asyncio.run(
        run_mcp_sdk_client_smoke(
            call_tool=call_tool,
            tool_arguments=tool_arguments,
        )
    )

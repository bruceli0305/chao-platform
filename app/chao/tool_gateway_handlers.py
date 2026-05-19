import contextlib
import importlib
from collections.abc import Callable
from io import StringIO
from typing import Any, TypedDict


class ToolHandlerDefinition(TypedDict):
    tool_name: str
    description: str
    handler: Callable[[dict[str, Any]], dict[str, Any]]


def _run_script_main(module_name: str) -> dict[str, Any]:
    stdout = StringIO()
    stderr = StringIO()

    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        module = importlib.import_module(module_name)
        exit_code = module.main()

    return {
        "exit_code": exit_code,
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
    }


def _run_schema_check(_arguments: dict[str, Any]) -> dict[str, Any]:
    return _run_script_main("scripts.schema_check")


def _run_data_boundary_check(_arguments: dict[str, Any]) -> dict[str, Any]:
    return _run_script_main("scripts.data_boundary_check")


TOOL_HANDLER_REGISTRY: dict[str, ToolHandlerDefinition] = {
    "schema_check": {
        "tool_name": "schema_check",
        "description": "Run the schema gate in-process and return captured output.",
        "handler": _run_schema_check,
    },
    "data_boundary_check": {
        "tool_name": "data_boundary_check",
        "description": "Run the data-boundary gate in-process and return captured output.",
        "handler": _run_data_boundary_check,
    },
}


def list_tool_handlers() -> list[dict[str, str]]:
    return [
        {
            "tool_name": definition["tool_name"],
            "description": definition["description"],
        }
        for definition in TOOL_HANDLER_REGISTRY.values()
    ]


def execute_registered_tool_handler(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    definition = TOOL_HANDLER_REGISTRY.get(tool_name)

    if definition is None:
        raise ValueError(f"no handler registered for tool: {tool_name}")

    return definition["handler"](arguments or {})

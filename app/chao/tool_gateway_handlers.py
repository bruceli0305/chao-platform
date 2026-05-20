import contextlib
import importlib
from collections.abc import Callable
from io import StringIO
from typing import Any, TypedDict

from app.chao.permissions import ROLE_ALLOWED_TOOLS, get_tool
from app.chao.runner_validation import execute_runner_validation_commands


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


def _coerce_string_list(value: Any, *, name: str) -> list[str]:
    if isinstance(value, str):
        return [value]

    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value

    raise ValueError(f"{name} must be a string or list of strings")


def _run_runner_validate(arguments: dict[str, Any]) -> dict[str, Any]:
    gates = _coerce_string_list(arguments.get("gates") or arguments.get("gate"), name="gates")
    timeout_seconds = int(arguments.get("timeout_seconds", 120))

    return execute_runner_validation_commands(
        gates,
        timeout_seconds=timeout_seconds,
    )


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
    "cli.runner_validate": {
        "tool_name": "cli.runner_validate",
        "description": "Run allowlisted Agent Runner validation gates.",
        "handler": _run_runner_validate,
    },
}


def _allowed_roles_for_tool(tool_name: str) -> list[str]:
    return sorted(role for role, tools in ROLE_ALLOWED_TOOLS.items() if tool_name in tools)


def list_tool_handlers() -> list[dict[str, Any]]:
    handlers = []

    for definition in TOOL_HANDLER_REGISTRY.values():
        tool = get_tool(definition["tool_name"])
        handlers.append(
            {
                "tool_name": definition["tool_name"],
                "description": definition["description"],
                "category": tool["category"],
                "risk": tool["risk"],
                "permission_policy": tool["permission_policy"],
                "allowed_roles": _allowed_roles_for_tool(definition["tool_name"]),
            }
        )

    return handlers


def execute_registered_tool_handler(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    definition = TOOL_HANDLER_REGISTRY.get(tool_name)

    if definition is None:
        raise ValueError(f"no handler registered for tool: {tool_name}")

    return definition["handler"](arguments or {})

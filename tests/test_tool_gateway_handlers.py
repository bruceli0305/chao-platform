import sys
import types

from app.chao import tool_gateway_handlers
from app.chao.tool_gateway_handlers import (
    execute_registered_tool_handler,
    list_tool_handlers,
)


def test_list_tool_handlers_exposes_safe_gate_handlers():
    tool_names = {tool["tool_name"] for tool in list_tool_handlers()}

    assert {"schema_check", "data_boundary_check", "cli.runner_validate"} <= tool_names


def test_execute_registered_tool_handler_reports_unknown_tool():
    try:
        execute_registered_tool_handler("unknown_tool")
    except ValueError as exc:
        assert str(exc) == "no handler registered for tool: unknown_tool"
    else:
        raise AssertionError("expected unknown tool to raise ValueError")


def test_run_script_main_captures_output(monkeypatch):
    module_name = "tests.fake_gateway_script"

    def main():
        print("gate passed")
        return 0

    monkeypatch.setitem(sys.modules, module_name, types.SimpleNamespace(main=main))

    result = tool_gateway_handlers._run_script_main(module_name)

    assert result == {
        "exit_code": 0,
        "stdout": "gate passed\n",
        "stderr": "",
    }


def test_execute_registered_tool_handler_runs_runner_validate(monkeypatch):
    calls = []

    def fake_validate(gates, *, timeout_seconds):
        calls.append((gates, timeout_seconds))
        return {
            "quality": "ok",
            "checks": gates,
            "plan": [],
            "command_results": [],
            "deliverable": True,
            "note": "validated",
        }

    monkeypatch.setattr(
        tool_gateway_handlers,
        "execute_runner_validation_commands",
        fake_validate,
    )

    result = execute_registered_tool_handler(
        "cli.runner_validate",
        {"gate": "lint", "timeout_seconds": 30},
    )

    assert calls == [(["lint"], 30)]
    assert result["deliverable"] is True


def test_execute_registered_tool_handler_rejects_invalid_runner_validate_gates():
    try:
        execute_registered_tool_handler("cli.runner_validate", {"gates": [123]})
    except ValueError as exc:
        assert str(exc) == "gates must be a string or list of strings"
    else:
        raise AssertionError("expected invalid gates to raise ValueError")

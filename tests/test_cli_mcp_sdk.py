from typer.testing import CliRunner

from app.chao import cli


def test_mcp_sdk_smoke_runs_default_initialize_and_list(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli,
        "run_mcp_sdk_client_smoke_sync",
        lambda call_tool=None, tool_arguments=None: (
            calls.append((call_tool, tool_arguments))
            or {
                "status": "success",
                "sdk": {"installed": True, "package": "mcp"},
                "tool_count": 2,
                "tools": [{"name": "schema_check"}, {"name": "data_boundary_check"}],
                "call_tool": call_tool,
                "call_result": None,
            }
        ),
    )

    result = CliRunner().invoke(cli.app, ["mcp-sdk-smoke"])

    assert result.exit_code == 0
    assert calls == [(None, {})]
    assert '"status": "success"' in result.output
    assert "schema_check" in result.output


def test_mcp_sdk_smoke_passes_optional_tool_call_arguments(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli,
        "run_mcp_sdk_client_smoke_sync",
        lambda call_tool=None, tool_arguments=None: (
            calls.append((call_tool, tool_arguments))
            or {
                "status": "success",
                "sdk": {"installed": True, "package": "mcp"},
                "tool_count": 1,
                "tools": [{"name": "data_boundary_check"}],
                "call_tool": call_tool,
                "call_result": {"isError": False},
            }
        ),
    )

    result = CliRunner().invoke(
        cli.app,
        [
            "mcp-sdk-smoke",
            "--call-tool",
            "data_boundary_check",
            "--arguments-json",
            '{"agent_name": "xingbu"}',
        ],
    )

    assert result.exit_code == 0
    assert calls == [("data_boundary_check", {"agent_name": "xingbu"})]
    assert "data_boundary_check" in result.output


def test_mcp_sdk_smoke_rejects_non_object_arguments():
    result = CliRunner().invoke(
        cli.app,
        ["mcp-sdk-smoke", "--arguments-json", '["not-object"]'],
    )

    assert result.exit_code == 1
    assert "MCP tool arguments JSON must be an object" in result.output


def test_mcp_sdk_smoke_exits_nonzero_when_sdk_smoke_fails(monkeypatch):
    monkeypatch.setattr(
        cli,
        "run_mcp_sdk_client_smoke_sync",
        lambda call_tool=None, tool_arguments=None: {
            "status": "failed",
            "sdk": {"installed": False, "package": "mcp"},
            "error": "Official MCP Python SDK is not installed.",
        },
    )

    result = CliRunner().invoke(cli.app, ["mcp-sdk-smoke"])

    assert result.exit_code == 1
    assert '"status": "failed"' in result.output
    assert "Official MCP Python SDK is not installed" in result.output

from app.chao.permissions import (
    TOOL_REGISTRY,
    evaluate_tool_permission,
    get_tool,
    list_tools,
    require_tool_permission,
)


def test_tool_registry_contains_first_batch():
    assert set(TOOL_REGISTRY) == {
        "cli.new",
        "cli.approve",
        "schema_check",
        "data_boundary_check",
    }
    assert {tool["name"] for tool in list_tools()} == set(TOOL_REGISTRY)


def test_get_tool_returns_policy_metadata():
    tool = get_tool("schema_check")

    assert tool["category"] == "postgres.read"
    assert tool["permission_policy"] == "schema-read-validation"


def test_shangshu_can_create_task():
    decision = evaluate_tool_permission(
        agent_name="shangshu",
        tool_name="cli.new",
        task_level="L2",
        required_confirmation="B",
        current_status="CLASSIFIED",
    )

    assert decision["allowed"] is True
    assert decision["permission_policy"] == "local-cli-task-create"
    assert decision["risk_flag"] is None


def test_emperor_can_approve_l3_waiting_task():
    decision = evaluate_tool_permission(
        agent_name="emperor",
        tool_name="cli.approve",
        task_level="L3",
        required_confirmation="A",
        current_status="NEED_CONFIRMATION",
    )

    assert decision["allowed"] is True
    assert decision["permission_policy"] == "human-approval-required"
    assert decision["requires_confirmation"] is True
    assert decision["risk_flag"] == "A_CONFIRMATION"


def test_high_risk_tool_requires_waiting_confirmation_state():
    decision = evaluate_tool_permission(
        agent_name="emperor",
        tool_name="cli.approve",
        task_level="L3",
        required_confirmation="A",
        current_status="CLASSIFIED",
    )

    assert decision["allowed"] is False
    assert decision["permission_policy"] == "a-confirmation-required"
    assert decision["risk_flag"] == "A_CONFIRMATION_REQUIRED"


def test_role_denied_tool_call():
    decision = evaluate_tool_permission(
        agent_name="gongbu",
        tool_name="cli.approve",
        task_level="L3",
        required_confirmation="A",
        current_status="NEED_CONFIRMATION",
    )

    assert decision["allowed"] is False
    assert decision["permission_policy"] == "role-tool-denied"
    assert decision["risk_flag"] == "ROLE_TOOL_DENIED"


def test_unknown_tool_is_denied():
    decision = evaluate_tool_permission(
        agent_name="xingbu",
        tool_name="shell.unrestricted",
        task_level="L2",
        required_confirmation="B",
        current_status="CLASSIFIED",
    )

    assert decision["allowed"] is False
    assert decision["permission_policy"] == "unknown-tool"
    assert decision["risk_flag"] == "UNKNOWN_TOOL"


def test_require_tool_permission_returns_allowed_decision():
    decision = require_tool_permission(
        agent_name="shangshu",
        tool_name="cli.new",
        task_level="L1",
        required_confirmation="none",
        current_status="DELIVERED",
    )

    assert decision["allowed"] is True
    assert decision["permission_policy"] == "local-cli-task-create"


def test_require_tool_permission_raises_for_denied_decision():
    try:
        require_tool_permission(
            agent_name="gongbu",
            tool_name="cli.approve",
            task_level="L3",
            required_confirmation="A",
            current_status="NEED_CONFIRMATION",
        )
    except PermissionError as exc:
        assert "未授权调用" in str(exc)
    else:
        raise AssertionError("expected PermissionError")

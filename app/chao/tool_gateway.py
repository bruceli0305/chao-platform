from collections.abc import Callable
from typing import Any, NotRequired, TypedDict

from app.chao.permissions import PermissionDecision, evaluate_tool_permission
from app.chao.state import TaskLevel


class ToolGatewayRequest(TypedDict):
    protocol: str
    agent_name: str
    tool_name: str
    task_level: TaskLevel
    required_confirmation: str
    current_status: str
    arguments_summary: str
    task_id: NotRequired[str]


class ToolGatewayResponse(TypedDict):
    allowed: bool
    result_status: str
    permission_decision: PermissionDecision
    output: Any
    error: str | None
    audit: dict[str, Any]


def build_tool_gateway_audit(
    request: ToolGatewayRequest,
    decision: PermissionDecision,
    *,
    result_status: str,
    output_summary: str = "",
) -> dict[str, Any]:
    audit = {
        "task_id": request.get("task_id"),
        "agent_name": request["agent_name"],
        "tool_name": request["tool_name"],
        "arguments_summary": request["arguments_summary"],
        "permission_policy": decision["permission_policy"],
        "permission_decision": decision,
        "result_status": result_status,
        "risk_flag": decision["risk_flag"],
        "output_summary": output_summary,
        "protocol": request["protocol"],
    }

    return audit


def evaluate_tool_gateway_request(request: ToolGatewayRequest) -> ToolGatewayResponse:
    decision = evaluate_tool_permission(
        agent_name=request["agent_name"],
        tool_name=request["tool_name"],
        task_level=request["task_level"],
        required_confirmation=request["required_confirmation"],
        current_status=request["current_status"],
    )
    result_status = "allowed" if decision["allowed"] else "denied"

    return {
        "allowed": decision["allowed"],
        "result_status": result_status,
        "permission_decision": decision,
        "output": None,
        "error": None if decision["allowed"] else decision["reason"],
        "audit": build_tool_gateway_audit(
            request,
            decision,
            result_status=result_status,
            output_summary=decision["reason"],
        ),
    }


def execute_tool_gateway_request(
    request: ToolGatewayRequest,
    handler: Callable[[], Any],
) -> ToolGatewayResponse:
    evaluated = evaluate_tool_gateway_request(request)

    if not evaluated["allowed"]:
        return evaluated

    decision = evaluated["permission_decision"]

    try:
        output = handler()
    except Exception as exc:
        return {
            "allowed": True,
            "result_status": "failed",
            "permission_decision": decision,
            "output": None,
            "error": str(exc),
            "audit": build_tool_gateway_audit(
                request,
                decision,
                result_status="failed",
                output_summary=str(exc),
            ),
        }

    return {
        "allowed": True,
        "result_status": "success",
        "permission_decision": decision,
        "output": output,
        "error": None,
        "audit": build_tool_gateway_audit(
            request,
            decision,
            result_status="success",
            output_summary=str(output)[:500],
        ),
    }


def persist_tool_gateway_audit(
    audit: dict[str, Any],
    *,
    recorder: Callable[..., None] | None = None,
) -> bool:
    task_id = audit.get("task_id")

    if not task_id:
        return False

    if recorder is None:
        from app.chao.services.tool_calls import record_tool_call

        recorder = record_tool_call

    recorder(
        task_id=str(task_id),
        agent_name=str(audit["agent_name"]),
        tool_name=str(audit["tool_name"]),
        arguments_summary=audit.get("arguments_summary"),
        permission_policy=audit.get("permission_policy"),
        result_status=str(audit["result_status"]),
        permission_decision=audit.get("permission_decision"),
        output_summary=audit.get("output_summary"),
        risk_flag=audit.get("risk_flag"),
    )

    return True


def start_tool_gateway_audit(
    audit: dict[str, Any],
    *,
    starter: Callable[..., str] | None = None,
) -> str | None:
    task_id = audit.get("task_id")

    if not task_id:
        return None

    if starter is None:
        from app.chao.services.tool_calls import start_tool_call

        starter = start_tool_call

    return starter(
        task_id=str(task_id),
        agent_name=str(audit["agent_name"]),
        tool_name=str(audit["tool_name"]),
        arguments_summary=audit.get("arguments_summary"),
        permission_policy=audit.get("permission_policy"),
        permission_decision=audit.get("permission_decision"),
        risk_flag=audit.get("risk_flag"),
    )


def finish_tool_gateway_audit(
    tool_call_id: str | None,
    audit: dict[str, Any],
    *,
    finisher: Callable[..., None] | None = None,
) -> bool:
    if not tool_call_id:
        return False

    if finisher is None:
        from app.chao.services.tool_calls import finish_tool_call

        finisher = finish_tool_call

    finisher(
        tool_call_id,
        result_status=str(audit["result_status"]),
        output_summary=audit.get("output_summary"),
        permission_decision=audit.get("permission_decision"),
        risk_flag=audit.get("risk_flag"),
    )

    return True


def execute_audited_tool_gateway_request(
    request: ToolGatewayRequest,
    handler: Callable[[], Any],
) -> dict[str, Any]:
    evaluated = evaluate_tool_gateway_request(request)
    tool_call_id = start_tool_gateway_audit(evaluated["audit"])

    if not evaluated["allowed"]:
        evaluated["audit_persisted"] = tool_call_id is not None
        evaluated["audit_completed"] = finish_tool_gateway_audit(
            tool_call_id,
            evaluated["audit"],
        )
        return evaluated

    result = execute_tool_gateway_request(request, handler)
    result["audit_persisted"] = tool_call_id is not None
    result["audit_completed"] = finish_tool_gateway_audit(tool_call_id, result["audit"])
    return result

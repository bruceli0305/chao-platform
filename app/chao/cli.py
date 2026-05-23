import json
import time
import uuid
from datetime import datetime
from typing import Annotated

import typer
from rich import print, print_json
from rich.console import Console
from rich.table import Table

from app.chao.agents import list_agents, validate_agent_registry, validate_self_upgrade_readiness
from app.chao.doctor import run_chao_doctor
from app.chao.github_ci import execute_github_pr_checks
from app.chao.github_pr import build_self_upgrade_pr_body, execute_github_pr_create
from app.chao.governance import build_governance_check_result, list_self_upgrade_governance_agents
from app.chao.graph.main_graph import build_graph
from app.chao.llm_client import execute_llm_chat_completion
from app.chao.llm_context import build_llm_task_prompt
from app.chao.llm_policy import (
    evaluate_llm_egress_policy,
    is_data_classification_covered,
    is_llm_provider_model_allowlisted,
    normalize_data_classification,
    resolve_task_data_classification,
)
from app.chao.llm_providers import build_llm_provider_config, list_llm_provider_defaults
from app.chao.mcp_sdk import run_mcp_sdk_client_smoke_sync
from app.chao.mcp_server import serve_mcp
from app.chao.permissions import require_tool_permission
from app.chao.repositories import (
    get_repository_config,
    list_repository_configs,
    validate_repository_configs,
)
from app.chao.repository_sync import (
    build_repository_doctor_report,
    build_repository_status_report,
    execute_repository_sync,
    inspect_repository_status,
)
from app.chao.runner_artifacts import save_failure_feedback_artifact, save_patch_artifact
from app.chao.runner_branch import create_runner_branch
from app.chao.runner_executor import (
    apply_text_patch_operations,
    build_implementation_result_from_execution,
)
from app.chao.runner_policy import build_runner_branch_plan, build_runner_workspace_plan
from app.chao.runner_preflight import (
    build_runner_preflight_result,
    require_runner_preflight_ready,
)
from app.chao.runner_sandbox import DEFAULT_SANDBOX_IMAGE, execute_runner_sandbox_commands
from app.chao.runner_validation import execute_runner_validation_commands
from app.chao.runner_workspace import create_runner_workspace
from app.chao.self_upgrade import (
    SELF_UPGRADE_SYSTEM_PROMPT,
    build_self_upgrade_prompt,
    extract_llm_response_text,
    parse_self_upgrade_plan,
)
from app.chao.self_upgrade_delivery import execute_self_upgrade_delivery
from app.chao.services.artifacts import record_artifact
from app.chao.services.console import (
    get_console_approval_queue,
    get_console_audit,
    get_console_gates,
    get_console_github_sync,
    get_console_overview,
    get_console_risks,
)
from app.chao.services.data_assets import record_data_asset
from app.chao.services.events import record_task_event
from app.chao.services.github_links import normalize_github_link_type, record_github_link
from app.chao.services.llm_egress_authorizations import (
    list_expired_llm_egress_authorizations,
    mark_llm_egress_authorizations_expired,
    record_llm_egress_authorization,
)
from app.chao.services.markdown_records import save_task_markdown
from app.chao.services.store import (
    approve_task,
    get_task_detail,
    list_tasks,
    save_task_result,
    update_task_status,
)
from app.chao.services.tool_calls import (
    DEFAULT_STALE_PENDING_TOOL_CALL_MINUTES,
    list_stale_pending_tool_calls,
    mark_stale_pending_tool_calls_timed_out,
    record_tool_call,
)
from app.chao.skills import list_skills, validate_skill_manifests
from app.chao.tool_gateway import (
    ToolGatewayRequest,
    evaluate_tool_gateway_request,
    execute_audited_tool_gateway_request,
)
from app.chao.tool_gateway_handlers import execute_registered_tool_handler, list_tool_handlers
from app.chao.tool_gateway_server import serve_tool_gateway
from app.chao.web_console import run_web_console_server

app = typer.Typer()
console = Console()


def _display_value(value: object) -> str:
    if value is None:
        return ""

    return str(value)


def _resolve_task_validation_gates(
    task: dict[str, object],
    gates: list[str] | tuple[str, ...] | None,
) -> list[str]:
    if gates:
        return [str(gate) for gate in gates]

    skill_execution_plan = task.get("skill_execution_plan")
    if isinstance(skill_execution_plan, dict):
        combined_gates = skill_execution_plan.get("combined_gates")
        if isinstance(combined_gates, list) and combined_gates:
            return [str(gate) for gate in combined_gates]

    route_result = task.get("route_result")
    if isinstance(route_result, dict):
        required_gates = route_result.get("required_gates")
        if isinstance(required_gates, list) and required_gates:
            return [str(gate) for gate in required_gates]

    required_gates = task.get("required_gates")
    if isinstance(required_gates, list) and required_gates:
        return [str(gate) for gate in required_gates]

    raise ValueError("No validation gates provided or recorded for this task.")


def _build_runner_preflight_summary(preflight: dict[str, object], repository_name: str) -> str:
    summary = f"Runner preflight {preflight['status']}: {repository_name}"
    errors = preflight.get("errors")
    if errors:
        summary = f"{summary}; errors={'; '.join(str(error) for error in errors)}"

    return summary


def _record_runner_repository_preflight(
    task: dict[str, object],
    repository_config,
    validation_gates: list[str] | None = None,
    *,
    require_validation_gates: bool = True,
    by: str = "gongbu",
):
    permission_decision = require_tool_permission(
        agent_name=by,
        tool_name="cli.runner_preflight",
        task_level=task["task_level"],
        required_confirmation=task.get("route_result", {}).get(
            "required_confirmation",
            "none",
        ),
        current_status=task["status"],
    )
    preflight = build_runner_preflight_result(
        task,
        repository_config,
        validation_gates,
        require_validation_gates=require_validation_gates,
    )
    result_status = "success" if not preflight["errors"] else "failed"
    event_type = (
        "runner_preflight_ready" if result_status == "success" else "runner_preflight_blocked"
    )
    record_task_event(
        task_id=task["id"],
        event_type=event_type,
        from_status=task["status"],
        to_status=task["status"],
        summary=_build_runner_preflight_summary(preflight, repository_config.name),
        created_by=by,
    )
    record_tool_call(
        task_id=task["id"],
        agent_name=by,
        tool_name="cli.runner_preflight",
        arguments_summary=(
            f"task_code={task['task_code']}; repository={repository_config.name}; "
            f"gates={preflight['validation_gates']}"
        ),
        permission_policy=permission_decision["permission_policy"],
        result_status=result_status,
        permission_decision=permission_decision,
        output_summary=(
            f"status={preflight['status']}; "
            f"suggested_action={preflight['repository_doctor']['suggested_action']}; "
            f"errors={preflight['errors']}"
        ),
        risk_flag=permission_decision["risk_flag"],
    )

    return preflight


def _require_runner_repository_preflight(
    task: dict[str, object],
    repository_config,
    validation_gates: list[str] | None = None,
    *,
    require_validation_gates: bool = True,
    by: str = "gongbu",
):
    preflight = _record_runner_repository_preflight(
        task,
        repository_config,
        validation_gates,
        require_validation_gates=require_validation_gates,
        by=by,
    )
    return require_runner_preflight_ready(preflight)


@app.command()
def new(title: str, request: str):
    task_id = str(uuid.uuid4())
    task_code = "TASK-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")

    graph = build_graph()

    result = graph.invoke(
        {
            "task_id": task_id,
            "task_code": task_code,
            "title": title,
            "raw_request": request,
            "status": "RAW",
        }
    )

    save_task_result(result)
    markdown_path = save_task_markdown(result)

    record_artifact(
        task_id=task_id,
        artifact_type="markdown_record",
        artifact_uri=str(markdown_path),
        access_level="internal",
        retention_days=365,
        summary="任务级 Markdown 史官记录",
    )

    record_data_asset(
        asset_name=str(markdown_path),
        asset_type="markdown_record",
        classification="D1",
        primary_storage="Git / Markdown",
        owner="historian",
        task_id=task_id,
        allowed_copies=["PostgreSQL", "pgvector"],
        forbidden_storages=["Secret Manager"],
        allow_vectorization=True,
        desensitized=True,
        retention_days=365,
        notes="任务级 Markdown 史官记录，可作为脱敏工程知识进入检索索引。",
    )

    result["markdown_record"] = str(markdown_path)

    print_json(data=result)


@app.command("list")
def list_command(limit: int = 10):
    tasks = list_tasks(limit)

    table = Table(title="Chao Tasks")
    table.add_column("Task Code")
    table.add_column("Title")
    table.add_column("Level")
    table.add_column("Status")
    table.add_column("Owner")
    table.add_column("Created At")

    for task in tasks:
        table.add_row(
            task["task_code"],
            task["title"],
            task["task_level"],
            task["status"],
            task["owner"],
            task["created_at"],
        )

    console.print(table)


@app.command()
def show(task_code: str):
    task = get_task_detail(task_code)

    if not task:
        print(f"[red]Task not found:[/red] {task_code}")
        raise typer.Exit(code=1)

    print_json(data=task)


@app.command("console")
def console_command(
    limit: int = typer.Option(10, "--limit", help="最近任务数量"),
    as_json: bool = typer.Option(False, "--json", help="输出 JSON"),
):
    overview = get_console_overview(limit=limit)

    if as_json:
        print_json(data=overview)
        return

    summary = Table(title="Chao Console Overview")
    summary.add_column("Metric")
    summary.add_column("Value")
    summary.add_row("Artifacts", str(overview["artifact_count"]))
    summary.add_row("Data Assets", str(overview["data_asset_count"]))
    summary.add_row("Approved Confirmations", str(overview["approved_confirmations"]))
    summary.add_row(
        "Active LLM Egress Authorizations",
        str(overview["active_llm_egress_authorization_count"]),
    )
    summary.add_row("Failed Tool Calls", str(overview["failed_tool_call_count"]))
    console.print(summary)

    status_table = Table(title="Task Status")
    status_table.add_column("Status")
    status_table.add_column("Count")
    for status, count in overview["task_status_counts"].items():
        status_table.add_row(status, str(count))
    console.print(status_table)

    recent = Table(title="Recent Tasks")
    recent.add_column("Task Code")
    recent.add_column("Title")
    recent.add_column("Level")
    recent.add_column("Status")
    recent.add_column("Owner")
    for task in overview["recent_tasks"]:
        recent.add_row(
            task["task_code"],
            task["title"],
            task["task_level"],
            task["status"],
            task["owner"],
        )
    console.print(recent)


@app.command("console-task")
def console_task_command(
    task_code: str,
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
):
    task = get_task_detail(task_code)

    if not task:
        print(f"[red]Task not found:[/red] {task_code}")
        raise typer.Exit(code=1)

    if as_json:
        print_json(data=task)
        return

    summary = Table(title="Task Detail")
    summary.add_column("Field")
    summary.add_column("Value")
    for field in (
        "task_code",
        "title",
        "task_level",
        "status",
        "owner",
        "created_at",
        "updated_at",
    ):
        summary.add_row(field, _display_value(task.get(field)))
    console.print(summary)

    counts = Table(title="Audit Counts")
    counts.add_column("Record")
    counts.add_column("Count")
    for name in (
        "events",
        "tool_calls",
        "artifacts",
        "data_assets",
        "skill_usage",
        "llm_egress_authorizations",
        "github_links",
        "historian_records",
        "gate_results",
    ):
        counts.add_row(name, str(len(task.get(name, []))))
    console.print(counts)

    artifacts = Table(title="Artifacts")
    artifacts.add_column("Type")
    artifacts.add_column("URI")
    artifacts.add_column("Access")
    for artifact in task.get("artifacts", []):
        artifacts.add_row(
            _display_value(artifact.get("artifact_type")),
            _display_value(artifact.get("artifact_uri")),
            _display_value(artifact.get("access_level")),
        )
    console.print(artifacts)

    data_assets = Table(title="Data Assets")
    data_assets.add_column("Type")
    data_assets.add_column("Class")
    data_assets.add_column("Owner")
    data_assets.add_column("Storage")
    for asset in task.get("data_assets", []):
        data_assets.add_row(
            _display_value(asset.get("asset_type")),
            _display_value(asset.get("classification")),
            _display_value(asset.get("owner")),
            _display_value(asset.get("primary_storage")),
        )
    console.print(data_assets)

    skill_usage = Table(title="Skill Usage")
    skill_usage.add_column("Skill")
    skill_usage.add_column("Status")
    skill_usage.add_column("SHA256")
    for skill in task.get("skill_usage", []):
        skill_usage.add_row(
            _display_value(skill.get("name")),
            _display_value(skill.get("status")),
            _display_value(skill.get("content_sha256")),
        )
    console.print(skill_usage)

    skill_plan = Table(title="Skill Execution Plan")
    skill_plan.add_column("Skill")
    skill_plan.add_column("Status")
    skill_plan.add_column("Gates")
    for skill in task.get("skill_execution_plan", {}).get("skills", []):
        skill_plan.add_row(
            _display_value(skill.get("name")),
            _display_value(skill.get("status")),
            ", ".join(skill.get("default_gates", [])),
        )
    console.print(skill_plan)

    llm_authorizations = Table(title="LLM Egress Authorizations")
    llm_authorizations.add_column("Provider")
    llm_authorizations.add_column("Model")
    llm_authorizations.add_column("Class")
    llm_authorizations.add_column("Status")
    llm_authorizations.add_column("Active")
    for authorization in task.get("llm_egress_authorizations", []):
        llm_authorizations.add_row(
            _display_value(authorization.get("provider")),
            _display_value(authorization.get("model")),
            _display_value(authorization.get("data_classification")),
            _display_value(authorization.get("status")),
            _display_value(authorization.get("active")),
        )
    console.print(llm_authorizations)

    events = Table(title="Events")
    events.add_column("Type")
    events.add_column("From")
    events.add_column("To")
    events.add_column("By")
    for event in task.get("events", []):
        events.add_row(
            _display_value(event.get("event_type")),
            _display_value(event.get("from_status")),
            _display_value(event.get("to_status")),
            _display_value(event.get("created_by")),
        )
    console.print(events)

    tool_calls = Table(title="Tool Calls")
    tool_calls.add_column("Agent")
    tool_calls.add_column("Tool")
    tool_calls.add_column("Policy")
    tool_calls.add_column("Result")
    for tool_call in task.get("tool_calls", []):
        tool_calls.add_row(
            _display_value(tool_call.get("agent_name")),
            _display_value(tool_call.get("tool_name")),
            _display_value(tool_call.get("permission_policy")),
            _display_value(tool_call.get("result_status")),
        )
    console.print(tool_calls)


@app.command("console-approvals")
def console_approvals_command(
    limit: int = typer.Option(20, "--limit", help="Approval task limit"),
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
):
    approvals = get_console_approval_queue(limit=limit)

    if as_json:
        print_json(data={"count": len(approvals), "approvals": approvals})
        return

    table = Table(title="Pending Approvals")
    table.add_column("Task Code")
    table.add_column("Title")
    table.add_column("Level")
    table.add_column("Required")
    table.add_column("Owner")
    table.add_column("Created At")
    for task in approvals:
        table.add_row(
            _display_value(task.get("task_code")),
            _display_value(task.get("title")),
            _display_value(task.get("task_level")),
            _display_value(task.get("required_confirmation")),
            _display_value(task.get("owner")),
            _display_value(task.get("created_at")),
        )
    console.print(table)


@app.command("console-audit")
def console_audit_command(
    limit: int = typer.Option(20, "--limit", help="Audit record limit per section"),
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
):
    audit = get_console_audit(limit=limit)

    if as_json:
        print_json(data=audit)
        return

    events = Table(title="Recent Events")
    events.add_column("Task")
    events.add_column("Type")
    events.add_column("From")
    events.add_column("To")
    events.add_column("By")
    for event in audit["events"]:
        events.add_row(
            _display_value(event.get("task_code")),
            _display_value(event.get("event_type")),
            _display_value(event.get("from_status")),
            _display_value(event.get("to_status")),
            _display_value(event.get("created_by")),
        )
    console.print(events)

    tool_calls = Table(title="Recent Tool Calls")
    tool_calls.add_column("Task")
    tool_calls.add_column("Agent")
    tool_calls.add_column("Tool")
    tool_calls.add_column("Policy")
    tool_calls.add_column("Result")
    for tool_call in audit["tool_calls"]:
        tool_calls.add_row(
            _display_value(tool_call.get("task_code")),
            _display_value(tool_call.get("agent_name")),
            _display_value(tool_call.get("tool_name")),
            _display_value(tool_call.get("permission_policy")),
            _display_value(tool_call.get("result_status")),
        )
    console.print(tool_calls)

    artifacts = Table(title="Recent Artifacts")
    artifacts.add_column("Task")
    artifacts.add_column("Type")
    artifacts.add_column("URI")
    artifacts.add_column("Access")
    for artifact in audit["artifacts"]:
        artifacts.add_row(
            _display_value(artifact.get("task_code")),
            _display_value(artifact.get("artifact_type")),
            _display_value(artifact.get("artifact_uri")),
            _display_value(artifact.get("access_level")),
        )
    console.print(artifacts)

    data_assets = Table(title="Recent Data Assets")
    data_assets.add_column("Task")
    data_assets.add_column("Type")
    data_assets.add_column("Class")
    data_assets.add_column("Owner")
    for asset in audit["data_assets"]:
        data_assets.add_row(
            _display_value(asset.get("task_code")),
            _display_value(asset.get("asset_type")),
            _display_value(asset.get("classification")),
            _display_value(asset.get("owner")),
        )
    console.print(data_assets)

    github_links = Table(title="Recent GitHub Links")
    github_links.add_column("Task")
    github_links.add_column("Type")
    github_links.add_column("External ID")
    github_links.add_column("Status")
    for link in audit["github_links"]:
        github_links.add_row(
            _display_value(link.get("task_code")),
            _display_value(link.get("link_type")),
            _display_value(link.get("external_id")),
            _display_value(link.get("status")),
        )
    console.print(github_links)

    llm_authorizations = Table(title="Recent LLM Egress Authorizations")
    llm_authorizations.add_column("Task")
    llm_authorizations.add_column("Provider")
    llm_authorizations.add_column("Model")
    llm_authorizations.add_column("Class")
    llm_authorizations.add_column("Active")
    for authorization in audit["llm_egress_authorizations"]:
        llm_authorizations.add_row(
            _display_value(authorization.get("task_code")),
            _display_value(authorization.get("provider")),
            _display_value(authorization.get("model")),
            _display_value(authorization.get("data_classification")),
            _display_value(authorization.get("active")),
        )
    console.print(llm_authorizations)


@app.command("console-gates")
def console_gates_command(
    limit: int = typer.Option(20, "--limit", help="Gate record limit"),
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
):
    gates = get_console_gates(limit=limit)

    if as_json:
        print_json(data=gates)
        return

    status_table = Table(title="Gate Status")
    status_table.add_column("Status")
    status_table.add_column("Count")
    for status, count in gates["gate_status_counts"].items():
        status_table.add_row(status, str(count))
    console.print(status_table)

    permission_table = Table(title="Tool Permission Audit")
    permission_table.add_column("Metric")
    permission_table.add_column("Count")
    for metric, count in gates["tool_permission_audit"].items():
        permission_table.add_row(metric, str(count))
    console.print(permission_table)

    boundary_table = Table(title="Data Boundary Audit")
    boundary_table.add_column("Metric")
    boundary_table.add_column("Count")
    for metric, count in gates["data_boundary_audit"].items():
        boundary_table.add_row(metric, str(count))
    console.print(boundary_table)

    recent = Table(title="Recent Gate Results")
    recent.add_column("Task")
    recent.add_column("Gate")
    recent.add_column("Status")
    recent.add_column("Command")
    for gate in gates["recent_gate_results"]:
        recent.add_row(
            _display_value(gate.get("task_code")),
            _display_value(gate.get("gate_name")),
            _display_value(gate.get("status")),
            _display_value(gate.get("command")),
        )
    console.print(recent)


@app.command("console-risks")
def console_risks_command(
    limit: int = typer.Option(20, "--limit", help="Risk record limit"),
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
):
    risks = get_console_risks(limit=limit)

    if as_json:
        print_json(data=risks)
        return

    summary = Table(title="Risk Summary")
    summary.add_column("Metric")
    summary.add_column("Count")
    for metric, count in risks["summary"].items():
        summary.add_row(metric, str(count))
    console.print(summary)

    blocked = Table(title="Blocked Tasks")
    blocked.add_column("Task")
    blocked.add_column("Title")
    blocked.add_column("Level")
    blocked.add_column("Status")
    for task in risks["blocked_tasks"]:
        blocked.add_row(
            _display_value(task.get("task_code")),
            _display_value(task.get("title")),
            _display_value(task.get("task_level")),
            _display_value(task.get("status")),
        )
    console.print(blocked)

    gates = Table(title="Failed Gates")
    gates.add_column("Task")
    gates.add_column("Gate")
    gates.add_column("Status")
    gates.add_column("Command")
    for gate in risks["failed_gates"]:
        gates.add_row(
            _display_value(gate.get("task_code")),
            _display_value(gate.get("gate_name")),
            _display_value(gate.get("status")),
            _display_value(gate.get("command")),
        )
    console.print(gates)

    runner_failures = Table(title="Runner Failure Feedback")
    runner_failures.add_column("Task")
    runner_failures.add_column("Artifact")
    runner_failures.add_column("URI")
    for failure in risks["runner_failures"]:
        runner_failures.add_row(
            _display_value(failure.get("task_code")),
            _display_value(failure.get("artifact_type")),
            _display_value(failure.get("artifact_uri")),
        )
    console.print(runner_failures)

    preflight_blocks = Table(title="Runner Preflight Blocks")
    preflight_blocks.add_column("Task")
    preflight_blocks.add_column("Summary")
    preflight_blocks.add_column("By")
    preflight_blocks.add_column("Created At")
    for block in risks["runner_preflight_blocks"]:
        preflight_blocks.add_row(
            _display_value(block.get("task_code")),
            _display_value(block.get("summary")),
            _display_value(block.get("created_by")),
            _display_value(block.get("created_at")),
        )
    console.print(preflight_blocks)

    stale_tools = Table(title="Stale Tool Calls")
    stale_tools.add_column("Task")
    stale_tools.add_column("Agent")
    stale_tools.add_column("Tool")
    stale_tools.add_column("Age Minutes")
    for tool_call in risks["stale_tool_calls"]:
        stale_tools.add_row(
            _display_value(tool_call.get("task_code")),
            _display_value(tool_call.get("agent_name")),
            _display_value(tool_call.get("tool_name")),
            _display_value(tool_call.get("age_minutes")),
        )
    console.print(stale_tools)

    pending_tools = Table(title="Pending Tool Calls")
    pending_tools.add_column("Task")
    pending_tools.add_column("Agent")
    pending_tools.add_column("Tool")
    pending_tools.add_column("Started At")
    for tool_call in risks["pending_tool_calls"]:
        pending_tools.add_row(
            _display_value(tool_call.get("task_code")),
            _display_value(tool_call.get("agent_name")),
            _display_value(tool_call.get("tool_name")),
            _display_value(tool_call.get("started_at")),
        )
    console.print(pending_tools)

    tools = Table(title="Tool Risks")
    tools.add_column("Task")
    tools.add_column("Agent")
    tools.add_column("Tool")
    tools.add_column("Result")
    for tool_risk in risks["tool_risks"]:
        tools.add_row(
            _display_value(tool_risk.get("task_code")),
            _display_value(tool_risk.get("agent_name")),
            _display_value(tool_risk.get("tool_name")),
            _display_value(tool_risk.get("result_status")),
        )
    console.print(tools)

    boundary = Table(title="Data Boundary Risks")
    boundary.add_column("Metric")
    boundary.add_column("Count")
    for metric, count in risks["data_boundary_risks"].items():
        boundary.add_row(metric, str(count))
    console.print(boundary)

    github = Table(title="GitHub Risks")
    github.add_column("Task")
    github.add_column("Type")
    github.add_column("External ID")
    github.add_column("Status")
    for link in risks["github_risks"]:
        github.add_row(
            _display_value(link.get("task_code")),
            _display_value(link.get("link_type")),
            _display_value(link.get("external_id")),
            _display_value(link.get("status")),
        )
    console.print(github)

    llm_authorizations = Table(title="Expired LLM Egress Authorizations")
    llm_authorizations.add_column("Task")
    llm_authorizations.add_column("Provider")
    llm_authorizations.add_column("Model")
    llm_authorizations.add_column("Expires At")
    for authorization in risks["expired_llm_egress_authorizations"]:
        llm_authorizations.add_row(
            _display_value(authorization.get("task_code")),
            _display_value(authorization.get("provider")),
            _display_value(authorization.get("model")),
            _display_value(authorization.get("expires_at")),
        )
    console.print(llm_authorizations)


@app.command("console-github-sync")
def console_github_sync_command(
    limit: int = typer.Option(20, "--limit", help="GitHub sync record limit"),
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
):
    github_sync = get_console_github_sync(limit=limit)

    if as_json:
        print_json(data=github_sync)
        return

    summary = Table(title="GitHub Task Sync Summary")
    summary.add_column("Metric")
    summary.add_column("Count")
    for metric, count in github_sync["summary"].items():
        summary.add_row(metric, str(count))
    console.print(summary)

    link_types = Table(title="GitHub Link Types")
    link_types.add_column("Type")
    link_types.add_column("Count")
    for link_type, count in github_sync["link_type_counts"].items():
        link_types.add_row(link_type, str(count))
    console.print(link_types)

    statuses = Table(title="GitHub Link Status")
    statuses.add_column("Status")
    statuses.add_column("Count")
    for status, count in github_sync["status_counts"].items():
        statuses.add_row(status, str(count))
    console.print(statuses)

    recent_links = Table(title="Recent GitHub Sync Links")
    recent_links.add_column("Task")
    recent_links.add_column("Type")
    recent_links.add_column("External ID")
    recent_links.add_column("Status")
    recent_links.add_column("By")
    for link in github_sync["recent_links"]:
        recent_links.add_row(
            _display_value(link.get("task_code")),
            _display_value(link.get("link_type")),
            _display_value(link.get("external_id")),
            _display_value(link.get("status")),
            _display_value(link.get("created_by")),
        )
    console.print(recent_links)

    delivery_events = Table(title="Recent GitHub Delivery Events")
    delivery_events.add_column("Task")
    delivery_events.add_column("Summary")
    delivery_events.add_column("By")
    delivery_events.add_column("Created At")
    for event in github_sync["recent_delivery_events"]:
        delivery_events.add_row(
            _display_value(event.get("task_code")),
            _display_value(event.get("summary")),
            _display_value(event.get("created_by")),
            _display_value(event.get("created_at")),
        )
    console.print(delivery_events)

    unlinked_tasks = Table(title="Unlinked Delivered Tasks")
    unlinked_tasks.add_column("Task")
    unlinked_tasks.add_column("Title")
    unlinked_tasks.add_column("Level")
    unlinked_tasks.add_column("Owner")
    for task in github_sync["recent_unlinked_delivered_tasks"]:
        unlinked_tasks.add_row(
            _display_value(task.get("task_code")),
            _display_value(task.get("title")),
            _display_value(task.get("task_level")),
            _display_value(task.get("owner")),
        )
    console.print(unlinked_tasks)

    failed_links = Table(title="Failed GitHub Sync Links")
    failed_links.add_column("Task")
    failed_links.add_column("Type")
    failed_links.add_column("External ID")
    failed_links.add_column("Status")
    for link in github_sync["failed_links"]:
        failed_links.add_row(
            _display_value(link.get("task_code")),
            _display_value(link.get("link_type")),
            _display_value(link.get("external_id")),
            _display_value(link.get("status")),
        )
    console.print(failed_links)


@app.command("console-repositories")
def console_repositories_command(
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
):
    repository_status = build_repository_status_report(list_repository_configs())

    if as_json:
        print_json(data=repository_status)
        return

    summary = Table(title="Repository Workspace Summary")
    summary.add_column("Metric")
    summary.add_column("Value")
    for metric, count in repository_status["summary"].items():
        summary.add_row(metric, str(count))
    console.print(summary)

    table = Table(title="Repository Workspaces")
    table.add_column("Name", no_wrap=True)
    table.add_column("Ready", no_wrap=True)
    table.add_column("Branch")
    table.add_column("Workspace")
    table.add_column("Dirty", no_wrap=True)
    table.add_column("Ahead", no_wrap=True)
    table.add_column("Behind", no_wrap=True)
    table.add_column("Errors")

    for repository in repository_status["repositories"]:
        table.add_row(
            str(repository["name"]),
            str(repository["workspace_ready"]),
            str(repository["current_branch"] or ""),
            str(repository["workspace_path"]),
            str(repository["dirty"]),
            str(repository["ahead"] if repository["ahead"] is not None else ""),
            str(repository["behind"] if repository["behind"] is not None else ""),
            str(repository["errors"]),
        )

    console.print(table)


@app.command("web-console")
def web_console_command(
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host"),
    port: int = typer.Option(8765, "--port", help="Bind port"),
):
    print(f"Chao Web Console listening on http://{host}:{port}")
    run_web_console_server(host=host, port=port)


@app.command("tool-gateway-serve")
def tool_gateway_serve_command():
    raise typer.Exit(code=serve_tool_gateway())


@app.command("tool-gateway-tools")
def tool_gateway_tools_command(
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
):
    tools = list_tool_handlers()

    if as_json:
        print_json(data={"tools": tools})
        return

    table = Table(title="Tool Gateway Tools")
    table.add_column("Tool", no_wrap=True)
    table.add_column("Category", no_wrap=True)
    table.add_column("Risk")
    table.add_column("Policy", no_wrap=True)
    table.add_column("Roles", no_wrap=True)
    table.add_column("Description")

    for tool in tools:
        table.add_row(
            _display_value(tool.get("tool_name")),
            _display_value(tool.get("category")),
            _display_value(tool.get("risk")),
            _display_value(tool.get("permission_policy")),
            ", ".join(tool.get("allowed_roles", [])),
            _display_value(tool.get("description")),
        )

    console.print(table)


@app.command("tool-gateway-call")
def tool_gateway_call_command(
    task_code: str,
    tool_name: str,
    by: str = typer.Option("xingbu", "--by", help="Agent name"),
    arguments_json: str = typer.Option("{}", "--arguments-json", help="Handler arguments JSON"),
    arguments_summary: str | None = typer.Option(
        None,
        "--arguments-summary",
        help="Audit-safe argument summary",
    ),
    execute: bool = typer.Option(False, "--execute", help="Execute the registered handler"),
):
    task = get_task_detail(task_code)

    if not task:
        print(f"[red]Task not found:[/red] {task_code}")
        raise typer.Exit(code=1)

    try:
        arguments = json.loads(arguments_json)
    except json.JSONDecodeError as exc:
        print(f"[red]Invalid arguments JSON:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not isinstance(arguments, dict):
        print("[red]Tool arguments JSON must be an object.[/red]")
        raise typer.Exit(code=1)

    request: ToolGatewayRequest = {
        "protocol": "cli",
        "agent_name": by,
        "tool_name": tool_name,
        "task_level": task["task_level"],
        "required_confirmation": task.get("route_result", {}).get(
            "required_confirmation",
            "none",
        ),
        "current_status": task["status"],
        "arguments_summary": arguments_summary or f"task_code={task_code}; tool={tool_name}",
        "task_id": task["id"],
    }

    if execute:
        result = execute_audited_tool_gateway_request(
            request,
            lambda: execute_registered_tool_handler(tool_name, arguments),
        )
    else:
        result = evaluate_tool_gateway_request(request)
        result["audit_persisted"] = False
        result["audit_completed"] = False

    print_json(data=result)

    if execute and result["result_status"] != "success":
        raise typer.Exit(code=1)


@app.command("tool-gateway-reconcile")
def tool_gateway_reconcile_command(
    max_age_minutes: int = typer.Option(
        DEFAULT_STALE_PENDING_TOOL_CALL_MINUTES,
        "--max-age-minutes",
        min=1,
        help="Pending tool call age threshold before it is treated as stale.",
    ),
    limit: int = typer.Option(100, "--limit", min=1, max=500, help="Maximum records to scan."),
    apply: bool = typer.Option(False, "--apply", help="Mark stale pending tool calls timed_out."),
    by: str = typer.Option("xingbu", "--by", help="Reconciliation agent name"),
):
    if apply:
        stale_tool_calls = mark_stale_pending_tool_calls_timed_out(
            max_age_minutes=max_age_minutes,
            limit=limit,
        )
        for tool_call in stale_tool_calls:
            record_task_event(
                task_id=tool_call["task_id"],
                event_type="tool_call_timed_out",
                from_status=None,
                to_status=None,
                summary=(
                    f"Tool call {tool_call['tool_name']} timed out after "
                    f"{tool_call['age_minutes']} minute(s)."
                ),
                created_by=by,
            )
    else:
        stale_tool_calls = list_stale_pending_tool_calls(
            max_age_minutes=max_age_minutes,
            limit=limit,
        )

    print_json(
        data={
            "dry_run": not apply,
            "applied": apply,
            "max_age_minutes": max_age_minutes,
            "count": len(stale_tool_calls),
            "stale_tool_calls": stale_tool_calls,
        }
    )


@app.command("mcp-serve")
def mcp_serve_command():
    raise typer.Exit(code=serve_mcp())


@app.command("mcp-sdk-smoke")
def mcp_sdk_smoke_command(
    call_tool: str | None = typer.Option(
        None,
        "--call-tool",
        help="Optional tool name to call after initialize and tools/list.",
    ),
    arguments_json: str = typer.Option(
        "{}",
        "--arguments-json",
        help="Optional MCP tool arguments JSON object.",
    ),
):
    try:
        tool_arguments = json.loads(arguments_json)
    except json.JSONDecodeError as exc:
        print(f"[red]Invalid arguments JSON:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not isinstance(tool_arguments, dict):
        print("[red]MCP tool arguments JSON must be an object.[/red]")
        raise typer.Exit(code=1)

    result = run_mcp_sdk_client_smoke_sync(
        call_tool=call_tool,
        tool_arguments=tool_arguments,
    )

    print_json(data=result)

    if result["status"] != "success":
        raise typer.Exit(code=1)


@app.command("skills-list")
def skills_list_command(
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
):
    skills = list_skills()

    if as_json:
        print_json(data={"skills": skills})
        return

    table = Table(title="Skills")
    table.add_column("Name", no_wrap=True)
    table.add_column("Owner", no_wrap=True)
    table.add_column("Path", no_wrap=True)
    table.add_column("Gates")
    table.add_column("Levels")
    table.add_column("Description")

    for skill in skills:
        table.add_row(
            skill["name"],
            skill["owner_agent"],
            skill["path"],
            ", ".join(skill["default_gates"]),
            ", ".join(skill["allowed_task_levels"]),
            skill["description"],
        )

    console.print(table)


@app.command("agents-list")
def agents_list_command(
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
):
    agents = list_agents()

    if as_json:
        print_json(data={"agents": agents})
        return

    table = Table(title="Agents")
    table.add_column("Name", no_wrap=True)
    table.add_column("Branch")
    table.add_column("Runtime")
    table.add_column("Self-Upgrade")
    table.add_column("Tools")
    table.add_column("Skills")

    for agent in agents:
        table.add_row(
            agent["name"],
            agent["branch"],
            "yes" if agent["runtime_ready"] else "no",
            "yes" if agent["required_for_self_upgrade"] else "no",
            ", ".join(agent["default_tools"]),
            ", ".join(agent["owned_skills"]),
        )

    console.print(table)


@app.command("agents-validate")
def agents_validate_command(
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
):
    errors = validate_agent_registry()
    payload = {
        "status": "failed" if errors else "success",
        "errors": errors,
        "agent_count": len(list_agents()),
    }

    if as_json:
        print_json(data=payload)
    elif errors:
        print("[red]Agent registry validation failed:[/red]")
        for error in errors:
            print(f"- {error}")
    else:
        print(f"[green]Agent registry validation passed:[/green] {payload['agent_count']} agents")

    if errors:
        raise typer.Exit(code=1)


def _execute_governance_check(task: dict[str, object], *, agent: str) -> dict[str, object]:
    permission_decision = require_tool_permission(
        agent_name=agent,
        tool_name="cli.governance_check",
        task_level=task["task_level"],
        required_confirmation=task.get("route_result", {}).get(
            "required_confirmation",
            "none",
        ),
        current_status=task["status"],
    )
    result = build_governance_check_result(task, agent_name=agent)

    record_task_event(
        task_id=task["id"],
        event_type=f"{agent}_governance_{result['status']}",
        from_status=task["status"],
        to_status=task["status"],
        summary=result["summary"],
        created_by=agent,
    )
    record_tool_call(
        task_id=task["id"],
        agent_name=agent,
        tool_name="cli.governance_check",
        arguments_summary=(
            f"task_code={task['task_code']}; agent={agent}; "
            f"missing_artifacts={result['missing_artifacts']}"
        ),
        permission_policy=permission_decision["permission_policy"],
        result_status="success" if result["deliverable"] else result["status"],
        permission_decision=permission_decision,
        output_summary=result["summary"],
        risk_flag=permission_decision["risk_flag"]
        or ("GOVERNANCE_BLOCKED" if not result["deliverable"] else None),
    )

    return result


def _execute_self_upgrade_governance_checks(task: dict[str, object]) -> list[dict[str, object]]:
    return [
        _execute_governance_check(task, agent=agent)
        for agent in list_self_upgrade_governance_agents(task)
    ]


@app.command("governance-check")
def governance_check_command(
    task_code: str,
    agent: str = typer.Option(..., "--agent", help="Governance agent: menxia, hubu, bingbu"),
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
):
    task = get_task_detail(task_code)

    if not task:
        print(f"[red]Task not found:[/red] {task_code}")
        raise typer.Exit(code=1)

    try:
        result = _execute_governance_check(task, agent=agent)
    except (PermissionError, ValueError) as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if as_json:
        print_json(data=result)
    else:
        table = Table(title=f"{agent} Governance Check")
        table.add_column("Artifact")
        table.add_column("Present")
        table.add_column("URI")
        for artifact in result["required_artifacts"]:
            table.add_row(
                artifact["artifact_type"],
                "yes" if artifact["present"] else "no",
                _display_value(artifact["artifact_uri"]),
            )
        console.print(table)
        print(result["summary"])

    if not result["deliverable"]:
        raise typer.Exit(code=1)


@app.command("skills-validate")
def skills_validate_command(
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
):
    errors = validate_skill_manifests()
    payload = {
        "status": "failed" if errors else "success",
        "errors": errors,
        "skill_count": len(list_skills()),
    }

    if as_json:
        print_json(data=payload)
    elif errors:
        print("[red]Skill manifest validation failed:[/red]")
        for error in errors:
            print(f"- {error}")
    else:
        print(f"[green]Skill manifest validation passed:[/green] {payload['skill_count']} skills")

    if errors:
        raise typer.Exit(code=1)


@app.command("repositories-list")
def repositories_list_command(
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
):
    repositories = [repository.to_safe_dict() for repository in list_repository_configs()]

    if as_json:
        print_json(data={"repositories": repositories})
        return

    table = Table(title="Repositories")
    table.add_column("Name", no_wrap=True)
    table.add_column("Default Branch", no_wrap=True)
    table.add_column("Workspace")
    table.add_column("Sandbox")
    table.add_column("Branch Prefix", no_wrap=True)
    table.add_column("Enabled")

    for repository in repositories:
        table.add_row(
            str(repository["name"]),
            str(repository["default_branch"]),
            str(repository["workspace_path"]),
            str(repository["sandbox_root"]),
            str(repository["branch_prefix"]),
            str(repository["enabled"]),
        )

    console.print(table)


@app.command("repository-show")
def repository_show_command(
    repository: str | None = typer.Argument(None, help="Repository name"),
):
    try:
        config = get_repository_config(repository).to_safe_dict()
    except ValueError as exc:
        print_json(data={"status": "failed", "error": str(exc)})
        raise typer.Exit(code=1) from exc

    print_json(data={"repository": config})


@app.command("repositories-validate")
def repositories_validate_command(
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
):
    errors = validate_repository_configs()
    payload = {
        "status": "failed" if errors else "success",
        "errors": errors,
        "repository_count": len(list_repository_configs()) if not errors else 0,
    }

    if as_json:
        print_json(data=payload)
    elif errors:
        print("[red]Repository configuration validation failed:[/red]")
        for error in errors:
            print(f"- {error}")
    else:
        print(
            f"[green]Repository configuration validation passed:[/green] "
            f"{payload['repository_count']} repositories"
        )

    if errors:
        raise typer.Exit(code=1)


@app.command("repository-sync")
def repository_sync_command(
    repository: str | None = typer.Argument(None, help="Repository name"),
    pull_ff_only: bool = typer.Option(
        False,
        "--pull-ff-only",
        help="Use git pull --ff-only instead of git fetch for existing workspaces",
    ),
    apply: bool = typer.Option(False, "--apply", help="Execute the planned git command"),
):
    try:
        repository_config = get_repository_config(repository)
        result = execute_repository_sync(
            repository_config,
            mode="pull-ff-only" if pull_ff_only else "fetch",
            dry_run=not apply,
        )
    except ValueError as exc:
        print_json(data={"status": "failed", "error": str(exc)})
        raise typer.Exit(code=1) from exc

    print_json(data={"repository": repository_config.to_safe_dict(), "sync": result})

    if result["errors"]:
        raise typer.Exit(code=1)


@app.command("repository-status")
def repository_status_command(
    repository: str | None = typer.Argument(None, help="Repository name"),
):
    try:
        repository_config = get_repository_config(repository)
        status = inspect_repository_status(repository_config)
    except ValueError as exc:
        print_json(data={"status": "failed", "error": str(exc)})
        raise typer.Exit(code=1) from exc

    print_json(data={"repository": repository_config.to_safe_dict(), "workspace_status": status})

    if status["errors"]:
        raise typer.Exit(code=1)


@app.command("repository-doctor")
def repository_doctor_command(
    repository: str | None = typer.Argument(None, help="Repository name"),
    pull_ff_only: bool = typer.Option(
        False,
        "--pull-ff-only",
        help="Plan git pull --ff-only instead of git fetch for existing workspaces",
    ),
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
):
    try:
        repository_config = get_repository_config(repository)
        report = build_repository_doctor_report(
            repository_config,
            mode="pull-ff-only" if pull_ff_only else "fetch",
        )
    except ValueError as exc:
        print_json(data={"status": "failed", "error": str(exc)})
        raise typer.Exit(code=1) from exc

    if as_json:
        print_json(data=report)
    else:
        summary = Table(title="Repository Doctor")
        summary.add_column("Field")
        summary.add_column("Value")
        summary.add_row("Repository", report["repository"])
        summary.add_row("Status", report["status"])
        summary.add_row("Runner Ready", str(report["runner_ready"]))
        summary.add_row("Suggested Action", report["suggested_action"])
        summary.add_row("Workspace", report["workspace_status"]["workspace_path"])
        summary.add_row("Sync Action", report["sync_plan"]["action"])
        summary.add_row("Errors", "; ".join(report["errors"]))
        console.print(summary)

    if report["errors"]:
        raise typer.Exit(code=1)


@app.command("llm-providers")
def llm_providers_command(
    provider: str | None = typer.Option(None, "--provider", help="Provider to resolve"),
):
    defaults = [
        {
            "name": item.name,
            "api_style": item.api_style,
            "base_url": item.base_url,
            "api_key_env": item.api_key_env,
            "model_env": item.model_env,
            "default_model": item.default_model,
            "notes": item.notes,
        }
        for item in list_llm_provider_defaults()
    ]
    selected = build_llm_provider_config(provider).to_safe_dict()

    print_json(data={"providers": defaults, "selected": selected})


@app.command("llm-provider-doctor")
def llm_provider_doctor_command(
    provider: str | None = typer.Option(None, "--provider", help="Provider to resolve"),
    require_key: bool = typer.Option(False, "--require-key", help="Fail if API key is not set"),
):
    try:
        selected = build_llm_provider_config(provider).to_safe_dict()
    except ValueError as exc:
        print_json(data={"status": "failed", "error": str(exc)})
        raise typer.Exit(code=1) from exc

    status = "configured" if selected["api_key_set"] else "missing_api_key"
    payload = {
        "status": status,
        "provider": selected,
    }
    print_json(data=payload)

    if require_key and not selected["api_key_set"]:
        raise typer.Exit(code=1)


@app.command("authorize-llm-egress")
def authorize_llm_egress_command(
    task_code: str,
    provider: str = typer.Option("deepseek", "--provider", help="LLM provider"),
    model: str = typer.Option("deepseek-chat", "--model", help="LLM model"),
    data_classification: str = typer.Option(
        "D1",
        "--data-classification",
        help="Highest data classification covered by this authorization",
    ),
    ttl_hours: int = typer.Option(24, "--ttl-hours", min=1, help="Authorization lifetime"),
    by: str = typer.Option("emperor", "--by", help="Authorizing agent or user"),
    reason: str = typer.Option("", "--reason", help="Governance reason"),
):
    task = get_task_detail(task_code)

    if not task:
        print(f"[red]Task not found:[/red] {task_code}")
        raise typer.Exit(code=1)

    try:
        normalized_classification = normalize_data_classification(data_classification)
        if task["task_level"] not in {"L3", "L4"}:
            raise ValueError("LLM egress authorization is only required for L3/L4 tasks.")
        if not _has_approved_a_confirmation(task):
            raise ValueError(
                "A-level APPROVED confirmation is required before LLM egress authorization."
            )
        if not is_llm_provider_model_allowlisted(provider, model):
            raise ValueError(f"{provider}/{model} is not allowlisted for external LLM execution")

        permission_decision = require_tool_permission(
            agent_name=by,
            tool_name="cli.authorize_llm_egress",
            task_level=task["task_level"],
            required_confirmation=task.get("route_result", {}).get(
                "required_confirmation",
                "none",
            ),
            current_status=task["status"],
        )
        authorization = record_llm_egress_authorization(
            task_id=task["id"],
            provider=provider.strip().lower(),
            model=model.strip(),
            data_classification=normalized_classification,
            authorized_by=by,
            reason=reason,
            ttl_hours=ttl_hours,
        )
    except (PermissionError, RuntimeError, ValueError) as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    record_task_event(
        task_id=task["id"],
        event_type="llm_egress_authorized",
        from_status=task["status"],
        to_status=task["status"],
        summary=(
            f"LLM egress authorized for {authorization['provider']}/"
            f"{authorization['model']} until {authorization['expires_at']}"
        ),
        created_by=by,
    )
    record_tool_call(
        task_id=task["id"],
        agent_name=by,
        tool_name="cli.authorize_llm_egress",
        arguments_summary=(
            f"task_code={task_code}; provider={authorization['provider']}; "
            f"model={authorization['model']}; data_classification={normalized_classification}; "
            f"ttl_hours={ttl_hours}"
        ),
        permission_policy=permission_decision["permission_policy"],
        result_status="success",
        permission_decision=permission_decision,
        output_summary=(
            f"authorization_id={authorization['id']}; expires_at={authorization['expires_at']}"
        ),
        risk_flag=permission_decision["risk_flag"],
    )

    print_json(data={"task_code": task_code, "authorization": authorization})


@app.command("audit-llm-egress-authorizations")
def audit_llm_egress_authorizations_command(
    limit: int = typer.Option(
        100, "--limit", min=1, help="Maximum expired authorizations to audit"
    ),
    apply: bool = typer.Option(False, "--apply", help="Mark expired authorizations as EXPIRED"),
    by: str = typer.Option("xingbu", "--by", help="Auditing agent or user"),
):
    try:
        authorizations = list_expired_llm_egress_authorizations(limit=limit)
        permission_decisions = [
            require_tool_permission(
                agent_name=by,
                tool_name="cli.audit_llm_egress_authorizations",
                task_level=authorization["task_level"],
                required_confirmation=authorization["required_confirmation"],
                current_status=authorization["task_status"],
            )
            for authorization in authorizations
        ]
        if apply:
            mark_llm_egress_authorizations_expired(
                [authorization["id"] for authorization in authorizations]
            )
            authorizations = [
                {**authorization, "status": "EXPIRED"} for authorization in authorizations
            ]
    except (PermissionError, RuntimeError) as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    result = {
        "dry_run": not apply,
        "expired_count": len(authorizations),
        "authorizations": authorizations,
    }
    event_type = (
        "llm_egress_authorization_expired" if apply else "llm_egress_authorization_expiry_detected"
    )
    tool_status = "success" if apply else "dry_run"

    for authorization, permission_decision in zip(
        result["authorizations"],
        permission_decisions,
        strict=True,
    ):
        record_task_event(
            task_id=authorization["task_id"],
            event_type=event_type,
            from_status=authorization["task_status"],
            to_status=authorization["task_status"],
            summary=(
                f"LLM egress authorization {authorization['id']} "
                f"for {authorization['provider']}/{authorization['model']} "
                f"expired at {authorization['expires_at']}"
            ),
            created_by=by,
        )
        record_tool_call(
            task_id=authorization["task_id"],
            agent_name=by,
            tool_name="cli.audit_llm_egress_authorizations",
            arguments_summary=(
                f"authorization_id={authorization['id']}; "
                f"provider={authorization['provider']}; model={authorization['model']}; "
                f"data_classification={authorization['data_classification']}; apply={apply}"
            ),
            permission_policy=permission_decision["permission_policy"],
            result_status=tool_status,
            permission_decision=permission_decision,
            output_summary=(
                f"task_code={authorization['task_code']}; "
                f"authorization_status={authorization['status']}; "
                f"expires_at={authorization['expires_at']}"
            ),
            risk_flag=permission_decision["risk_flag"],
        )

    print_json(data=result)


@app.command("llm-chat")
def llm_chat_command(
    task_code: str,
    prompt: str,
    provider: str | None = typer.Option(None, "--provider", help="LLM provider"),
    by: str = typer.Option("zhongshu", "--by", help="Agent name"),
    system_prompt: str | None = typer.Option(None, "--system", help="Optional system prompt"),
    data_classification: str = typer.Option(
        "D1",
        "--data-classification",
        help="Highest data classification included in the LLM prompt",
    ),
    temperature: float = typer.Option(0.2, "--temperature", min=0.0, max=2.0),
    max_tokens: int = typer.Option(1024, "--max-tokens", min=1),
    execute: bool = typer.Option(False, "--execute", help="Call the external provider"),
    allow_governed_egress: bool = typer.Option(
        False,
        "--allow-governed-egress",
        help="Allow L3/L4 egress only when an A-level approval exists",
    ),
):
    task = get_task_detail(task_code)

    if not task:
        print(f"[red]Task not found:[/red] {task_code}")
        raise typer.Exit(code=1)

    try:
        provider_config = build_llm_provider_config(provider)
        permission_decision = require_tool_permission(
            agent_name=by,
            tool_name="llm.chat_completion",
            task_level=task["task_level"],
            required_confirmation=task.get("route_result", {}).get(
                "required_confirmation",
                "none",
            ),
            current_status=task["status"],
        )
        llm_prompt = build_llm_task_prompt(task, prompt)
        resolved_classification = resolve_task_data_classification(task, data_classification)
        egress_decision = evaluate_llm_egress_policy(
            task_level=task["task_level"],
            data_classification=resolved_classification,
            provider=provider_config.name,
            model=provider_config.model,
            execute=execute,
            governed_egress_approved=(
                allow_governed_egress
                and _has_active_llm_egress_authorization(
                    task,
                    provider=provider_config.name,
                    model=provider_config.model,
                    data_classification=resolved_classification,
                )
            ),
        )
        if egress_decision.allowed:
            result = execute_llm_chat_completion(
                provider_config,
                llm_prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                dry_run=not execute,
            )
            result_payload = result.to_safe_dict()
            result_status = "success" if result.status in {"success", "dry_run"} else "failed"
            output_summary = (
                f"provider={provider_config.name}; model={provider_config.model}; "
                f"status={result.status}; dry_run={result.dry_run}; "
                f"data_classification={resolved_classification}; error={result.error}"
            )
        else:
            result_payload = {
                "provider": provider_config.name,
                "model": provider_config.model,
                "status": "denied",
                "dry_run": not execute,
                "request": None,
                "response": None,
                "error": egress_decision.reason,
                "egress_policy": egress_decision.to_dict(),
            }
            result_status = "denied"
            output_summary = (
                f"provider={provider_config.name}; model={provider_config.model}; "
                f"status=denied; dry_run={not execute}; "
                f"data_classification={resolved_classification}; error={egress_decision.reason}"
            )
    except (PermissionError, RuntimeError, ValueError) as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    record_tool_call(
        task_id=task["id"],
        agent_name=by,
        tool_name="llm.chat_completion",
        arguments_summary=(
            f"task_code={task_code}; provider={provider_config.name}; "
            f"model={provider_config.model}; user_prompt_chars={len(prompt)}; "
            f"llm_prompt_chars={len(llm_prompt)}; data_classification={resolved_classification}; "
            f"execute={execute}; allow_governed_egress={allow_governed_egress}"
        ),
        permission_policy=permission_decision["permission_policy"],
        result_status=result_status,
        permission_decision={
            **permission_decision,
            "egress_policy": egress_decision.to_dict(),
        },
        output_summary=output_summary,
        risk_flag=permission_decision["risk_flag"] or not egress_decision.allowed,
    )

    print_json(data=result_payload)

    if result_status != "success":
        raise typer.Exit(code=1)


@app.command("self-upgrade")
def self_upgrade_command(
    task_code: str,
    request: str = typer.Argument("", help="Self-upgrade request. Defaults to task raw_request."),
    provider: str | None = typer.Option(None, "--provider", help="LLM provider"),
    repository: str | None = typer.Option(None, "--repository", help="Repository config name"),
    data_classification: str = typer.Option(
        "D1",
        "--data-classification",
        help="Highest data classification included in the LLM prompt",
    ),
    execute: bool = typer.Option(False, "--execute", help="Call the external provider"),
    apply: bool = typer.Option(False, "--apply", help="Write the generated patch to disk"),
    validate: bool = typer.Option(
        True,
        "--validate/--skip-validation",
        help="Run validation gates after applying the patch",
    ),
    branch: bool = typer.Option(False, "--branch", help="Create a runner branch before applying"),
    base_ref: str | None = typer.Option(
        None, "--base-ref", help="Git base ref for branch creation"
    ),
    commit: bool = typer.Option(False, "--commit", help="Commit applied self-upgrade changes"),
    push: bool = typer.Option(False, "--push", help="Push the self-upgrade commit to origin HEAD"),
    create_pr: bool = typer.Option(
        False,
        "--create-pr",
        help="Create and bind a GitHub PR after pushing the self-upgrade branch",
    ),
    check_ci: bool = typer.Option(
        False,
        "--check-ci",
        help="Read GitHub PR checks after creating the self-upgrade PR",
    ),
    allow_governed_egress: bool = typer.Option(
        False,
        "--allow-governed-egress",
        help="Allow L3/L4 egress only when an A-level approval exists",
    ),
    temperature: float = typer.Option(0.1, "--temperature", min=0.0, max=2.0),
    max_tokens: int = typer.Option(2048, "--max-tokens", min=1),
    timeout_seconds: int = typer.Option(120, "--timeout", help="Per-command timeout seconds"),
    llm_by: str = typer.Option("zhongshu", "--llm-by", help="LLM planning agent name"),
    patch_by: str = typer.Option("gongbu", "--patch-by", help="Patch agent name"),
    validate_by: str = typer.Option("xingbu", "--validate-by", help="Validation agent name"),
    delivery_by: str = typer.Option("gongbu", "--delivery-by", help="Delivery agent name"),
    pr_by: str = typer.Option("shangshu", "--pr-by", help="GitHub PR agent name"),
    ci_by: str = typer.Option("xingbu", "--ci-by", help="GitHub CI check agent name"),
):
    task = get_task_detail(task_code)

    if not task:
        print(f"[red]Task not found:[/red] {task_code}")
        raise typer.Exit(code=1)

    if task["task_level"] == "L4" and apply:
        print("[red]L4 tasks cannot execute self-upgrade patches.[/red]")
        raise typer.Exit(code=1)
    if branch and not apply:
        print("[red]--branch requires --apply.[/red]")
        raise typer.Exit(code=1)
    if commit and not apply:
        print("[red]--commit requires --apply.[/red]")
        raise typer.Exit(code=1)
    if push and not commit:
        print("[red]--push requires --commit.[/red]")
        raise typer.Exit(code=1)
    if create_pr and not push:
        print("[red]--create-pr requires --push.[/red]")
        raise typer.Exit(code=1)
    if check_ci and not create_pr:
        print("[red]--check-ci requires --create-pr.[/red]")
        raise typer.Exit(code=1)

    readiness_errors = validate_self_upgrade_readiness()
    if readiness_errors:
        print("[red]Self-upgrade readiness check failed:[/red]")
        for error in readiness_errors:
            print(f"- {error}")
        raise typer.Exit(code=1)

    try:
        provider_config = build_llm_provider_config(provider)
        llm_permission = require_tool_permission(
            agent_name=llm_by,
            tool_name="llm.chat_completion",
            task_level=task["task_level"],
            required_confirmation=task.get("route_result", {}).get(
                "required_confirmation",
                "none",
            ),
            current_status=task["status"],
        )
        llm_prompt = build_self_upgrade_prompt(task, request)
        resolved_classification = resolve_task_data_classification(task, data_classification)
        egress_decision = evaluate_llm_egress_policy(
            task_level=task["task_level"],
            data_classification=resolved_classification,
            provider=provider_config.name,
            model=provider_config.model,
            execute=execute,
            governed_egress_approved=(
                allow_governed_egress
                and _has_active_llm_egress_authorization(
                    task,
                    provider=provider_config.name,
                    model=provider_config.model,
                    data_classification=resolved_classification,
                )
            ),
        )
        if egress_decision.allowed:
            llm_result = execute_llm_chat_completion(
                provider_config,
                llm_prompt,
                system_prompt=SELF_UPGRADE_SYSTEM_PROMPT,
                temperature=temperature,
                max_tokens=max_tokens,
                dry_run=not execute,
            )
            llm_payload = llm_result.to_safe_dict()
            llm_result_status = (
                "success" if llm_result.status in {"success", "dry_run"} else "failed"
            )
            llm_output_summary = (
                f"provider={provider_config.name}; model={provider_config.model}; "
                f"status={llm_result.status}; dry_run={llm_result.dry_run}; "
                f"data_classification={resolved_classification}; error={llm_result.error}"
            )
        else:
            llm_payload = {
                "provider": provider_config.name,
                "model": provider_config.model,
                "status": "denied",
                "dry_run": not execute,
                "request": None,
                "response": None,
                "error": egress_decision.reason,
                "egress_policy": egress_decision.to_dict(),
            }
            llm_result_status = "denied"
            llm_output_summary = (
                f"provider={provider_config.name}; model={provider_config.model}; "
                f"status=denied; dry_run={not execute}; "
                f"data_classification={resolved_classification}; error={egress_decision.reason}"
            )
    except (PermissionError, RuntimeError, ValueError) as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    record_tool_call(
        task_id=task["id"],
        agent_name=llm_by,
        tool_name="llm.chat_completion",
        arguments_summary=(
            f"task_code={task_code}; provider={provider_config.name}; "
            f"model={provider_config.model}; user_request_chars={len(request)}; "
            f"llm_prompt_chars={len(llm_prompt)}; data_classification={resolved_classification}; "
            f"execute={execute}; apply={apply}; validate={validate}; branch={branch}; "
            f"commit={commit}; push={push}; create_pr={create_pr}; check_ci={check_ci}; "
            f"allow_governed_egress={allow_governed_egress}"
        ),
        permission_policy=llm_permission["permission_policy"],
        result_status=llm_result_status,
        permission_decision={
            **llm_permission,
            "egress_policy": egress_decision.to_dict(),
        },
        output_summary=llm_output_summary,
        risk_flag=llm_permission["risk_flag"] or not egress_decision.allowed,
    )

    if llm_result_status != "success":
        print_json(
            data={
                "task_code": task_code,
                "status": llm_payload["status"],
                "llm_result": llm_payload,
                "plan": None,
                "governance_results": [],
                "execution_result": None,
                "validation_result": None,
            }
        )
        raise typer.Exit(code=1)

    if not execute:
        print_json(
            data={
                "task_code": task_code,
                "status": "dry_run",
                "llm_result": llm_payload,
                "plan": None,
                "governance_results": [],
                "execution_result": None,
                "validation_result": None,
            }
        )
        return

    try:
        plan = parse_self_upgrade_plan(extract_llm_response_text(llm_payload["response"]))
        repository_config = get_repository_config(repository)
        execution_result = None
        validation_result = None
        delivery_result = None
        branch_result = None
        pr_result = None
        ci_result = None
        governance_results = []

        if plan["operations"]:
            if apply:
                governance_results = _execute_self_upgrade_governance_checks(task)
                if any(not result["deliverable"] for result in governance_results):
                    print_json(
                        data={
                            "task_code": task_code,
                            "status": "governance_blocked",
                            "repository": repository_config.to_safe_dict(),
                            "llm_result": llm_payload,
                            "branch_result": branch_result,
                            "plan": plan,
                            "governance_results": governance_results,
                            "execution_result": execution_result,
                            "validation_result": validation_result,
                            "delivery_result": delivery_result,
                            "pr_result": pr_result,
                            "ci_result": ci_result,
                        }
                    )
                    raise typer.Exit(code=1)

            if branch and apply:
                branch_permission = require_tool_permission(
                    agent_name=patch_by,
                    tool_name="cli.runner_branch",
                    task_level=task["task_level"],
                    required_confirmation=task.get("route_result", {}).get(
                        "required_confirmation",
                        "none",
                    ),
                    current_status=task["status"],
                )
                _require_runner_repository_preflight(
                    task,
                    repository_config,
                    plan["validation_gates"] if validate else None,
                    require_validation_gates=validate,
                    by=patch_by,
                )
                resolved_base_ref = base_ref or repository_config.default_branch
                branch_plan = build_runner_branch_plan(
                    task_code=task_code,
                    title=task.get("title", ""),
                    task_level=task["task_level"],
                    base_ref=resolved_base_ref,
                    branch_prefix=repository_config.branch_prefix,
                )
                branch_result = create_runner_branch(
                    branch_plan,
                    repo_root=repository_config.workspace_path,
                    dry_run=False,
                )
                record_task_event(
                    task_id=task["id"],
                    event_type="self_upgrade_branch_created",
                    from_status=task["status"],
                    to_status=task["status"],
                    summary=f"Self-upgrade runner branch created: {branch_result['branch_name']}",
                    created_by=patch_by,
                )
                record_tool_call(
                    task_id=task["id"],
                    agent_name=patch_by,
                    tool_name="cli.runner_branch",
                    arguments_summary=(
                        f"task_code={task_code}; repository={repository_config.name}; "
                        f"base_ref={resolved_base_ref}; apply=True"
                    ),
                    permission_policy=branch_permission["permission_policy"],
                    result_status="success",
                    permission_decision=branch_permission,
                    output_summary=(
                        f"branch_name={branch_result['branch_name']}; "
                        f"created={branch_result['created']}; errors={branch_result['errors']}"
                    ),
                    risk_flag=branch_permission["risk_flag"],
                )

            patch_permission = require_tool_permission(
                agent_name=patch_by,
                tool_name="cli.runner_patch",
                task_level=task["task_level"],
                required_confirmation=task.get("route_result", {}).get(
                    "required_confirmation",
                    "none",
                ),
                current_status=task["status"],
            )
            if apply and not branch:
                _require_runner_repository_preflight(
                    task,
                    repository_config,
                    plan["validation_gates"] if validate else None,
                    require_validation_gates=validate,
                    by=patch_by,
                )
            execution_result = apply_text_patch_operations(
                plan["operations"],
                repo_root=repository_config.workspace_path,
                dry_run=not apply,
            )
            record_task_event(
                task_id=task["id"],
                event_type="self_upgrade_patch_applied" if apply else "self_upgrade_patch_planned",
                from_status=task["status"],
                to_status=task["status"],
                summary=(
                    f"Self-upgrade {'applied' if apply else 'planned'} "
                    f"{len(plan['operations'])} controlled patch operation(s)."
                ),
                created_by=patch_by,
            )
            record_tool_call(
                task_id=task["id"],
                agent_name=patch_by,
                tool_name="cli.runner_patch",
                arguments_summary=(
                    f"task_code={task_code}; repository={repository_config.name}; "
                    f"paths={execution_result['changed_files']}; apply={apply}"
                ),
                permission_policy=patch_permission["permission_policy"],
                result_status="success",
                permission_decision=patch_permission,
                output_summary=(
                    f"changed_files={execution_result['changed_files']}; "
                    f"applied={execution_result['applied']}"
                ),
                risk_flag=patch_permission["risk_flag"],
            )

        if plan["operations"] and apply and validate:
            validation_permission = require_tool_permission(
                agent_name=validate_by,
                tool_name="cli.runner_validate",
                task_level=task["task_level"],
                required_confirmation=task.get("route_result", {}).get(
                    "required_confirmation",
                    "none",
                ),
                current_status=task["status"],
            )
            validation_result = execute_runner_validation_commands(
                plan["validation_gates"],
                repo_root=repository_config.workspace_path,
                timeout_seconds=timeout_seconds,
            )
            record_tool_call(
                task_id=task["id"],
                agent_name=validate_by,
                tool_name="cli.runner_validate",
                arguments_summary=(
                    f"task_code={task_code}; repository={repository_config.name}; "
                    f"gates={plan['validation_gates']}"
                ),
                permission_policy=validation_permission["permission_policy"],
                result_status="success" if validation_result["deliverable"] else "failed",
                permission_decision=validation_permission,
                output_summary=f"deliverable={validation_result['deliverable']}",
                risk_flag=validation_permission["risk_flag"],
            )

        deliverable = validation_result is None or validation_result["deliverable"]
        if plan["operations"] and commit and deliverable and execution_result:
            delivery_permission = require_tool_permission(
                agent_name=delivery_by,
                tool_name="cli.self_upgrade_delivery",
                task_level=task["task_level"],
                required_confirmation=task.get("route_result", {}).get(
                    "required_confirmation",
                    "none",
                ),
                current_status=task["status"],
            )
            delivery_result = execute_self_upgrade_delivery(
                repository_config,
                changed_files=execution_result["changed_files"],
                commit_message=plan["commit_message"],
                dry_run=False,
                push=push,
            )
            delivery_success = not delivery_result["errors"]
            record_task_event(
                task_id=task["id"],
                event_type=(
                    "self_upgrade_delivered" if delivery_success else "self_upgrade_delivery_failed"
                ),
                from_status=task["status"],
                to_status=task["status"],
                summary=(
                    f"Self-upgrade delivery committed={delivery_result['committed']}; "
                    f"pushed={delivery_result['pushed']}; sha={delivery_result['commit_sha']}"
                ),
                created_by=delivery_by,
            )
            record_tool_call(
                task_id=task["id"],
                agent_name=delivery_by,
                tool_name="cli.self_upgrade_delivery",
                arguments_summary=(
                    f"task_code={task_code}; repository={repository_config.name}; "
                    f"changed_files={delivery_result['changed_files']}; push={push}"
                ),
                permission_policy=delivery_permission["permission_policy"],
                result_status="success" if delivery_success else "failed",
                permission_decision=delivery_permission,
                output_summary=(
                    f"committed={delivery_result['committed']}; "
                    f"pushed={delivery_result['pushed']}; errors={delivery_result['errors']}"
                ),
                risk_flag=delivery_permission["risk_flag"] or not delivery_success,
            )

        delivered = delivery_result is None or not delivery_result["errors"]
        if plan["operations"] and create_pr and deliverable and delivered and execution_result:
            pr_permission = require_tool_permission(
                agent_name=pr_by,
                tool_name="cli.create_github_pr",
                task_level=task["task_level"],
                required_confirmation=task.get("route_result", {}).get(
                    "required_confirmation",
                    "none",
                ),
                current_status=task["status"],
            )
            pr_body = build_self_upgrade_pr_body(
                task_code=task_code,
                summary=plan["summary"],
                changed_files=execution_result["changed_files"],
                validation_gates=plan["validation_gates"],
            )
            pr_result = execute_github_pr_create(
                repository_config,
                title=plan["commit_message"],
                body=pr_body,
                base_ref=repository_config.default_branch,
                dry_run=False,
            )
            pr_success = not pr_result["errors"] and bool(pr_result["url"])
            if pr_success:
                record_github_link(
                    task_id=task["id"],
                    link_type="pull_request",
                    external_id=pr_result["external_id"] or pr_result["url"],
                    url=pr_result["url"],
                    title=pr_result["title"],
                    status="open",
                    metadata={
                        "task_code": task_code,
                        "source": "self_upgrade",
                        "head_ref": pr_result["head_ref"],
                        "base_ref": pr_result["base_ref"],
                    },
                    created_by=pr_by,
                )
            record_task_event(
                task_id=task["id"],
                event_type="self_upgrade_pr_created" if pr_success else "self_upgrade_pr_failed",
                from_status=task["status"],
                to_status=task["status"],
                summary=f"Self-upgrade PR url={pr_result['url']}; errors={pr_result['errors']}",
                created_by=pr_by,
            )
            record_tool_call(
                task_id=task["id"],
                agent_name=pr_by,
                tool_name="cli.create_github_pr",
                arguments_summary=(
                    f"task_code={task_code}; repository={repository_config.name}; "
                    f"base_ref={pr_result['base_ref']}; head_ref={pr_result['head_ref']}"
                ),
                permission_policy=pr_permission["permission_policy"],
                result_status="success" if pr_success else "failed",
                permission_decision=pr_permission,
                output_summary=f"url={pr_result['url']}; errors={pr_result['errors']}",
                risk_flag=pr_permission["risk_flag"] or not pr_success,
            )

        pr_delivered = pr_result is None or (not pr_result["errors"] and bool(pr_result["url"]))
        if plan["operations"] and check_ci and pr_result and pr_delivered:
            ci_permission = require_tool_permission(
                agent_name=ci_by,
                tool_name="cli.github_ci_check",
                task_level=task["task_level"],
                required_confirmation=task.get("route_result", {}).get(
                    "required_confirmation",
                    "none",
                ),
                current_status=task["status"],
            )
            ci_result = execute_github_pr_checks(
                repository_config,
                pr_ref=pr_result["url"] or pr_result["external_id"] or "",
                dry_run=False,
            )
            for check in ci_result["checks"]:
                if not check["link"]:
                    continue
                record_github_link(
                    task_id=task["id"],
                    link_type="ci_run",
                    external_id=f"{pr_result['external_id'] or pr_result['url']}:{check['name']}",
                    url=check["link"],
                    title=check["name"],
                    status=check["state"].lower(),
                    metadata={
                        "source": "self_upgrade_ci_check",
                        "pr_url": pr_result["url"],
                        "workflow": check["workflow"],
                        "bucket": check["bucket"],
                    },
                    created_by=ci_by,
                )
            record_task_event(
                task_id=task["id"],
                event_type=f"self_upgrade_ci_{ci_result['status']}",
                from_status=task["status"],
                to_status=task["status"],
                summary=(
                    f"Self-upgrade CI {ci_result['status']}: {len(ci_result['checks'])} check(s)."
                ),
                created_by=ci_by,
            )
            record_tool_call(
                task_id=task["id"],
                agent_name=ci_by,
                tool_name="cli.github_ci_check",
                arguments_summary=(
                    f"task_code={task_code}; repository={repository_config.name}; "
                    f"pr_ref={ci_result['pr_ref']}"
                ),
                permission_policy=ci_permission["permission_policy"],
                result_status="success" if ci_result["deliverable"] else ci_result["status"],
                permission_decision=ci_permission,
                output_summary=(
                    f"status={ci_result['status']}; checks={len(ci_result['checks'])}; "
                    f"errors={ci_result['errors']}"
                ),
                risk_flag=ci_permission["risk_flag"] or not ci_result["deliverable"],
            )

        if not plan["operations"]:
            record_task_event(
                task_id=task["id"],
                event_type="self_upgrade_no_patch",
                from_status=task["status"],
                to_status=task["status"],
                summary=plan["summary"],
                created_by=patch_by,
            )
    except (PermissionError, ValueError, FileNotFoundError) as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    deliverable = validation_result is None or validation_result["deliverable"]
    delivered = delivery_result is None or not delivery_result["errors"]
    pr_delivered = pr_result is None or (not pr_result["errors"] and bool(pr_result["url"]))
    ci_delivered = ci_result is None or ci_result["deliverable"]
    status = "no_patch"
    if plan["operations"]:
        status = "planned"
        if apply:
            status = "applied" if deliverable else "validation_failed"
        if commit:
            status = "delivered" if deliverable and delivered else "delivery_failed"
        if create_pr:
            status = "pr_created" if deliverable and delivered and pr_delivered else "pr_failed"
        if check_ci:
            status = (
                "ci_passed"
                if deliverable and delivered and pr_delivered and ci_delivered
                else f"ci_{ci_result['status']}"
                if ci_result
                else "ci_failed"
            )

    print_json(
        data={
            "task_code": task_code,
            "status": status,
            "repository": repository_config.to_safe_dict(),
            "llm_result": llm_payload,
            "branch_result": branch_result,
            "plan": plan,
            "governance_results": governance_results,
            "execution_result": execution_result,
            "validation_result": validation_result,
            "delivery_result": delivery_result,
            "pr_result": pr_result,
            "ci_result": ci_result,
        }
    )

    if not deliverable or not delivered or not pr_delivered or not ci_delivered:
        raise typer.Exit(code=1)


def _resolve_task_pull_request_ref(task: dict[str, object]) -> str:
    github_links = task.get("github_links") or []
    for link in reversed(github_links):
        if not isinstance(link, dict):
            continue
        if link.get("link_type") != "pull_request":
            continue
        url = link.get("url")
        external_id = link.get("external_id")
        if isinstance(url, str) and url:
            return url
        if isinstance(external_id, str) and external_id:
            return external_id

    raise ValueError("No pull_request github link found for this task. Pass --pr-ref explicitly.")


def _record_self_upgrade_ci_result(
    *,
    task: dict[str, object],
    repository_name: str,
    ci_result: dict[str, object],
    permission_decision: dict[str, object],
    by: str,
    source: str,
) -> None:
    for check in ci_result["checks"]:
        if not check["link"]:
            continue
        record_github_link(
            task_id=task["id"],
            link_type="ci_run",
            external_id=f"{ci_result['pr_ref']}:{check['name']}",
            url=check["link"],
            title=check["name"],
            status=check["state"].lower(),
            metadata={
                "source": source,
                "pr_ref": ci_result["pr_ref"],
                "workflow": check["workflow"],
                "bucket": check["bucket"],
            },
            created_by=by,
        )

    record_task_event(
        task_id=task["id"],
        event_type=f"self_upgrade_ci_{ci_result['status']}",
        from_status=task["status"],
        to_status=task["status"],
        summary=f"Self-upgrade CI {ci_result['status']}: {len(ci_result['checks'])} check(s).",
        created_by=by,
    )
    record_tool_call(
        task_id=task["id"],
        agent_name=by,
        tool_name="cli.github_ci_check",
        arguments_summary=(
            f"task_code={task['task_code']}; repository={repository_name}; "
            f"pr_ref={ci_result['pr_ref']}"
        ),
        permission_policy=permission_decision["permission_policy"],
        result_status="success" if ci_result["deliverable"] else ci_result["status"],
        permission_decision=permission_decision,
        output_summary=(
            f"status={ci_result['status']}; checks={len(ci_result['checks'])}; "
            f"errors={ci_result['errors']}"
        ),
        risk_flag=permission_decision["risk_flag"] or not ci_result["deliverable"],
    )


@app.command("self-upgrade-status")
def self_upgrade_status_command(
    task_code: str,
    pr_ref: str | None = typer.Option(
        None,
        "--pr-ref",
        help="GitHub PR number or URL. Defaults to the latest bound pull_request link.",
    ),
    repository: str | None = typer.Option(None, "--repository", help="Repository config name"),
    by: str = typer.Option("xingbu", "--by", help="GitHub CI check agent name"),
):
    task = get_task_detail(task_code)

    if not task:
        print(f"[red]Task not found:[/red] {task_code}")
        raise typer.Exit(code=1)

    try:
        repository_config = get_repository_config(repository)
        resolved_pr_ref = pr_ref or _resolve_task_pull_request_ref(task)
        permission_decision = require_tool_permission(
            agent_name=by,
            tool_name="cli.github_ci_check",
            task_level=task["task_level"],
            required_confirmation=task.get("route_result", {}).get(
                "required_confirmation",
                "none",
            ),
            current_status=task["status"],
        )
        ci_result = execute_github_pr_checks(
            repository_config,
            pr_ref=resolved_pr_ref,
            dry_run=False,
        )
    except (PermissionError, ValueError) as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    _record_self_upgrade_ci_result(
        task=task,
        repository_name=repository_config.name,
        ci_result=ci_result,
        permission_decision=permission_decision,
        by=by,
        source="self_upgrade_status",
    )

    print_json(
        data={
            "task_code": task_code,
            "status": f"ci_{ci_result['status']}",
            "repository": repository_config.to_safe_dict(),
            "ci_result": ci_result,
        }
    )

    if not ci_result["deliverable"]:
        raise typer.Exit(code=1)


@app.command("self-upgrade-watch")
def self_upgrade_watch_command(
    task_code: str,
    pr_ref: str | None = typer.Option(
        None,
        "--pr-ref",
        help="GitHub PR number or URL. Defaults to the latest bound pull_request link.",
    ),
    repository: str | None = typer.Option(None, "--repository", help="Repository config name"),
    interval_seconds: int = typer.Option(30, "--interval", min=1, help="Seconds between checks"),
    attempts: int = typer.Option(10, "--attempts", min=1, help="Maximum CI polling attempts"),
    by: str = typer.Option("xingbu", "--by", help="GitHub CI check agent name"),
):
    task = get_task_detail(task_code)

    if not task:
        print(f"[red]Task not found:[/red] {task_code}")
        raise typer.Exit(code=1)

    try:
        repository_config = get_repository_config(repository)
        resolved_pr_ref = pr_ref or _resolve_task_pull_request_ref(task)
        permission_decision = require_tool_permission(
            agent_name=by,
            tool_name="cli.github_ci_check",
            task_level=task["task_level"],
            required_confirmation=task.get("route_result", {}).get(
                "required_confirmation",
                "none",
            ),
            current_status=task["status"],
        )
    except (PermissionError, ValueError) as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    ci_result = None
    for attempt in range(1, attempts + 1):
        ci_result = execute_github_pr_checks(
            repository_config,
            pr_ref=resolved_pr_ref,
            dry_run=False,
        )
        if ci_result["status"] != "pending":
            break
        if attempt < attempts:
            time.sleep(interval_seconds)

    assert ci_result is not None
    _record_self_upgrade_ci_result(
        task=task,
        repository_name=repository_config.name,
        ci_result=ci_result,
        permission_decision=permission_decision,
        by=by,
        source="self_upgrade_watch",
    )

    print_json(
        data={
            "task_code": task_code,
            "status": f"ci_{ci_result['status']}",
            "attempts": attempt,
            "repository": repository_config.to_safe_dict(),
            "ci_result": ci_result,
        }
    )

    if not ci_result["deliverable"]:
        raise typer.Exit(code=1)


def _has_approved_a_confirmation(task: dict[str, object]) -> bool:
    for confirmation in task.get("confirmations", []) or []:
        if (
            isinstance(confirmation, dict)
            and confirmation.get("confirmation_level") == "A"
            and confirmation.get("status") == "APPROVED"
        ):
            return True

    return False


def _has_active_llm_egress_authorization(
    task: dict[str, object],
    *,
    provider: str,
    model: str,
    data_classification: str,
) -> bool:
    normalized_provider = provider.strip().lower()
    normalized_model = model.strip()

    for authorization in task.get("llm_egress_authorizations", []) or []:
        if not isinstance(authorization, dict):
            continue
        if authorization.get("active") is not True:
            continue
        if authorization.get("provider") != normalized_provider:
            continue
        if authorization.get("model") != normalized_model:
            continue
        if not is_data_classification_covered(
            authorized_classification=str(authorization.get("data_classification", "")),
            requested_classification=data_classification,
        ):
            continue
        return True

    return False


@app.command("runner-branch")
def runner_branch_command(
    task_code: str,
    repository: str | None = typer.Option(None, "--repository", help="Repository config name"),
    base_ref: str | None = typer.Option(
        None, "--base-ref", help="Git base ref for branch creation"
    ),
    apply: bool = typer.Option(False, "--apply", help="Create and switch to the runner branch"),
    by: str = typer.Option("gongbu", "--by", help="Runner agent name"),
):
    task = get_task_detail(task_code)

    if not task:
        print(f"[red]Task not found:[/red] {task_code}")
        raise typer.Exit(code=1)

    try:
        permission_decision = require_tool_permission(
            agent_name=by,
            tool_name="cli.runner_branch",
            task_level=task["task_level"],
            required_confirmation=task.get("route_result", {}).get(
                "required_confirmation",
                "none",
            ),
            current_status=task["status"],
        )
        repository_config = get_repository_config(repository)
        if apply:
            _require_runner_repository_preflight(
                task,
                repository_config,
                require_validation_gates=False,
                by=by,
            )
        resolved_base_ref = base_ref or repository_config.default_branch
        branch_plan = build_runner_branch_plan(
            task_code=task_code,
            title=task.get("title", ""),
            task_level=task["task_level"],
            base_ref=resolved_base_ref,
            branch_prefix=repository_config.branch_prefix,
        )
        branch_result = create_runner_branch(
            branch_plan,
            repo_root=repository_config.workspace_path,
            dry_run=not apply,
        )
    except (PermissionError, RuntimeError, ValueError) as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if branch_result["created"]:
        event_type = "runner_branch_created"
    elif branch_result["branch_required"]:
        event_type = "runner_branch_dry_run"
    else:
        event_type = "runner_branch_skipped"

    record_task_event(
        task_id=task["id"],
        event_type=event_type,
        from_status=task["status"],
        to_status=task["status"],
        summary=f"Runner branch {'created' if branch_result['created'] else 'checked'}",
        created_by=by,
    )
    record_tool_call(
        task_id=task["id"],
        agent_name=by,
        tool_name="cli.runner_branch",
        arguments_summary=(
            f"task_code={task_code}; repository={repository_config.name}; "
            f"base_ref={resolved_base_ref}; apply={apply}"
        ),
        permission_policy=permission_decision["permission_policy"],
        result_status="success",
        permission_decision=permission_decision,
        output_summary=(
            f"branch_name={branch_result['branch_name']}; "
            f"created={branch_result['created']}; errors={branch_result['errors']}"
        ),
        risk_flag=permission_decision["risk_flag"],
    )

    print_json(
        data={
            "task_code": task_code,
            "event_type": event_type,
            "repository": repository_config.to_safe_dict(),
            "branch_plan": branch_plan,
            "branch_result": branch_result,
        }
    )


@app.command("runner-preflight")
def runner_preflight_command(
    task_code: str,
    gate: Annotated[
        list[str] | None,
        typer.Option("--gate", help="Validation gate expected for runner execution"),
    ] = None,
    repository: str | None = typer.Option(None, "--repository", help="Repository config name"),
    as_json: bool = typer.Option(False, "--json", help="Output JSON"),
    by: str = typer.Option("gongbu", "--by", help="Runner agent name"),
):
    task = get_task_detail(task_code)

    if not task:
        print(f"[red]Task not found:[/red] {task_code}")
        raise typer.Exit(code=1)

    try:
        repository_config = get_repository_config(repository)
        try:
            validation_gates = _resolve_task_validation_gates(task, gate)
        except ValueError:
            validation_gates = []
        preflight = _record_runner_repository_preflight(
            task,
            repository_config,
            validation_gates,
            by=by,
        )
    except (PermissionError, ValueError) as exc:
        print_json(data={"status": "failed", "error": str(exc)})
        raise typer.Exit(code=1) from exc

    if as_json:
        print_json(data=preflight)
    else:
        summary = Table(title="Runner Preflight")
        summary.add_column("Field")
        summary.add_column("Value")
        summary.add_row("Task", preflight["task_code"])
        summary.add_row("Level", preflight["task_level"])
        summary.add_row("Repository", preflight["repository"])
        summary.add_row("Status", preflight["status"])
        summary.add_row("Runner Allowed", str(preflight["runner_allowed"]))
        summary.add_row("Repository Ready", str(preflight["repository_ready"]))
        summary.add_row("Validation Gates", ", ".join(preflight["validation_gates"]))
        summary.add_row("Errors", "; ".join(preflight["errors"]))
        summary.add_row(
            "Suggested Action",
            preflight["repository_doctor"]["suggested_action"],
        )
        console.print(summary)

    if preflight["errors"]:
        raise typer.Exit(code=1)


@app.command("runner-workspace")
def runner_workspace_command(
    task_code: str,
    repository: str | None = typer.Option(None, "--repository", help="Repository config name"),
    base_ref: str | None = typer.Option(
        None, "--base-ref", help="Git base ref for worktree creation"
    ),
    apply: bool = typer.Option(False, "--apply", help="Create the isolated runner worktree"),
    by: str = typer.Option("gongbu", "--by", help="Runner agent name"),
):
    task = get_task_detail(task_code)

    if not task:
        print(f"[red]Task not found:[/red] {task_code}")
        raise typer.Exit(code=1)

    try:
        permission_decision = require_tool_permission(
            agent_name=by,
            tool_name="cli.runner_workspace",
            task_level=task["task_level"],
            required_confirmation=task.get("route_result", {}).get(
                "required_confirmation",
                "none",
            ),
            current_status=task["status"],
        )
        repository_config = get_repository_config(repository)
        if apply:
            _require_runner_repository_preflight(
                task,
                repository_config,
                require_validation_gates=False,
                by=by,
            )
        resolved_base_ref = base_ref or repository_config.default_branch
        workspace_plan = build_runner_workspace_plan(
            task_code=task_code,
            title=task.get("title", ""),
            task_level=task["task_level"],
            base_ref=resolved_base_ref,
            branch_prefix=repository_config.branch_prefix,
            sandbox_root=repository_config.sandbox_root,
        )
        workspace_result = create_runner_workspace(
            workspace_plan,
            repo_root=repository_config.workspace_path,
            allowed_workspace_root=repository_config.sandbox_root,
            dry_run=not apply,
        )
    except (PermissionError, RuntimeError, ValueError) as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if workspace_result["created"]:
        event_type = "runner_workspace_created"
    elif workspace_result["workspace_required"]:
        event_type = "runner_workspace_dry_run"
    else:
        event_type = "runner_workspace_skipped"

    record_task_event(
        task_id=task["id"],
        event_type=event_type,
        from_status=task["status"],
        to_status=task["status"],
        summary=f"Runner workspace {'created' if workspace_result['created'] else 'checked'}",
        created_by=by,
    )
    record_tool_call(
        task_id=task["id"],
        agent_name=by,
        tool_name="cli.runner_workspace",
        arguments_summary=(
            f"task_code={task_code}; repository={repository_config.name}; "
            f"base_ref={resolved_base_ref}; apply={apply}"
        ),
        permission_policy=permission_decision["permission_policy"],
        result_status="success",
        permission_decision=permission_decision,
        output_summary=(
            f"workspace_path={workspace_result['workspace_path']}; "
            f"created={workspace_result['created']}; errors={workspace_result['errors']}"
        ),
        risk_flag=permission_decision["risk_flag"],
    )

    print_json(
        data={
            "task_code": task_code,
            "event_type": event_type,
            "repository": repository_config.to_safe_dict(),
            "workspace_plan": workspace_plan,
            "workspace_result": workspace_result,
        }
    )


@app.command("runner-sandbox")
def runner_sandbox_command(
    task_code: str,
    gate: Annotated[
        list[str] | None,
        typer.Option("--gate", help="Validation gate to run in Docker sandbox"),
    ] = None,
    repository: str | None = typer.Option(None, "--repository", help="Repository config name"),
    workspace_path: str = typer.Option(".", "--workspace-path", help="Workspace path to mount"),
    image: str = typer.Option(DEFAULT_SANDBOX_IMAGE, "--image", help="Docker image"),
    apply: bool = typer.Option(False, "--apply", help="Run the sandbox commands"),
    timeout_seconds: int = typer.Option(120, "--timeout", help="Per-command timeout seconds"),
    by: str = typer.Option("gongbu", "--by", help="Runner agent name"),
):
    task = get_task_detail(task_code)

    if not task:
        print(f"[red]Task not found:[/red] {task_code}")
        raise typer.Exit(code=1)

    try:
        permission_decision = require_tool_permission(
            agent_name=by,
            tool_name="cli.runner_sandbox",
            task_level=task["task_level"],
            required_confirmation=task.get("route_result", {}).get(
                "required_confirmation",
                "none",
            ),
            current_status=task["status"],
        )
        repository_config = get_repository_config(repository)
        sandbox_gates = _resolve_task_validation_gates(task, gate)
        if apply:
            _require_runner_repository_preflight(
                task,
                repository_config,
                sandbox_gates,
                by=by,
            )
        sandbox_result = execute_runner_sandbox_commands(
            sandbox_gates,
            workspace_path=workspace_path,
            repo_root=repository_config.workspace_path,
            image=image,
            dry_run=not apply,
            timeout_seconds=timeout_seconds,
        )
    except (PermissionError, RuntimeError, ValueError) as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    event_type = (
        "runner_sandbox_dry_run"
        if sandbox_result["dry_run"]
        else ("runner_sandbox_passed" if sandbox_result["deliverable"] else "runner_sandbox_failed")
    )
    result_status = (
        "success" if sandbox_result["dry_run"] or sandbox_result["deliverable"] else "failed"
    )

    record_task_event(
        task_id=task["id"],
        event_type=event_type,
        from_status=task["status"],
        to_status=task["status"],
        summary=f"Runner sandbox {'planned' if sandbox_result['dry_run'] else 'executed'}",
        created_by=by,
    )
    record_tool_call(
        task_id=task["id"],
        agent_name=by,
        tool_name="cli.runner_sandbox",
        arguments_summary=(
            f"task_code={task_code}; repository={repository_config.name}; gates={sandbox_gates}; "
            f"workspace_path={workspace_path}; image={image}; apply={apply}"
        ),
        permission_policy=permission_decision["permission_policy"],
        result_status=result_status,
        permission_decision=permission_decision,
        output_summary=(
            f"executed={sandbox_result['executed']}; "
            f"deliverable={sandbox_result['deliverable']}; errors={sandbox_result['errors']}"
        ),
        risk_flag=permission_decision["risk_flag"],
    )

    print_json(
        data={
            "task_code": task_code,
            "event_type": event_type,
            "repository": repository_config.to_safe_dict(),
            "sandbox_result": sandbox_result,
        }
    )

    if not sandbox_result["dry_run"] and not sandbox_result["deliverable"]:
        raise typer.Exit(code=1)


@app.command("runner-patch")
def runner_patch_command(
    task_code: str,
    path: str,
    old_text: str = typer.Option(..., "--old-text", help="Text that must match once"),
    new_text: str = typer.Option(..., "--new-text", help="Replacement text"),
    repository: str | None = typer.Option(None, "--repository", help="Repository config name"),
    apply: bool = typer.Option(False, "--apply", help="Write the patch to disk"),
    by: str = typer.Option("gongbu", "--by", help="Runner agent name"),
):
    task = get_task_detail(task_code)

    if not task:
        print(f"[red]Task not found:[/red] {task_code}")
        raise typer.Exit(code=1)

    if task["task_level"] == "L4":
        print("[red]L4 tasks cannot execute runner patches.[/red]")
        raise typer.Exit(code=1)

    try:
        permission_decision = require_tool_permission(
            agent_name=by,
            tool_name="cli.runner_patch",
            task_level=task["task_level"],
            required_confirmation=task.get("route_result", {}).get(
                "required_confirmation",
                "none",
            ),
            current_status=task["status"],
        )
        repository_config = get_repository_config(repository)
        if apply:
            _require_runner_repository_preflight(
                task,
                repository_config,
                require_validation_gates=False,
                by=by,
            )
        execution_result = apply_text_patch_operations(
            [
                {
                    "path": path,
                    "old_text": old_text,
                    "new_text": new_text,
                }
            ],
            repo_root=repository_config.workspace_path,
            dry_run=not apply,
        )
    except (PermissionError, ValueError, FileNotFoundError) as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    event_type = "runner_patch_applied" if apply else "runner_patch_dry_run"
    record_task_event(
        task_id=task["id"],
        event_type=event_type,
        from_status=task["status"],
        to_status=task["status"],
        summary=f"Runner patch {'applied' if apply else 'validated'} for {path}",
        created_by=by,
    )
    record_tool_call(
        task_id=task["id"],
        agent_name=by,
        tool_name="cli.runner_patch",
        arguments_summary=(
            f"task_code={task_code}; repository={repository_config.name}; "
            f"path={path}; apply={apply}"
        ),
        permission_policy=permission_decision["permission_policy"],
        result_status="success",
        permission_decision=permission_decision,
        output_summary=(
            f"changed_files={execution_result['changed_files']}; "
            f"applied={execution_result['applied']}"
        ),
        risk_flag=permission_decision["risk_flag"],
    )

    print_json(
        data={
            "task_code": task_code,
            "event_type": event_type,
            "repository": repository_config.to_safe_dict(),
            "execution_result": execution_result,
        }
    )


@app.command("runner-validate")
def runner_validate_command(
    task_code: str,
    gate: Annotated[
        list[str] | None,
        typer.Option("--gate", help="Validation gate to execute"),
    ] = None,
    repository: str | None = typer.Option(None, "--repository", help="Repository config name"),
    timeout_seconds: int = typer.Option(120, "--timeout", help="Per-command timeout seconds"),
    by: str = typer.Option("xingbu", "--by", help="Validation agent name"),
):
    task = get_task_detail(task_code)

    if not task:
        print(f"[red]Task not found:[/red] {task_code}")
        raise typer.Exit(code=1)

    try:
        permission_decision = require_tool_permission(
            agent_name=by,
            tool_name="cli.runner_validate",
            task_level=task["task_level"],
            required_confirmation=task.get("route_result", {}).get(
                "required_confirmation",
                "none",
            ),
            current_status=task["status"],
        )
        repository_config = get_repository_config(repository)
        validation_gates = _resolve_task_validation_gates(task, gate)
        _require_runner_repository_preflight(
            task,
            repository_config,
            validation_gates,
            by=by,
        )
        validation_result = execute_runner_validation_commands(
            validation_gates,
            repo_root=repository_config.workspace_path,
            timeout_seconds=timeout_seconds,
        )
    except (PermissionError, ValueError) as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    result_status = "success" if validation_result["deliverable"] else "failed"
    event_type = (
        "runner_validation_passed"
        if validation_result["deliverable"]
        else "runner_validation_failed"
    )
    record_task_event(
        task_id=task["id"],
        event_type=event_type,
        from_status=task["status"],
        to_status=task["status"],
        summary=f"Runner validation {result_status}: {', '.join(validation_gates)}",
        created_by=by,
    )
    record_tool_call(
        task_id=task["id"],
        agent_name=by,
        tool_name="cli.runner_validate",
        arguments_summary=(
            f"task_code={task_code}; repository={repository_config.name}; gates={validation_gates}"
        ),
        permission_policy=permission_decision["permission_policy"],
        result_status=result_status,
        permission_decision=permission_decision,
        output_summary=f"deliverable={validation_result['deliverable']}",
        risk_flag=permission_decision["risk_flag"],
    )

    print_json(
        data={
            "task_code": task_code,
            "repository": repository_config.to_safe_dict(),
            "validation_result": validation_result,
        }
    )

    if not validation_result["deliverable"]:
        raise typer.Exit(code=1)


@app.command("runner-attempt")
def runner_attempt_command(
    task_code: str,
    path: str,
    gate: Annotated[
        list[str] | None,
        typer.Option("--gate", help="Validation gate to execute after patch"),
    ] = None,
    old_text: str = typer.Option(..., "--old-text", help="Text that must match once"),
    new_text: str = typer.Option(..., "--new-text", help="Replacement text"),
    repository: str | None = typer.Option(None, "--repository", help="Repository config name"),
    apply: bool = typer.Option(False, "--apply", help="Write the patch before validation"),
    timeout_seconds: int = typer.Option(120, "--timeout", help="Per-command timeout seconds"),
    patch_by: str = typer.Option("gongbu", "--patch-by", help="Patch agent name"),
    validate_by: str = typer.Option("xingbu", "--validate-by", help="Validation agent name"),
):
    task = get_task_detail(task_code)

    if not task:
        print(f"[red]Task not found:[/red] {task_code}")
        raise typer.Exit(code=1)

    if task["task_level"] == "L4":
        print("[red]L4 tasks cannot execute runner attempts.[/red]")
        raise typer.Exit(code=1)

    try:
        patch_permission = require_tool_permission(
            agent_name=patch_by,
            tool_name="cli.runner_patch",
            task_level=task["task_level"],
            required_confirmation=task.get("route_result", {}).get(
                "required_confirmation",
                "none",
            ),
            current_status=task["status"],
        )
        validation_permission = require_tool_permission(
            agent_name=validate_by,
            tool_name="cli.runner_validate",
            task_level=task["task_level"],
            required_confirmation=task.get("route_result", {}).get(
                "required_confirmation",
                "none",
            ),
            current_status=task["status"],
        )
        repository_config = get_repository_config(repository)
        validation_gates = _resolve_task_validation_gates(task, gate)
        _require_runner_repository_preflight(
            task,
            repository_config,
            validation_gates,
            by=patch_by,
        )
        execution_result = apply_text_patch_operations(
            [
                {
                    "path": path,
                    "old_text": old_text,
                    "new_text": new_text,
                }
            ],
            repo_root=repository_config.workspace_path,
            dry_run=not apply,
        )
        validation_result = execute_runner_validation_commands(
            validation_gates,
            repo_root=repository_config.workspace_path,
            timeout_seconds=timeout_seconds,
        )
    except (PermissionError, ValueError, FileNotFoundError) as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    implementation_result = build_implementation_result_from_execution(execution_result)
    delivered = validation_result["deliverable"]
    next_status = "DELIVERED" if delivered else "VALIDATION_FAILED"
    artifact_uri = None
    artifact_type = None

    if apply:
        artifact_task = {
            **task,
            "status": next_status,
            "implementation_result": implementation_result,
            "validation_result": validation_result,
        }
        if delivered:
            artifact_path = save_patch_artifact(artifact_task)
            artifact_type = "runner_patch"
            artifact_summary = "Agent Runner patch attempt artifact"
        else:
            artifact_path = save_failure_feedback_artifact(artifact_task)
            artifact_type = "runner_failure_feedback"
            artifact_summary = "Agent Runner failed patch attempt artifact"

        artifact_uri = str(artifact_path)
        record_artifact(
            task_id=task["id"],
            artifact_type=artifact_type,
            artifact_uri=artifact_uri,
            access_level="internal",
            retention_days=365,
            summary=artifact_summary,
        )
        record_data_asset(
            asset_name=artifact_uri,
            asset_type=artifact_type,
            classification="D1",
            primary_storage="Git / Markdown",
            owner="gongbu",
            task_id=task["id"],
            allowed_copies=["PostgreSQL", "pgvector"],
            forbidden_storages=["Secret Manager"],
            allow_vectorization=True,
            desensitized=True,
            retention_days=365,
            notes="Agent Runner patch attempt evidence.",
        )
        update_task_status(task["id"], next_status)

    event_type = "runner_attempt_delivered" if delivered else "runner_attempt_failed"
    record_task_event(
        task_id=task["id"],
        event_type=event_type,
        from_status=task["status"],
        to_status=next_status if apply else task["status"],
        summary=(
            f"Runner attempt {'applied' if apply else 'dry-run'}: {', '.join(validation_gates)}"
        ),
        created_by=patch_by,
    )
    record_tool_call(
        task_id=task["id"],
        agent_name=patch_by,
        tool_name="cli.runner_patch",
        arguments_summary=(
            f"task_code={task_code}; repository={repository_config.name}; "
            f"path={path}; apply={apply}"
        ),
        permission_policy=patch_permission["permission_policy"],
        result_status="success",
        permission_decision=patch_permission,
        output_summary=(
            f"changed_files={execution_result['changed_files']}; "
            f"applied={execution_result['applied']}"
        ),
        risk_flag=patch_permission["risk_flag"],
    )
    record_tool_call(
        task_id=task["id"],
        agent_name=validate_by,
        tool_name="cli.runner_validate",
        arguments_summary=(
            f"task_code={task_code}; repository={repository_config.name}; gates={validation_gates}"
        ),
        permission_policy=validation_permission["permission_policy"],
        result_status="success" if delivered else "failed",
        permission_decision=validation_permission,
        output_summary=f"deliverable={delivered}",
        risk_flag=validation_permission["risk_flag"],
    )

    print_json(
        data={
            "task_code": task_code,
            "repository": repository_config.to_safe_dict(),
            "status": next_status,
            "artifact_type": artifact_type,
            "artifact_uri": artifact_uri,
            "implementation_result": implementation_result,
            "validation_result": validation_result,
        }
    )

    if not delivered:
        raise typer.Exit(code=1)


@app.command()
def approve(
    task_code: str,
    by: str = typer.Option("emperor", "--by", help="确认人"),
    note: str = typer.Option("", "--note", help="确认说明"),
):
    try:
        task = approve_task(task_code=task_code, confirmed_by=by, note=note)
    except ValueError as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    print_json(data=task)


@app.command("bind-github")
def bind_github(
    task_code: str,
    link_type: str,
    external_id: str,
    url: str,
    title: str | None = typer.Option(None, "--title", help="GitHub 标题"),
    link_status: str | None = typer.Option(None, "--status", help="GitHub 状态"),
    by: str = typer.Option("shangshu", "--by", help="记录人"),
):
    task = get_task_detail(task_code)

    if not task:
        print(f"[red]Task not found:[/red] {task_code}")
        raise typer.Exit(code=1)

    try:
        normalized_link_type = normalize_github_link_type(link_type)
        permission_decision = require_tool_permission(
            agent_name="shangshu",
            tool_name="cli.bind_github",
            task_level=task["task_level"],
            required_confirmation=task.get("route_result", {}).get(
                "required_confirmation",
                "none",
            ),
            current_status=task["status"],
        )
        record_github_link(
            task_id=task["id"],
            link_type=normalized_link_type,
            external_id=external_id,
            url=url,
            title=title,
            status=link_status,
            metadata={"task_code": task_code},
            created_by=by,
        )
    except (PermissionError, ValueError) as exc:
        print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    record_task_event(
        task_id=task["id"],
        event_type="github_link_bound",
        from_status=task["status"],
        to_status=task["status"],
        summary=f"绑定 GitHub {normalized_link_type}: {external_id}",
        created_by=by,
    )
    record_tool_call(
        task_id=task["id"],
        agent_name="shangshu",
        tool_name="cli.bind_github",
        arguments_summary=(
            f"task_code={task_code}; link_type={normalized_link_type}; external_id={external_id}"
        ),
        permission_policy=permission_decision["permission_policy"],
        result_status="success",
        permission_decision=permission_decision,
        output_summary=f"url={url}",
        risk_flag=permission_decision["risk_flag"],
    )

    updated_task = get_task_detail(task_code)
    print_json(data=updated_task)


@app.command("doctor")
def doctor_command(as_json: bool = typer.Option(False, "--json", help="Output JSON")):
    report = run_chao_doctor()

    if as_json:
        print_json(data=report)
    else:
        table = Table(title="Chao First-Run Doctor")
        table.add_column("Check")
        table.add_column("Ready")
        table.add_column("Summary")
        for check in report["checks"]:
            table.add_row(
                check["name"],
                "yes" if check["ready"] else "no",
                check["summary"],
            )
        console.print(table)

    if not report["ready"]:
        raise typer.Exit(code=1)


@app.command()
def status():
    print("[green]chao local mvp is running[/green]")


if __name__ == "__main__":
    app()

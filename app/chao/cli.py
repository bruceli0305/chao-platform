import uuid
from datetime import datetime
from typing import Annotated

import typer
from rich import print, print_json
from rich.console import Console
from rich.table import Table

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
from app.chao.mcp_server import serve_mcp
from app.chao.permissions import require_tool_permission
from app.chao.runner_artifacts import save_failure_feedback_artifact, save_patch_artifact
from app.chao.runner_branch import create_runner_branch
from app.chao.runner_executor import (
    apply_text_patch_operations,
    build_implementation_result_from_execution,
)
from app.chao.runner_policy import build_runner_branch_plan, build_runner_workspace_plan
from app.chao.runner_sandbox import DEFAULT_SANDBOX_IMAGE, execute_runner_sandbox_commands
from app.chao.runner_validation import execute_runner_validation_commands
from app.chao.runner_workspace import create_runner_workspace
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
from app.chao.services.tool_calls import record_tool_call
from app.chao.tool_gateway_server import serve_tool_gateway
from app.chao.web_console import run_web_console_server

app = typer.Typer()
console = Console()


def _display_value(value: object) -> str:
    if value is None:
        return ""

    return str(value)


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


@app.command("mcp-serve")
def mcp_serve_command():
    raise typer.Exit(code=serve_mcp())


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
    base_ref: str = typer.Option("HEAD", "--base-ref", help="Git base ref for branch creation"),
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
        branch_plan = build_runner_branch_plan(
            task_code=task_code,
            title=task.get("title", ""),
            task_level=task["task_level"],
            base_ref=base_ref,
        )
        branch_result = create_runner_branch(
            branch_plan,
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
        arguments_summary=f"task_code={task_code}; base_ref={base_ref}; apply={apply}",
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
            "branch_plan": branch_plan,
            "branch_result": branch_result,
        }
    )


@app.command("runner-workspace")
def runner_workspace_command(
    task_code: str,
    base_ref: str = typer.Option("HEAD", "--base-ref", help="Git base ref for worktree creation"),
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
        workspace_plan = build_runner_workspace_plan(
            task_code=task_code,
            title=task.get("title", ""),
            task_level=task["task_level"],
            base_ref=base_ref,
        )
        workspace_result = create_runner_workspace(
            workspace_plan,
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
        arguments_summary=f"task_code={task_code}; base_ref={base_ref}; apply={apply}",
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
            "workspace_plan": workspace_plan,
            "workspace_result": workspace_result,
        }
    )


@app.command("runner-sandbox")
def runner_sandbox_command(
    task_code: str,
    gate: Annotated[
        list[str],
        typer.Option("--gate", help="Validation gate to run in Docker sandbox"),
    ],
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
        sandbox_result = execute_runner_sandbox_commands(
            gate,
            workspace_path=workspace_path,
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
            f"task_code={task_code}; gates={gate}; workspace_path={workspace_path}; "
            f"image={image}; apply={apply}"
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
        execution_result = apply_text_patch_operations(
            [
                {
                    "path": path,
                    "old_text": old_text,
                    "new_text": new_text,
                }
            ],
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
        arguments_summary=f"task_code={task_code}; path={path}; apply={apply}",
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
            "execution_result": execution_result,
        }
    )


@app.command("runner-validate")
def runner_validate_command(
    task_code: str,
    gate: Annotated[
        list[str],
        typer.Option("--gate", help="Validation gate to execute"),
    ],
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
        validation_result = execute_runner_validation_commands(
            gate,
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
        summary=f"Runner validation {result_status}: {', '.join(gate)}",
        created_by=by,
    )
    record_tool_call(
        task_id=task["id"],
        agent_name=by,
        tool_name="cli.runner_validate",
        arguments_summary=f"task_code={task_code}; gates={gate}",
        permission_policy=permission_decision["permission_policy"],
        result_status=result_status,
        permission_decision=permission_decision,
        output_summary=f"deliverable={validation_result['deliverable']}",
        risk_flag=permission_decision["risk_flag"],
    )

    print_json(data={"task_code": task_code, "validation_result": validation_result})

    if not validation_result["deliverable"]:
        raise typer.Exit(code=1)


@app.command("runner-attempt")
def runner_attempt_command(
    task_code: str,
    path: str,
    gate: Annotated[
        list[str],
        typer.Option("--gate", help="Validation gate to execute after patch"),
    ],
    old_text: str = typer.Option(..., "--old-text", help="Text that must match once"),
    new_text: str = typer.Option(..., "--new-text", help="Replacement text"),
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
        execution_result = apply_text_patch_operations(
            [
                {
                    "path": path,
                    "old_text": old_text,
                    "new_text": new_text,
                }
            ],
            dry_run=not apply,
        )
        validation_result = execute_runner_validation_commands(
            gate,
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
        summary=f"Runner attempt {'applied' if apply else 'dry-run'}: {', '.join(gate)}",
        created_by=patch_by,
    )
    record_tool_call(
        task_id=task["id"],
        agent_name=patch_by,
        tool_name="cli.runner_patch",
        arguments_summary=f"task_code={task_code}; path={path}; apply={apply}",
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
        arguments_summary=f"task_code={task_code}; gates={gate}",
        permission_policy=validation_permission["permission_policy"],
        result_status="success" if delivered else "failed",
        permission_decision=validation_permission,
        output_summary=f"deliverable={delivered}",
        risk_flag=validation_permission["risk_flag"],
    )

    print_json(
        data={
            "task_code": task_code,
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


@app.command()
def status():
    print("[green]chao local mvp is running[/green]")


if __name__ == "__main__":
    app()

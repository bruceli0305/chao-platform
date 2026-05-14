import uuid
from datetime import datetime

import typer
from rich import print, print_json
from rich.console import Console
from rich.table import Table

from app.chao.graph.main_graph import build_graph
from app.chao.permissions import require_tool_permission
from app.chao.services.artifacts import record_artifact
from app.chao.services.console import get_console_overview
from app.chao.services.data_assets import record_data_asset
from app.chao.services.events import record_task_event
from app.chao.services.github_links import normalize_github_link_type, record_github_link
from app.chao.services.markdown_records import save_task_markdown
from app.chao.services.store import approve_task, get_task_detail, list_tasks, save_task_result
from app.chao.services.tool_calls import record_tool_call

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

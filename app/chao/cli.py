import uuid
from datetime import datetime

import typer
from rich import print, print_json
from rich.console import Console
from rich.table import Table

from app.chao.graph.main_graph import build_graph
from app.chao.services.artifacts import record_artifact
from app.chao.services.data_assets import record_data_asset
from app.chao.services.markdown_records import save_task_markdown
from app.chao.services.store import approve_task, get_task_detail, list_tasks, save_task_result

app = typer.Typer()
console = Console()


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


@app.command()
def status():
    print("[green]chao local mvp is running[/green]")


if __name__ == "__main__":
    app()

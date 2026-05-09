import uuid
from datetime import datetime

import typer
from rich import print
from rich import print_json
from rich.table import Table
from rich.console import Console

from app.chao.graph.main_graph import build_graph
from app.chao.services.store import save_task_result, list_tasks, get_task_detail
from app.chao.services.markdown_records import save_task_markdown

app = typer.Typer()
console = Console()


@app.command()
def new(title: str, request: str):
    task_id = str(uuid.uuid4())
    task_code = "TASK-" + datetime.now().strftime("%Y%m%d-%H%M%S")

    graph = build_graph()

    result = graph.invoke({
        "task_id": task_id,
        "task_code": task_code,
        "title": title,
        "raw_request": request,
        "status": "RAW",
    })

    save_task_result(result)
    markdown_path = save_task_markdown(result)

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
def status():
    print("[green]chao local mvp is running[/green]")


if __name__ == "__main__":
    app()

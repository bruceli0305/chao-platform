import uuid
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from app.chao.config import DATABASE_URL
from app.chao.permissions import evaluate_tool_permission
from app.chao.services.artifacts import list_artifacts
from app.chao.services.data_assets import list_task_data_assets
from app.chao.services.events import list_task_events, record_task_event
from app.chao.services.tool_calls import list_tool_calls, record_tool_call


def save_task_result(result: dict[str, Any]) -> None:
    task_id = result["task_id"]

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into tasks (
                    id,
                    task_code,
                    title,
                    raw_request,
                    task_level,
                    status,
                    owner
                )
                values (%s, %s, %s, %s, %s, %s, %s)
                on conflict (task_code) do update set
                    title = excluded.title,
                    raw_request = excluded.raw_request,
                    task_level = excluded.task_level,
                    status = excluded.status,
                    owner = excluded.owner,
                    updated_at = now()
                """,
                (
                    task_id,
                    result["task_code"],
                    result["title"],
                    result["raw_request"],
                    result.get("task_level", "UNKNOWN"),
                    result.get("status", "UNKNOWN"),
                    "shangshu",
                ),
            )

            if result.get("route_result"):
                cur.execute(
                    """
                    insert into task_routes (
                        id,
                        task_id,
                        route_json
                    )
                    values (%s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        task_id,
                        Jsonb(result["route_result"]),
                    ),
                )

            for record in result.get("historian_records", []):
                cur.execute(
                    """
                    insert into historian_records (
                        id,
                        task_id,
                        record_type,
                        content,
                        source,
                        created_by
                    )
                    values (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        task_id,
                        record.get("type", "unknown"),
                        record.get("content", ""),
                        "langgraph-local-mvp",
                        "historian",
                    ),
                )

            validation = result.get("validation_result")
            if validation:
                for gate in validation.get("checks", []):
                    cur.execute(
                        """
                        insert into gate_results (
                            id,
                            task_id,
                            gate_name,
                            status,
                            command,
                            output
                        )
                        values (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(uuid.uuid4()),
                            task_id,
                            gate,
                            validation.get("quality", "unknown"),
                            "local-mvp-smoke-test",
                            validation.get("note", ""),
                        ),
                    )

        conn.commit()

    record_task_event(
        task_id=task_id,
        event_type="task_created",
        from_status="RAW",
        to_status=result.get("status", "UNKNOWN"),
        summary=f"任务已创建并完成路由，当前状态：{result.get('status', 'UNKNOWN')}",
        created_by="shangshu",
    )

    record_tool_call(
        task_id=task_id,
        agent_name="shangshu",
        tool_name="cli.new",
        arguments_summary=f"title={result.get('title', '')}; level={result.get('task_level', '')}",
        permission_policy=evaluate_tool_permission(
            agent_name="shangshu",
            tool_name="cli.new",
            task_level=result.get("task_level", "L1"),
            required_confirmation=result.get("required_confirmation", "none"),
            current_status=result.get("status", "UNKNOWN"),
        )["permission_policy"],
        result_status="success",
        output_summary=(
            f"task_code={result.get('task_code', '')}; status={result.get('status', '')}"
        ),
        risk_flag=None,
    )


def list_tasks(limit: int = 10) -> list[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    id::text,
                    task_code,
                    title,
                    task_level,
                    status,
                    owner,
                    created_at::text
                from tasks
                order by created_at desc
                limit %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [
        {
            "id": row[0],
            "task_code": row[1],
            "title": row[2],
            "task_level": row[3],
            "status": row[4],
            "owner": row[5],
            "created_at": row[6],
        }
        for row in rows
    ]


def get_task_detail(task_code: str) -> dict[str, Any] | None:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    id::text,
                    task_code,
                    title,
                    raw_request,
                    task_level,
                    status,
                    owner,
                    created_at::text,
                    updated_at::text
                from tasks
                where task_code = %s
                """,
                (task_code,),
            )
            task = cur.fetchone()

            if not task:
                return None

            task_id = task[0]

            cur.execute(
                """
                select record_type, content, source, created_by, created_at::text
                from historian_records
                where task_id = %s
                order by created_at asc
                """,
                (task_id,),
            )
            records = cur.fetchall()

            cur.execute(
                """
                select gate_name, status, command, output, created_at::text
                from gate_results
                where task_id = %s
                order by created_at asc
                """,
                (task_id,),
            )
            gates = cur.fetchall()

            cur.execute(
                """
                select route_json
                from task_routes
                where task_id = %s
                order by created_at desc
                limit 1
                """,
                (task_id,),
            )
            route = cur.fetchone()
            route_result = route[0] if route else {}

    return {
        "id": task[0],
        "task_code": task[1],
        "title": task[2],
        "raw_request": task[3],
        "task_level": task[4],
        "status": task[5],
        "owner": task[6],
        "created_at": task[7],
        "updated_at": task[8],
        "route_result": route_result,
        "required_skills": route_result.get("required_skills", []),
        "required_skill_paths": route_result.get("required_skill_paths", []),
        "required_skill_details": route_result.get("required_skill_details", []),
        "events": list_task_events(task[0]),
        "tool_calls": list_tool_calls(task[0]),
        "artifacts": list_artifacts(task[0]),
        "data_assets": list_task_data_assets(task[0]),
        "historian_records": [
            {
                "record_type": r[0],
                "content": r[1],
                "source": r[2],
                "created_by": r[3],
                "created_at": r[4],
            }
            for r in records
        ],
        "gate_results": [
            {
                "gate_name": g[0],
                "status": g[1],
                "command": g[2],
                "output": g[3],
                "created_at": g[4],
            }
            for g in gates
        ],
    }


def approve_task(task_code: str, confirmed_by: str, note: str = "") -> dict[str, Any]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id::text, task_code, title, task_level, status
                from tasks
                where task_code = %s
                """,
                (task_code,),
            )
            task = cur.fetchone()

            if not task:
                raise ValueError(f"Task not found: {task_code}")

            task_id = task[0]
            current_status = task[4]

            if current_status != "NEED_CONFIRMATION":
                raise ValueError(
                    f"Task {task_code} is not waiting for confirmation. "
                    f"Current status: {current_status}"
                )

            cur.execute(
                """
                insert into confirmations (
                    id,
                    task_id,
                    confirmation_level,
                    status,
                    confirmed_by,
                    note
                )
                values (%s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    task_id,
                    "A",
                    "APPROVED",
                    confirmed_by,
                    note,
                ),
            )

            cur.execute(
                """
                update tasks
                set status = %s, updated_at = now()
                where id = %s
                """,
                ("APPROVED", task_id),
            )

            cur.execute(
                """
                insert into historian_records (
                    id,
                    task_id,
                    record_type,
                    content,
                    source,
                    created_by
                )
                values (%s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    task_id,
                    "confirmation",
                    f"A 级事项已由 {confirmed_by} 确认。说明：{note or '无'}",
                    "cli-approve",
                    "historian",
                ),
            )

        conn.commit()

    record_task_event(
        task_id=task_id,
        event_type="task_approved",
        from_status="NEED_CONFIRMATION",
        to_status="APPROVED",
        summary=f"A 级事项已由 {confirmed_by} 确认。",
        created_by=confirmed_by,
    )

    record_tool_call(
        task_id=task_id,
        agent_name="emperor",
        tool_name="cli.approve",
        arguments_summary=f"task_code={task_code}; confirmed_by={confirmed_by}",
        permission_policy=evaluate_tool_permission(
            agent_name="emperor",
            tool_name="cli.approve",
            task_level="L3",
            required_confirmation="A",
            current_status=current_status,
        )["permission_policy"],
        result_status="success",
        output_summary=f"task_code={task_code}; status=APPROVED",
        risk_flag="A_CONFIRMATION",
    )

    detail = get_task_detail(task_code)
    if detail is None:
        raise ValueError(f"Task not found after approval: {task_code}")

    return detail

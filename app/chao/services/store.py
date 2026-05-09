import uuid
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from app.chao.config import DATABASE_URL


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

from typing import Any

import psycopg

from app.chao.config import DATABASE_URL


def _rows_to_counts(rows: list[tuple[str, int]]) -> dict[str, int]:
    return {name: count for name, count in rows}


def _route_value(route_result: dict[str, Any] | None, key: str) -> Any:
    if not route_result:
        return None

    return route_result.get(key)


def get_console_overview(limit: int = 10) -> dict[str, Any]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select status, count(*)
                from tasks
                group by status
                order by status asc
                """
            )
            task_status_rows = cur.fetchall()

            cur.execute(
                """
                select task_level, count(*)
                from tasks
                group by task_level
                order by task_level asc
                """
            )
            task_level_rows = cur.fetchall()

            cur.execute(
                """
                select count(*)
                from confirmations
                where status = 'APPROVED'
                """
            )
            approved_confirmations = cur.fetchone()[0]

            cur.execute("select count(*) from artifacts")
            artifact_count = cur.fetchone()[0]

            cur.execute("select count(*) from data_assets")
            data_asset_count = cur.fetchone()[0]

            cur.execute(
                """
                select count(*)
                from tool_calls
                where result_status <> 'success'
                """
            )
            failed_tool_call_count = cur.fetchone()[0]

            cur.execute(
                """
                select
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
            recent_task_rows = cur.fetchall()

    return {
        "task_status_counts": _rows_to_counts(task_status_rows),
        "task_level_counts": _rows_to_counts(task_level_rows),
        "approved_confirmations": approved_confirmations,
        "artifact_count": artifact_count,
        "data_asset_count": data_asset_count,
        "failed_tool_call_count": failed_tool_call_count,
        "recent_tasks": [
            {
                "task_code": row[0],
                "title": row[1],
                "task_level": row[2],
                "status": row[3],
                "owner": row[4],
                "created_at": row[5],
            }
            for row in recent_task_rows
        ],
    }


def get_console_approval_queue(limit: int = 20) -> list[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    t.task_code,
                    t.title,
                    t.task_level,
                    t.status,
                    t.owner,
                    t.created_at::text,
                    tr.route_json
                from tasks t
                left join lateral (
                    select route_json
                    from task_routes
                    where task_id = t.id
                    order by created_at desc
                    limit 1
                ) tr on true
                where t.status = 'NEED_CONFIRMATION'
                order by t.created_at asc
                limit %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [
        {
            "task_code": row[0],
            "title": row[1],
            "task_level": row[2],
            "status": row[3],
            "owner": row[4],
            "created_at": row[5],
            "required_confirmation": _route_value(row[6], "required_confirmation"),
            "required_skills": _route_value(row[6], "required_skills") or [],
            "required_skill_paths": _route_value(row[6], "required_skill_paths") or [],
        }
        for row in rows
    ]

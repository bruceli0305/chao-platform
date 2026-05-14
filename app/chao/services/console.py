from typing import Any

import psycopg

from app.chao.config import DATABASE_URL


def _rows_to_counts(rows: list[tuple[str, int]]) -> dict[str, int]:
    return {name: count for name, count in rows}


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

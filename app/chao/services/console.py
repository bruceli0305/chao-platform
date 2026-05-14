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


def get_console_audit(limit: int = 20) -> dict[str, list[dict[str, Any]]]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    t.task_code,
                    e.event_type,
                    e.from_status,
                    e.to_status,
                    e.summary,
                    e.created_by,
                    e.created_at::text
                from task_events e
                join tasks t on t.id = e.task_id
                order by e.created_at desc
                limit %s
                """,
                (limit,),
            )
            event_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    tc.agent_name,
                    tc.tool_name,
                    tc.permission_policy,
                    tc.result_status,
                    tc.risk_flag,
                    tc.started_at::text
                from tool_calls tc
                join tasks t on t.id = tc.task_id
                order by tc.started_at desc
                limit %s
                """,
                (limit,),
            )
            tool_call_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    a.artifact_type,
                    a.artifact_uri,
                    a.access_level,
                    a.retention_days,
                    a.created_at::text
                from artifacts a
                join tasks t on t.id = a.task_id
                order by a.created_at desc
                limit %s
                """,
                (limit,),
            )
            artifact_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    da.asset_name,
                    da.asset_type,
                    da.classification,
                    da.owner,
                    da.created_at::text
                from data_assets da
                left join tasks t on t.id = da.task_id
                order by da.created_at desc
                limit %s
                """,
                (limit,),
            )
            data_asset_rows = cur.fetchall()

            cur.execute(
                """
                select
                    t.task_code,
                    gl.link_type,
                    gl.external_id,
                    gl.url,
                    gl.status,
                    gl.created_by,
                    gl.created_at::text
                from github_links gl
                join tasks t on t.id = gl.task_id
                order by gl.created_at desc
                limit %s
                """,
                (limit,),
            )
            github_link_rows = cur.fetchall()

    return {
        "events": [
            {
                "task_code": row[0],
                "event_type": row[1],
                "from_status": row[2],
                "to_status": row[3],
                "summary": row[4],
                "created_by": row[5],
                "created_at": row[6],
            }
            for row in event_rows
        ],
        "tool_calls": [
            {
                "task_code": row[0],
                "agent_name": row[1],
                "tool_name": row[2],
                "permission_policy": row[3],
                "result_status": row[4],
                "risk_flag": row[5],
                "started_at": row[6],
            }
            for row in tool_call_rows
        ],
        "artifacts": [
            {
                "task_code": row[0],
                "artifact_type": row[1],
                "artifact_uri": row[2],
                "access_level": row[3],
                "retention_days": row[4],
                "created_at": row[5],
            }
            for row in artifact_rows
        ],
        "data_assets": [
            {
                "task_code": row[0],
                "asset_name": row[1],
                "asset_type": row[2],
                "classification": row[3],
                "owner": row[4],
                "created_at": row[5],
            }
            for row in data_asset_rows
        ],
        "github_links": [
            {
                "task_code": row[0],
                "link_type": row[1],
                "external_id": row[2],
                "url": row[3],
                "status": row[4],
                "created_by": row[5],
                "created_at": row[6],
            }
            for row in github_link_rows
        ],
    }

import hashlib
import uuid
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from app.chao.config import DATABASE_URL

DEFAULT_STALE_PENDING_TOOL_CALL_MINUTES = 15


def _hash_text(value: str | None) -> str | None:
    if not value:
        return None

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def record_tool_call(
    task_id: str,
    agent_name: str,
    tool_name: str,
    arguments_summary: str | None,
    permission_policy: str | None,
    result_status: str,
    permission_decision: dict[str, Any] | None = None,
    output_summary: str | None = None,
    risk_flag: str | None = None,
) -> None:
    output_hash = _hash_text(output_summary)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into tool_calls (
                    id,
                    task_id,
                    agent_name,
                    tool_name,
                    arguments_summary,
                    permission_policy,
                    permission_decision,
                    result_status,
                    output_hash,
                    risk_flag,
                    finished_at
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                """,
                (
                    str(uuid.uuid4()),
                    task_id,
                    agent_name,
                    tool_name,
                    arguments_summary,
                    permission_policy,
                    Jsonb(permission_decision or {}),
                    result_status,
                    output_hash,
                    risk_flag,
                ),
            )

        conn.commit()


def start_tool_call(
    task_id: str,
    agent_name: str,
    tool_name: str,
    arguments_summary: str | None,
    permission_policy: str | None,
    permission_decision: dict[str, Any] | None = None,
    risk_flag: str | None = None,
) -> str:
    tool_call_id = str(uuid.uuid4())

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into tool_calls (
                    id,
                    task_id,
                    agent_name,
                    tool_name,
                    arguments_summary,
                    permission_policy,
                    permission_decision,
                    result_status,
                    risk_flag
                )
                values (%s, %s, %s, %s, %s, %s, %s, 'started', %s)
                """,
                (
                    tool_call_id,
                    task_id,
                    agent_name,
                    tool_name,
                    arguments_summary,
                    permission_policy,
                    Jsonb(permission_decision or {}),
                    risk_flag,
                ),
            )

        conn.commit()

    return tool_call_id


def finish_tool_call(
    tool_call_id: str,
    *,
    result_status: str,
    output_summary: str | None = None,
    permission_decision: dict[str, Any] | None = None,
    risk_flag: str | None = None,
) -> None:
    output_hash = _hash_text(output_summary)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                update tool_calls
                set
                    result_status = %s,
                    output_hash = %s,
                    permission_decision = coalesce(%s, permission_decision),
                    risk_flag = coalesce(%s, risk_flag),
                    finished_at = now()
                where id = %s
                """,
                (
                    result_status,
                    output_hash,
                    Jsonb(permission_decision) if permission_decision is not None else None,
                    risk_flag,
                    tool_call_id,
                ),
            )

        conn.commit()


def list_stale_pending_tool_calls(
    *,
    max_age_minutes: int = DEFAULT_STALE_PENDING_TOOL_CALL_MINUTES,
    limit: int = 100,
) -> list[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    tc.id,
                    tc.task_id,
                    t.task_code,
                    tc.agent_name,
                    tc.tool_name,
                    tc.permission_policy,
                    tc.result_status,
                    tc.risk_flag,
                    tc.started_at::text,
                    floor(extract(epoch from (now() - tc.started_at)) / 60)::int
                from tool_calls tc
                join tasks t on t.id = tc.task_id
                where lower(coalesce(tc.result_status, '')) = 'started'
                  and tc.finished_at is null
                  and tc.started_at < now() - (%s::int * interval '1 minute')
                order by tc.started_at asc
                limit %s
                """,
                (max_age_minutes, limit),
            )
            rows = cur.fetchall()

    return [_stale_pending_tool_call_from_row(row) for row in rows]


def mark_stale_pending_tool_calls_timed_out(
    *,
    max_age_minutes: int = DEFAULT_STALE_PENDING_TOOL_CALL_MINUTES,
    limit: int = 100,
    output_summary: str | None = None,
) -> list[dict[str, Any]]:
    output_hash = _hash_text(
        output_summary or f"Tool call exceeded pending timeout of {max_age_minutes} minute(s)."
    )

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                with stale as (
                    select
                        tc.id,
                        tc.task_id,
                        t.task_code,
                        floor(extract(epoch from (now() - tc.started_at)) / 60)::int
                            as age_minutes
                    from tool_calls tc
                    join tasks t on t.id = tc.task_id
                    where lower(coalesce(tc.result_status, '')) = 'started'
                      and tc.finished_at is null
                      and tc.started_at < now() - (%s::int * interval '1 minute')
                    order by tc.started_at asc
                    limit %s
                )
                update tool_calls tc
                set
                    result_status = 'timed_out',
                    output_hash = %s,
                    risk_flag = coalesce(tc.risk_flag, 'high'),
                    finished_at = now()
                from stale
                where tc.id = stale.id
                returning
                    tc.id,
                    tc.task_id,
                    stale.task_code,
                    tc.agent_name,
                    tc.tool_name,
                    tc.permission_policy,
                    tc.result_status,
                    tc.risk_flag,
                    tc.started_at::text,
                    stale.age_minutes
                """,
                (max_age_minutes, limit, output_hash),
            )
            rows = cur.fetchall()

        conn.commit()

    return [_stale_pending_tool_call_from_row(row) for row in rows]


def _stale_pending_tool_call_from_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": row[0],
        "task_id": row[1],
        "task_code": row[2],
        "agent_name": row[3],
        "tool_name": row[4],
        "permission_policy": row[5],
        "result_status": row[6],
        "risk_flag": row[7],
        "started_at": row[8],
        "age_minutes": row[9],
    }


def list_tool_calls(task_id: str) -> list[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    agent_name,
                    tool_name,
                    arguments_summary,
                    permission_policy,
                    permission_decision,
                    result_status,
                    output_hash,
                    risk_flag,
                    started_at::text,
                    finished_at::text
                from tool_calls
                where task_id = %s
                order by started_at asc
                """,
                (task_id,),
            )
            rows = cur.fetchall()

    return [
        {
            "agent_name": row[0],
            "tool_name": row[1],
            "arguments_summary": row[2],
            "permission_policy": row[3],
            "permission_decision": row[4],
            "result_status": row[5],
            "output_hash": row[6],
            "risk_flag": row[7],
            "started_at": row[8],
            "finished_at": row[9],
        }
        for row in rows
    ]

import hashlib
import uuid
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from app.chao.config import DATABASE_URL


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

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg

from app.chao.config import DATABASE_URL


def record_llm_egress_authorization(
    *,
    task_id: str,
    provider: str,
    model: str,
    data_classification: str,
    authorized_by: str,
    reason: str | None = None,
    ttl_hours: int = 24,
) -> dict[str, Any]:
    authorization = {
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "provider": provider,
        "model": model,
        "data_classification": data_classification,
        "status": "APPROVED",
        "authorized_by": authorized_by,
        "reason": reason or "",
        "expires_at": datetime.now(UTC) + timedelta(hours=ttl_hours),
    }

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into llm_egress_authorizations (
                    id,
                    task_id,
                    provider,
                    model,
                    data_classification,
                    status,
                    authorized_by,
                    reason,
                    expires_at
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    authorization["id"],
                    authorization["task_id"],
                    authorization["provider"],
                    authorization["model"],
                    authorization["data_classification"],
                    authorization["status"],
                    authorization["authorized_by"],
                    authorization["reason"],
                    authorization["expires_at"],
                ),
            )

        conn.commit()

    return {**authorization, "expires_at": authorization["expires_at"].isoformat()}


def list_task_llm_egress_authorizations(task_id: str) -> list[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    provider,
                    model,
                    data_classification,
                    status,
                    authorized_by,
                    reason,
                    expires_at::text,
                    created_at::text,
                    (status = 'APPROVED' and expires_at > now()) as active
                from llm_egress_authorizations
                where task_id = %s
                order by created_at asc
                """,
                (task_id,),
            )
            rows = cur.fetchall()

    return [
        {
            "provider": row[0],
            "model": row[1],
            "data_classification": row[2],
            "status": row[3],
            "authorized_by": row[4],
            "reason": row[5],
            "expires_at": row[6],
            "created_at": row[7],
            "active": row[8],
        }
        for row in rows
    ]

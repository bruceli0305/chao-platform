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


def list_expired_llm_egress_authorizations(limit: int = 100) -> list[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    lea.id::text,
                    lea.task_id::text,
                    t.task_code,
                    t.task_level,
                    t.status as task_status,
                    tr.required_confirmation,
                    lea.provider,
                    lea.model,
                    lea.data_classification,
                    lea.status,
                    lea.authorized_by,
                    lea.reason,
                    lea.expires_at::text,
                    lea.created_at::text
                from llm_egress_authorizations lea
                join tasks t on t.id = lea.task_id
                left join lateral (
                    select route_json->>'required_confirmation' as required_confirmation
                    from task_routes
                    where task_id = t.id
                    order by created_at desc
                    limit 1
                ) tr on true
                where lea.status = 'APPROVED'
                  and lea.expires_at <= now()
                order by lea.expires_at asc
                limit %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [_expired_authorization_from_row(row) for row in rows]


def expire_llm_egress_authorizations(
    *,
    limit: int = 100,
    dry_run: bool = True,
) -> dict[str, Any]:
    authorizations = list_expired_llm_egress_authorizations(limit=limit)

    if not dry_run and authorizations:
        mark_llm_egress_authorizations_expired(
            [authorization["id"] for authorization in authorizations]
        )
        authorizations = [
            {**authorization, "status": "EXPIRED"} for authorization in authorizations
        ]

    return {
        "dry_run": dry_run,
        "expired_count": len(authorizations),
        "authorizations": authorizations,
    }


def mark_llm_egress_authorizations_expired(authorization_ids: list[str]) -> None:
    if not authorization_ids:
        return

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            for authorization_id in authorization_ids:
                cur.execute(
                    """
                    update llm_egress_authorizations
                    set status = 'EXPIRED'
                    where id = %s
                      and status = 'APPROVED'
                      and expires_at <= now()
                    """,
                    (authorization_id,),
                )

        conn.commit()


def _expired_authorization_from_row(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": row[0],
        "task_id": row[1],
        "task_code": row[2],
        "task_level": row[3],
        "task_status": row[4],
        "required_confirmation": row[5] or "none",
        "provider": row[6],
        "model": row[7],
        "data_classification": row[8],
        "status": row[9],
        "authorized_by": row[10],
        "reason": row[11],
        "expires_at": row[12],
        "created_at": row[13],
    }

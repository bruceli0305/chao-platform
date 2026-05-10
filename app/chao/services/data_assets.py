import uuid
from typing import Any

import psycopg

from app.chao.config import DATABASE_URL


def record_data_asset(
    asset_name: str,
    asset_type: str,
    classification: str,
    primary_storage: str,
    owner: str,
    task_id: str | None = None,
    allowed_copies: list[str] | None = None,
    forbidden_storages: list[str] | None = None,
    allow_vectorization: bool = False,
    desensitized: bool = False,
    retention_days: int | None = None,
    notes: str | None = None,
) -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into data_assets (
                    id,
                    task_id,
                    asset_name,
                    asset_type,
                    classification,
                    primary_storage,
                    allowed_copies,
                    forbidden_storages,
                    allow_vectorization,
                    desensitized,
                    retention_days,
                    owner,
                    notes
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    task_id,
                    asset_name,
                    asset_type,
                    classification,
                    primary_storage,
                    allowed_copies or [],
                    forbidden_storages or [],
                    allow_vectorization,
                    desensitized,
                    retention_days,
                    owner,
                    notes,
                ),
            )

        conn.commit()


def list_data_assets(limit: int = 20) -> list[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    task_id::text,
                    asset_name,
                    asset_type,
                    classification,
                    primary_storage,
                    allowed_copies,
                    forbidden_storages,
                    allow_vectorization,
                    desensitized,
                    retention_days,
                    owner,
                    notes,
                    created_at::text
                from data_assets
                order by created_at desc
                limit %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

    return [
        {
            "task_id": row[0],
            "asset_name": row[1],
            "asset_type": row[2],
            "classification": row[3],
            "primary_storage": row[4],
            "allowed_copies": row[5],
            "forbidden_storages": row[6],
            "allow_vectorization": row[7],
            "desensitized": row[8],
            "retention_days": row[9],
            "owner": row[10],
            "notes": row[11],
            "created_at": row[12],
        }
        for row in rows
    ]


def list_task_data_assets(task_id: str) -> list[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    asset_name,
                    asset_type,
                    classification,
                    primary_storage,
                    allowed_copies,
                    forbidden_storages,
                    allow_vectorization,
                    desensitized,
                    retention_days,
                    owner,
                    notes,
                    created_at::text
                from data_assets
                where task_id = %s
                order by created_at asc
                """,
                (task_id,),
            )
            rows = cur.fetchall()

    return [
        {
            "asset_name": row[0],
            "asset_type": row[1],
            "classification": row[2],
            "primary_storage": row[3],
            "allowed_copies": row[4],
            "forbidden_storages": row[5],
            "allow_vectorization": row[6],
            "desensitized": row[7],
            "retention_days": row[8],
            "owner": row[9],
            "notes": row[10],
            "created_at": row[11],
        }
        for row in rows
    ]

import uuid
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from app.chao.config import DATABASE_URL

GITHUB_LINK_TYPE_ALIASES = {
    "issue": "issue",
    "issues": "issue",
    "pr": "pull_request",
    "pull_request": "pull_request",
    "pull-request": "pull_request",
    "commit": "commit",
    "ci": "ci_run",
    "ci_run": "ci_run",
    "ci-run": "ci_run",
}


def normalize_github_link_type(link_type: str) -> str:
    normalized = GITHUB_LINK_TYPE_ALIASES.get(link_type.strip().lower())

    if normalized is None:
        raise ValueError(f"Unsupported GitHub link type: {link_type}")

    return normalized


def record_github_link(
    *,
    task_id: str,
    link_type: str,
    external_id: str,
    url: str,
    title: str | None = None,
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
    created_by: str = "system",
) -> None:
    normalized_link_type = normalize_github_link_type(link_type)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into github_links (
                    id,
                    task_id,
                    link_type,
                    external_id,
                    url,
                    title,
                    status,
                    metadata,
                    created_by
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (task_id, link_type, external_id) do update set
                    url = excluded.url,
                    title = excluded.title,
                    status = excluded.status,
                    metadata = excluded.metadata,
                    created_by = excluded.created_by,
                    updated_at = now()
                """,
                (
                    str(uuid.uuid4()),
                    task_id,
                    normalized_link_type,
                    external_id,
                    url,
                    title,
                    status,
                    Jsonb(metadata or {}),
                    created_by,
                ),
            )

        conn.commit()


def list_task_github_links(task_id: str) -> list[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    link_type,
                    external_id,
                    url,
                    title,
                    status,
                    metadata,
                    created_by,
                    created_at::text,
                    updated_at::text
                from github_links
                where task_id = %s
                order by created_at asc
                """,
                (task_id,),
            )
            rows = cur.fetchall()

    return [
        {
            "link_type": row[0],
            "external_id": row[1],
            "url": row[2],
            "title": row[3],
            "status": row[4],
            "metadata": row[5],
            "created_by": row[6],
            "created_at": row[7],
            "updated_at": row[8],
        }
        for row in rows
    ]

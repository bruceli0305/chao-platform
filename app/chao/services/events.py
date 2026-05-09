import uuid
from typing import Any

import psycopg
from dotenv import load_dotenv

from app.chao.config import DATABASE_URL

load_dotenv()


def record_task_event(
    task_id: str,
    event_type: str,
    from_status: str | None,
    to_status: str | None,
    summary: str,
    created_by: str,
) -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into task_events (
                    id,
                    task_id,
                    event_type,
                    from_status,
                    to_status,
                    summary,
                    created_by
                )
                values (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    task_id,
                    event_type,
                    from_status,
                    to_status,
                    summary,
                    created_by,
                ),
            )

        conn.commit()


def list_task_events(task_id: str) -> list[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    event_type,
                    from_status,
                    to_status,
                    summary,
                    created_by,
                    created_at::text
                from task_events
                where task_id = %s
                order by created_at asc
                """,
                (task_id,),
            )
            rows = cur.fetchall()

    return [
        {
            "event_type": row[0],
            "from_status": row[1],
            "to_status": row[2],
            "summary": row[3],
            "created_by": row[4],
            "created_at": row[5],
        }
        for row in rows
    ]

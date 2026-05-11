import uuid

import psycopg

from app.chao.config import DATABASE_URL


def record_historian_record(
    *,
    task_id: str,
    record_type: str,
    content: str,
    source: str,
    created_by: str,
) -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into historian_records (
                    id,
                    task_id,
                    record_type,
                    content,
                    source,
                    created_by
                )
                values (%s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    task_id,
                    record_type,
                    content,
                    source,
                    created_by,
                ),
            )

        conn.commit()

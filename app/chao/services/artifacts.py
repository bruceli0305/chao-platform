import hashlib
import uuid
from pathlib import Path
from typing import Any

import psycopg

from app.chao.config import DATABASE_URL


def _sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def record_artifact(
    task_id: str,
    artifact_type: str,
    artifact_uri: str,
    access_level: str = "internal",
    retention_days: int | None = None,
    summary: str | None = None,
    artifact_hash: str | None = None,
) -> None:
    path = Path(artifact_uri)

    if artifact_hash is None:
        artifact_hash = _sha256_file(path)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into artifacts (
                    id,
                    task_id,
                    artifact_type,
                    artifact_uri,
                    artifact_hash,
                    access_level,
                    retention_days,
                    summary
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(uuid.uuid4()),
                    task_id,
                    artifact_type,
                    artifact_uri,
                    artifact_hash,
                    access_level,
                    retention_days,
                    summary,
                ),
            )

        conn.commit()


def list_artifacts(task_id: str) -> list[dict[str, Any]]:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    artifact_type,
                    artifact_uri,
                    artifact_hash,
                    access_level,
                    retention_days,
                    summary,
                    created_at::text
                from artifacts
                where task_id = %s
                order by created_at asc
                """,
                (task_id,),
            )
            rows = cur.fetchall()

    return [
        {
            "artifact_type": row[0],
            "artifact_uri": row[1],
            "artifact_hash": row[2],
            "access_level": row[3],
            "retention_days": row[4],
            "summary": row[5],
            "created_at": row[6],
        }
        for row in rows
    ]

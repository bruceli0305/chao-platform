import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv

try:
    from scripts.context_embeddings import build_local_embedding, format_pgvector
except ModuleNotFoundError:
    from context_embeddings import build_local_embedding, format_pgvector

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def get_database_url() -> str:
    load_dotenv()

    return os.getenv(
        "DATABASE_URL",
        "postgresql://chao:chao_dev_password@localhost:5432/chao",
    )


def map_context_row(row: tuple[Any, ...]) -> dict[str, Any]:
    result = {
        "source_path": row[0],
        "source_type": row[1],
        "data_classification": row[2],
        "source_hash": row[3],
        "redacted": row[4],
        "ingest_allowed": row[5],
        "retention_policy": row[6],
        "created_by": row[7],
        "created_at": row[8],
        "content_preview": row[9],
    }

    if len(row) > 10 and row[10] is not None:
        result["vector_distance"] = float(row[10])

    return result


def search_context_by_keyword(query: str, limit: int = 10) -> list[dict[str, Any]]:
    pattern = f"%{query}%"

    with psycopg.connect(get_database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    source_path,
                    source_type,
                    data_classification,
                    source_hash,
                    redacted,
                    ingest_allowed,
                    retention_policy,
                    created_by,
                    created_at::text,
                    left(content, 500) as content_preview
                from context_chunks
                where content ilike %s
                   or source_path ilike %s
                order by created_at desc
                limit %s
                """,
                (pattern, pattern, limit),
            )
            rows = cur.fetchall()

    return [map_context_row(row) for row in rows]


def search_context_by_vector(query: str, limit: int = 10) -> list[dict[str, Any]]:
    embedding = format_pgvector(build_local_embedding(query))

    with psycopg.connect(get_database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    source_path,
                    source_type,
                    data_classification,
                    source_hash,
                    redacted,
                    ingest_allowed,
                    retention_policy,
                    created_by,
                    created_at::text,
                    left(content, 500) as content_preview,
                    embedding <=> %s::vector as vector_distance
                from context_chunks
                where embedding is not null
                  and ingest_allowed = true
                order by embedding <=> %s::vector, created_at desc
                limit %s
                """,
                (embedding, embedding, limit),
            )
            rows = cur.fetchall()

    return [map_context_row(row) for row in rows]


def search_context(query: str, limit: int = 10, mode: str = "keyword") -> list[dict[str, Any]]:
    if mode == "keyword":
        return search_context_by_keyword(query, limit)

    if mode == "vector":
        return search_context_by_vector(query, limit)

    raise ValueError(f"unsupported search mode: {mode}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search context_chunks by keyword.")
    parser.add_argument("query", help="Keyword to search in content or source_path.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum rows to return.")
    parser.add_argument(
        "--mode",
        choices=["keyword", "vector"],
        default="keyword",
        help="Search mode. keyword keeps the existing ILIKE behavior; vector uses pgvector.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results = search_context(args.query, args.limit, args.mode)
    payload = {
        "query": args.query,
        "mode": args.mode,
        "count": len(results),
        "results": results,
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv

try:
    from scripts import data_boundary_check
except ModuleNotFoundError:
    import data_boundary_check

ROOT = Path(__file__).resolve().parents[1]


def get_database_url() -> str:
    load_dotenv()

    return os.getenv(
        "DATABASE_URL",
        "postgresql://chao:chao_dev_password@localhost:5432/chao",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def classify_source(path: str) -> tuple[str, str, bool]:
    normalized = data_boundary_check.normalize_repo_path(path)

    if normalized in {"README.md", "CHANGELOG-v3.md"}:
        return "documentation", "D0", False

    if normalized == "AGENTS.md":
        return "agent_rule", "D1", True

    if normalized.startswith(".ai-agents/records/tasks/TASK-"):
        return "historian_summary", "D1", True

    if normalized.startswith(".ai-agents/"):
        return "agent_rule", "D1", True

    return "documentation", "D1", True


def build_candidate(root: Path, repo_path: str) -> dict[str, Any]:
    source_type, classification, redacted = classify_source(repo_path)
    absolute_path = root / repo_path
    content = absolute_path.read_text(encoding="utf-8")

    return {
        "source_uri": repo_path,
        "source_path": repo_path,
        "source_hash": sha256_file(absolute_path),
        "source_type": source_type,
        "data_classification": classification,
        "redacted": redacted,
        "ingest_allowed": True,
        "retention_policy": "project_default",
        "created_by": "ingest_markdown",
        "content": content,
    }


def extract_task_code(source_path: str) -> str | None:
    normalized = data_boundary_check.normalize_repo_path(source_path)
    prefix = ".ai-agents/records/tasks/"

    if not normalized.startswith(prefix):
        return None

    filename = Path(normalized).name

    if not filename.startswith("TASK-") or not filename.endswith(".md"):
        return None

    return filename.removesuffix(".md")


def build_data_asset_record(candidate: dict[str, Any], task_id: str | None) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "asset_name": candidate["source_path"],
        "asset_type": "context_chunk_source",
        "classification": candidate["data_classification"],
        "primary_storage": "Git / Markdown",
        "allowed_copies": ["PostgreSQL", "pgvector"],
        "forbidden_storages": ["Secret Manager", "logs", "unapproved artifact"],
        "allow_vectorization": candidate["ingest_allowed"],
        "desensitized": candidate["redacted"],
        "retention_days": 3650,
        "owner": "historian",
        "notes": f"source_hash={candidate['source_hash']}; source_type={candidate['source_type']}",
    }


def collect_candidates(
    root: Path,
    tracked_files: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    candidates = []
    rejected = []

    for repo_path in tracked_files:
        normalized = data_boundary_check.normalize_repo_path(repo_path)

        if data_boundary_check.is_forbidden_ingest_path(normalized):
            rejected.append(
                {
                    "source_uri": normalized,
                    "reason": "forbidden_path",
                }
            )
            continue

        if not data_boundary_check.is_allowed_ingest_source(normalized):
            continue

        absolute_path = root / normalized

        if not absolute_path.is_file():
            rejected.append(
                {
                    "source_uri": normalized,
                    "reason": "missing_file",
                }
            )
            continue

        try:
            content = absolute_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            rejected.append(
                {
                    "source_uri": normalized,
                    "reason": "decode_error",
                }
            )
            continue

        if data_boundary_check.contains_secret_pattern(content):
            rejected.append(
                {
                    "source_uri": normalized,
                    "reason": "secret_pattern",
                }
            )
            continue

        candidates.append(build_candidate(root, normalized))

    return candidates, rejected


def build_dry_run_report(root: Path, tracked_files: list[str]) -> dict[str, Any]:
    candidates, rejected = collect_candidates(root, tracked_files)
    return build_report("dry_run", candidates, rejected)


def summarize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in candidate.items() if key != "content"}


def build_report(
    mode: str,
    candidates: list[dict[str, Any]],
    rejected: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "mode": mode,
        "candidate_count": len(candidates),
        "rejected_count": len(rejected),
        "candidates": [summarize_candidate(candidate) for candidate in candidates],
        "rejected": rejected,
    }


def find_task_id(cur: Any, source_path: str) -> str | None:
    task_code = extract_task_code(source_path)

    if task_code is None:
        return None

    cur.execute(
        """
        select id::text
        from tasks
        where task_code = %s
        """,
        (task_code,),
    )
    row = cur.fetchone()

    if row is None:
        return None

    return row[0]


def write_ingest_results(candidates: list[dict[str, Any]]) -> tuple[int, int, int]:
    written_count = 0
    data_asset_count = 0
    skipped_count = 0

    with psycopg.connect(get_database_url()) as conn:
        with conn.cursor() as cur:
            for candidate in candidates:
                task_code = extract_task_code(candidate["source_path"])
                task_id = find_task_id(cur, candidate["source_path"])

                if task_code is not None and task_id is None:
                    cur.execute(
                        """
                        delete from context_chunks
                        where source_path = %s
                        """,
                        (candidate["source_path"],),
                    )
                    cur.execute(
                        """
                        delete from data_assets
                        where asset_name = %s
                          and asset_type = %s
                        """,
                        (candidate["source_path"], "context_chunk_source"),
                    )
                    skipped_count += 1
                    continue

                cur.execute(
                    """
                    delete from context_chunks
                    where source_path = %s
                    """,
                    (candidate["source_path"],),
                )
                cur.execute(
                    """
                    insert into context_chunks (
                        id,
                        source_path,
                        source_type,
                        source_hash,
                        data_classification,
                        redacted,
                        ingest_allowed,
                        retention_policy,
                        created_by,
                        content
                    )
                    values (
                        gen_random_uuid(),
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        candidate["source_path"],
                        candidate["source_type"],
                        candidate["source_hash"],
                        candidate["data_classification"],
                        candidate["redacted"],
                        candidate["ingest_allowed"],
                        candidate["retention_policy"],
                        candidate["created_by"],
                        candidate["content"],
                    ),
                )
                written_count += 1

                data_asset = build_data_asset_record(candidate, task_id)
                cur.execute(
                    """
                    delete from data_assets
                    where asset_name = %s
                      and asset_type = %s
                    """,
                    (data_asset["asset_name"], data_asset["asset_type"]),
                )
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
                    values (
                        gen_random_uuid(),
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        data_asset["task_id"],
                        data_asset["asset_name"],
                        data_asset["asset_type"],
                        data_asset["classification"],
                        data_asset["primary_storage"],
                        data_asset["allowed_copies"],
                        data_asset["forbidden_storages"],
                        data_asset["allow_vectorization"],
                        data_asset["desensitized"],
                        data_asset["retention_days"],
                        data_asset["owner"],
                        data_asset["notes"],
                    ),
                )
                data_asset_count += 1

        conn.commit()

    return written_count, data_asset_count, skipped_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest markdown context candidates.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write candidates to context_chunks. Defaults to dry-run.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tracked_files = data_boundary_check.get_tracked_files()
    candidates, rejected = collect_candidates(ROOT, tracked_files)
    report = build_report("dry_run", candidates, rejected)

    if args.write:
        written_count, data_asset_count, skipped_count = write_ingest_results(candidates)
        report = {
            **build_report("write", candidates, rejected),
            "mode": "write",
            "written_count": written_count,
            "data_asset_count": data_asset_count,
            "skipped_count": skipped_count,
        }

    print(json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

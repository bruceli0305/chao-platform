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


def write_context_chunks(candidates: list[dict[str, Any]]) -> int:
    with psycopg.connect(get_database_url()) as conn:
        with conn.cursor() as cur:
            for candidate in candidates:
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

        conn.commit()

    return len(candidates)


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
        written_count = write_context_chunks(candidates)
        report = {
            **build_report("write", candidates, rejected),
            "mode": "write",
            "written_count": written_count,
        }

    print(json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

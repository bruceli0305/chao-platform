import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import data_boundary_check


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

    return {
        "source_uri": repo_path,
        "source_hash": sha256_file(absolute_path),
        "source_type": source_type,
        "data_classification": classification,
        "redacted": redacted,
        "ingest_allowed": True,
        "retention_policy": "project_default",
        "created_by": "ingest_markdown_dry_run",
    }


def build_dry_run_report(root: Path, tracked_files: list[str]) -> dict[str, Any]:
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

    return {
        "mode": "dry_run",
        "candidate_count": len(candidates),
        "rejected_count": len(rejected),
        "candidates": candidates,
        "rejected": rejected,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run markdown ingest candidates.")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tracked_files = data_boundary_check.get_tracked_files()
    report = build_dry_run_report(ROOT, tracked_files)

    print(json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

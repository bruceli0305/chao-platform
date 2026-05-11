import json
import os
import sys
from pathlib import Path
from typing import Any

from app.chao.services.events import record_task_event
from app.chao.services.github_links import record_github_link
from app.chao.services.historian_records import record_historian_record
from app.chao.services.store import get_task_detail
from scripts.check_pr_task_binding import extract_task_codes


def load_event(path: str | None) -> dict[str, Any]:
    if not path:
        return {}

    event_path = Path(path)

    if not event_path.is_file():
        return {}

    return json.loads(event_path.read_text(encoding="utf-8"))


def build_repo_url(env: dict[str, str]) -> str | None:
    repository = env.get("GITHUB_REPOSITORY")

    if not repository:
        return None

    server_url = env.get("GITHUB_SERVER_URL", "https://github.com")
    return f"{server_url}/{repository}"


def extract_task_code(event: dict[str, Any]) -> str | None:
    pull_request = event.get("pull_request")

    if pull_request:
        task_codes = extract_task_codes(pull_request.get("body") or "")
        return task_codes[0] if task_codes else None

    candidate_text = "\n".join(
        [
            event.get("head_commit", {}).get("message") or "",
            *[commit.get("message") or "" for commit in event.get("commits", [])],
        ]
    )
    task_codes = extract_task_codes(candidate_text)

    return task_codes[0] if task_codes else None


def build_delivery_links(event: dict[str, Any], env: dict[str, str]) -> list[dict[str, Any]]:
    links = []
    repo_url = build_repo_url(env)
    pull_request = event.get("pull_request")

    if pull_request:
        state = "merged" if pull_request.get("merged") else pull_request.get("state")
        links.append(
            {
                "link_type": "pull_request",
                "external_id": str(pull_request["number"]),
                "url": pull_request["html_url"],
                "title": pull_request.get("title"),
                "status": state,
                "metadata": {
                    "base_ref": pull_request.get("base", {}).get("ref"),
                    "head_ref": pull_request.get("head", {}).get("ref"),
                },
            }
        )

    commit_sha = env.get("GITHUB_SHA") or event.get("after")

    if repo_url and commit_sha:
        links.append(
            {
                "link_type": "commit",
                "external_id": commit_sha,
                "url": f"{repo_url}/commit/{commit_sha}",
                "title": "GitHub commit",
                "status": "recorded",
                "metadata": {"ref": env.get("GITHUB_REF")},
            }
        )

    run_id = env.get("GITHUB_RUN_ID")

    if repo_url and run_id:
        links.append(
            {
                "link_type": "ci_run",
                "external_id": run_id,
                "url": f"{repo_url}/actions/runs/{run_id}",
                "title": "GitHub Actions run",
                "status": env.get("GITHUB_JOB", "recorded"),
                "metadata": {"workflow": env.get("GITHUB_WORKFLOW")},
            }
        )

    return links


def record_delivery_context(
    *,
    task_code: str,
    links: list[dict[str, Any]],
    created_by: str,
    allow_missing_task: bool = False,
) -> bool:
    task = get_task_detail(task_code)

    if task is None:
        if allow_missing_task:
            print(f"GitHub delivery record skipped: task not found: {task_code}")
            return False
        raise ValueError(f"Task not found: {task_code}")

    for link in links:
        record_github_link(
            task_id=task["id"],
            link_type=link["link_type"],
            external_id=link["external_id"],
            url=link["url"],
            title=link.get("title"),
            status=link.get("status"),
            metadata=link.get("metadata"),
            created_by=created_by,
        )

    summary = f"GitHub delivery context recorded for {task_code}: {len(links)} link(s)."
    record_historian_record(
        task_id=task["id"],
        record_type="github_delivery",
        content=summary,
        source="github-actions",
        created_by=created_by,
    )
    record_task_event(
        task_id=task["id"],
        event_type="github_delivery_recorded",
        from_status=task["status"],
        to_status=task["status"],
        summary=summary,
        created_by=created_by,
    )

    print(summary)
    return True


def main() -> int:
    event = load_event(os.getenv("GITHUB_EVENT_PATH"))
    task_code = os.getenv("CHAO_TASK_CODE") or extract_task_code(event)

    if not task_code:
        print("GitHub delivery record skipped: no Task Code found")
        return 0

    links = build_delivery_links(event, dict(os.environ))

    if not links:
        print("GitHub delivery record skipped: no GitHub links found")
        return 0

    record_delivery_context(
        task_code=task_code,
        links=links,
        created_by=os.getenv("GITHUB_ACTOR", "github-actions"),
        allow_missing_task=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

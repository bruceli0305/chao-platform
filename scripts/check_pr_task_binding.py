import json
import os
import re
import sys
from pathlib import Path
from typing import Any

TASK_CODE_PATTERN = re.compile(r"\bTASK-\d{8}-\d{6}(?:-\d{6})?\b")


def extract_task_codes(text: str) -> list[str]:
    return TASK_CODE_PATTERN.findall(text)


def load_event(path: str | None) -> dict[str, Any]:
    if not path:
        return {}

    event_path = Path(path)

    if not event_path.is_file():
        return {}

    return json.loads(event_path.read_text(encoding="utf-8"))


def check_pull_request_body(event: dict[str, Any]) -> list[str]:
    body = event.get("pull_request", {}).get("body") or ""
    task_codes = extract_task_codes(body)

    if task_codes:
        return []

    return ["PR description must include a valid Task Code, for example TASK-20260511-120000."]


def main() -> int:
    event_name = os.getenv("GITHUB_EVENT_NAME", "")

    if event_name != "pull_request":
        print("PR task binding check skipped: not a pull_request event")
        return 0

    event = load_event(os.getenv("GITHUB_EVENT_PATH"))
    errors = check_pull_request_body(event)

    if errors:
        print("PR task binding check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PR task binding check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

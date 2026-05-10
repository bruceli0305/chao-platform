import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK_RECORDS_DIR = ROOT / ".ai-agents" / "records" / "tasks"


FORBIDDEN_TRACKED_PATHS = [
    ".env",
    "data/postgres",
    "logs",
    ".venv",
]

REQUIRED_GITIGNORE_ENTRIES = [
    ".env",
    ".venv",
    "data/",
    "logs/",
    "__pycache__/",
    "*.pyc",
]

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(api_key|apikey|secret|token|password)\s*=\s*['\"][^'\"]{8,}['\"]"),
]

SCAN_SUFFIXES = {
    ".py",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".json",
    ".sql",
    ".sh",
    ".txt",
}

IGNORED_DIRS = {
    ".git",
    ".venv",
    "data",
    "logs",
    "__pycache__",
    ".pytest_cache",
}


def run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout


def get_tracked_files() -> list[str]:
    output = run_git(["ls-files"])
    return [line.strip() for line in output.splitlines() if line.strip()]


def check_forbidden_tracked_paths(tracked_files: list[str]) -> list[str]:
    errors = []

    for tracked in tracked_files:
        for forbidden in FORBIDDEN_TRACKED_PATHS:
            if tracked == forbidden or tracked.startswith(forbidden.rstrip("/") + "/"):
                errors.append(f"禁止被 Git 跟踪的路径：{tracked}")

    return errors


def check_gitignore() -> list[str]:
    errors = []
    gitignore_path = ROOT / ".gitignore"

    if not gitignore_path.exists():
        return ["缺少 .gitignore 文件"]

    content = gitignore_path.read_text(encoding="utf-8")

    for entry in REQUIRED_GITIGNORE_ENTRIES:
        if entry not in content:
            errors.append(f".gitignore 缺少必要项：{entry}")

    return errors


def should_scan(path: Path) -> bool:
    relative_parts = path.relative_to(ROOT).parts

    if any(part in IGNORED_DIRS for part in relative_parts):
        return False

    if is_task_markdown_record(path):
        return False

    if path.suffix not in SCAN_SUFFIXES:
        return False

    return path.is_file()


def is_task_markdown_record(path: Path) -> bool:
    try:
        path.relative_to(TASK_RECORDS_DIR)
    except ValueError:
        return False

    return path.is_file() and path.name.startswith("TASK-") and path.suffix == ".md"


def contains_secret_pattern(content: str) -> bool:
    return any(pattern.search(content) for pattern in SECRET_PATTERNS)


def check_secret_patterns() -> list[str]:
    errors = []

    for path in ROOT.rglob("*"):
        if not should_scan(path):
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        if contains_secret_pattern(content):
            errors.append(f"疑似敏感信息：{path.relative_to(ROOT)}")

    return errors


def check_task_markdown_records() -> list[str]:
    errors = []

    if not TASK_RECORDS_DIR.exists():
        return errors

    for path in TASK_RECORDS_DIR.glob("TASK-*.md"):
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        if contains_secret_pattern(content):
            errors.append(f"史官任务记录疑似敏感信息：{path.relative_to(ROOT)}")

    return errors


def main() -> int:
    errors = []

    tracked_files = get_tracked_files()

    errors.extend(check_forbidden_tracked_paths(tracked_files))
    errors.extend(check_gitignore())
    errors.extend(check_secret_patterns())
    errors.extend(check_task_markdown_records())

    if errors:
        print("data-boundary check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("data-boundary check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

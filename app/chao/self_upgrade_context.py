import re
from pathlib import Path

from app.chao.runner_policy import normalize_repo_path


SELF_UPGRADE_SOURCE_CONTEXT_PATHS = [
    "app/chao/web_console.py",
]

MAX_INLINE_SOURCE_CONTEXT_CHARS = 24000
MAX_EXTRACTED_CONTEXT_CHARS = 60000

_TEXT_BETWEEN_TAGS_PATTERN = re.compile(r">[^<{}`]*[A-Za-z][^<{}`]*<")
_PLACEHOLDER_PATTERN = re.compile(r"placeholder=\"[^\"]*[A-Za-z][^\"]*\"")
_ARIA_LABEL_PATTERN = re.compile(r"aria-label=\"[^\"]*[A-Za-z][^\"]*\"")
_JS_LABEL_PATTERN = re.compile(r"\blabel:\s*\"[^\"]*[A-Za-z][^\"]*\"")
_TITLE_PATTERN = re.compile(r"<title>[^<]*[A-Za-z][^<]*</title>")
_OPTION_PATTERN = re.compile(r"<option[^>]*>[^<]*[A-Za-z][^<]*</option>")
_ANCHOR_TEXT_PATTERN = re.compile(r"<a[^>]*>[^<]*[A-Za-z][^<]*</a>")
_BUTTON_TEXT_PATTERN = re.compile(r"^\s*[A-Z][A-Za-z0-9 /_-]{1,40}\s*$")
_USER_VISIBLE_HINT_PATTERN = re.compile(
    r"(renderNotice|renderPanelError|textContent|placeholder|<h[1-6]|<label|<button|<th|<td|<option|<title|aria-label|label:)"
)


class SourceContextResult(dict):
    path: str
    mode: str
    content: str


def build_self_upgrade_source_context(user_request: str) -> str:
    blocks: list[str] = []

    for path in SELF_UPGRADE_SOURCE_CONTEXT_PATHS:
        if path not in user_request:
            continue

        normalized_path = normalize_repo_path(path)
        source_path = Path(normalized_path)
        if not source_path.is_file():
            blocks.append(
                "## Source File Context\n"
                f"### {normalized_path}\n"
                "Source file was requested but could not be found in the workspace."
            )
            continue

        content = source_path.read_text(encoding="utf-8")
        if len(content) <= MAX_INLINE_SOURCE_CONTEXT_CHARS:
            blocks.append(_format_inline_source_context(normalized_path, content))
        else:
            blocks.append(_format_extracted_source_context(normalized_path, content))

    return "\n\n".join(blocks)


def _format_inline_source_context(path: str, content: str) -> str:
    return (
        "## Source File Context\n"
        f"### {path}\n"
        "The following complete source file content is provided so old_text values can be exact.\n"
        "```python\n"
        f"{content}\n"
        "```"
    )


def _format_extracted_source_context(path: str, content: str) -> str:
    candidates = extract_user_visible_text_candidates(content)
    candidate_blocks: list[str] = []
    total_chars = 0

    for index, candidate in enumerate(candidates, start=1):
        block = (
            f"### Candidate {index:03d}: {path}:{candidate['start_line']}-{candidate['end_line']}\n"
            "Use this exact old_text block if this visible text should change:\n"
            "```text\n"
            f"{candidate['old_text']}\n"
            "```"
        )
        if total_chars + len(block) > MAX_EXTRACTED_CONTEXT_CHARS:
            break
        candidate_blocks.append(block)
        total_chars += len(block)

    return (
        "## Source File Context\n"
        f"### {path}\n"
        "The file is large, so the complete source is not included. Instead, the local runner extracted candidate user-visible text units.\n"
        "For this task, treat the candidates below as the allowed replacement surface.\n"
        "Use old_text exactly as one full candidate block, including indentation and surrounding syntax.\n"
        "Do not use only a repeated label such as Task, Title, Status, or Owner as old_text.\n\n"
        + "\n\n".join(candidate_blocks)
    )


def extract_user_visible_text_candidates(content: str) -> list[dict[str, object]]:
    lines = content.splitlines()
    candidates: list[dict[str, object]] = []
    seen: set[str] = set()

    for line_number, line in enumerate(lines, start=1):
        if not _line_may_contain_user_visible_text(line):
            continue

        old_text = line.rstrip()
        if not old_text or old_text in seen:
            continue

        seen.add(old_text)
        candidates.append(
            {
                "start_line": line_number,
                "end_line": line_number,
                "old_text": old_text,
            }
        )

    return candidates


def _line_may_contain_user_visible_text(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("//") or stripped.startswith("#"):
        return False
    if not re.search(r"[A-Za-z]", stripped):
        return False
    if not _USER_VISIBLE_HINT_PATTERN.search(stripped):
        return False

    return any(
        pattern.search(stripped)
        for pattern in [
            _TEXT_BETWEEN_TAGS_PATTERN,
            _PLACEHOLDER_PATTERN,
            _ARIA_LABEL_PATTERN,
            _JS_LABEL_PATTERN,
            _TITLE_PATTERN,
            _OPTION_PATTERN,
            _ANCHOR_TEXT_PATTERN,
        ]
    ) or _BUTTON_TEXT_PATTERN.match(stripped) is not None

import re
from pathlib import Path

from app.chao.runner_policy import normalize_repo_path


SELF_UPGRADE_SOURCE_CONTEXT_PATHS = [
    "app/chao/web_console.py",
]

MAX_INLINE_SOURCE_CONTEXT_CHARS = 24000
MAX_EXTRACTED_CONTEXT_CHARS = 60000

_TEXT_BETWEEN_TAGS_PATTERN = re.compile(r">([^<{}`]*[A-Za-z][^<{}`]*)<")
_PLACEHOLDER_PATTERN = re.compile(r"placeholder=\"([^\"]*[A-Za-z][^\"]*)\"")
_ARIA_LABEL_PATTERN = re.compile(r"aria-label=\"([^\"]*[A-Za-z][^\"]*)\"")
_JS_LABEL_PATTERN = re.compile(r"\blabel:\s*\"([^\"]*[A-Za-z][^\"]*)\"")
_TITLE_PATTERN = re.compile(r"<title>([^<]*[A-Za-z][^<]*)</title>")
_OPTION_PATTERN = re.compile(r"(<option[^>]*>)([^<]*[A-Za-z][^<]*)(</option>)")
_ANCHOR_TEXT_PATTERN = re.compile(r"(<a[^>]*>)([^<]*[A-Za-z][^<]*)(</a>)")
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


def resolve_candidate_patch(
    path: str,
    candidate_id: str,
    translated_text: str,
) -> dict[str, str]:
    normalized_path = normalize_repo_path(path)
    source_path = Path(normalized_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"self-upgrade candidate source not found: {normalized_path}")

    candidate = _find_candidate(source_path, candidate_id)
    old_text = str(candidate["old_text"])
    new_text = build_candidate_replacement(old_text, translated_text)

    return {
        "path": normalized_path,
        "old_text": old_text,
        "new_text": new_text,
    }


def build_candidate_replacement(old_text: str, translated_text: str) -> str:
    translated = translated_text.strip()
    if not translated:
        raise ValueError("candidate translated_text cannot be empty")

    replacements = [
        (_PLACEHOLDER_PATTERN, 'placeholder="{}"'),
        (_ARIA_LABEL_PATTERN, 'aria-label="{}"'),
        (_JS_LABEL_PATTERN, 'label: "{}"'),
    ]
    for pattern, template in replacements:
        match = pattern.search(old_text)
        if match:
            start, end = match.span(1)
            return old_text[:start] + translated + old_text[end:]

    title_match = _TITLE_PATTERN.search(old_text)
    if title_match:
        start, end = title_match.span(1)
        return old_text[:start] + translated + old_text[end:]

    for pattern in [_OPTION_PATTERN, _ANCHOR_TEXT_PATTERN]:
        match = pattern.search(old_text)
        if match:
            start, end = match.span(2)
            return old_text[:start] + translated + old_text[end:]

    tag_match = _TEXT_BETWEEN_TAGS_PATTERN.search(old_text)
    if tag_match:
        start, end = tag_match.span(1)
        return old_text[:start] + translated + old_text[end:]

    if _BUTTON_TEXT_PATTERN.match(old_text.strip()):
        prefix_len = len(old_text) - len(old_text.lstrip())
        suffix_len = len(old_text) - len(old_text.rstrip())
        return old_text[:prefix_len] + translated + (old_text[len(old_text) - suffix_len :] if suffix_len else "")

    raise ValueError("candidate old_text does not contain a supported visible text segment")


def _find_candidate(source_path: Path, candidate_id: str) -> dict[str, object]:
    normalized_id = candidate_id.strip().lstrip("#")
    if not normalized_id.isdigit():
        raise ValueError(f"candidate_id must be a number-like value: {candidate_id}")

    index = int(normalized_id)
    if index <= 0:
        raise ValueError(f"candidate_id must be positive: {candidate_id}")

    content = source_path.read_text(encoding="utf-8")
    candidates = extract_user_visible_text_candidates(content)
    if index > len(candidates):
        raise ValueError(
            f"candidate_id out of range for {source_path}: {candidate_id}; total={len(candidates)}"
        )

    return candidates[index - 1]


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
            f"visible_text: {candidate['visible_text']}\n"
            "To change this text, return an operation using candidate_id and translated_text.\n"
            "Example operation shape: {\"path\": \"app/chao/web_console.py\", \"candidate_id\": \"001\", \"translated_text\": \"中文译文\"}\n"
        )
        if total_chars + len(block) > MAX_EXTRACTED_CONTEXT_CHARS:
            break
        candidate_blocks.append(block)
        total_chars += len(block)

    return (
        "## Source File Context\n"
        f"### {path}\n"
        "The file is large, so the complete source is not included. Instead, the local runner extracted candidate user-visible text units.\n"
        "For this task, use candidate_id plus translated_text instead of copying HTML or JavaScript lines into old_text.\n"
        "Do not output old_text for candidates in this extracted context.\n\n"
        + "\n\n".join(candidate_blocks)
    )


def extract_user_visible_text_candidates(content: str) -> list[dict[str, object]]:
    lines = content.splitlines()
    candidates: list[dict[str, object]] = []
    seen: set[str] = set()

    for line_number, line in enumerate(lines, start=1):
        visible_text = _extract_visible_text(line)
        if not visible_text:
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
                "visible_text": visible_text,
            }
        )

    return candidates


def _extract_visible_text(line: str) -> str | None:
    stripped = line.strip()
    if not _line_may_contain_user_visible_text(line):
        return None

    for pattern in [
        _PLACEHOLDER_PATTERN,
        _ARIA_LABEL_PATTERN,
        _JS_LABEL_PATTERN,
        _TITLE_PATTERN,
    ]:
        match = pattern.search(stripped)
        if match:
            return match.group(1).strip()

    for pattern in [_OPTION_PATTERN, _ANCHOR_TEXT_PATTERN]:
        match = pattern.search(stripped)
        if match:
            return match.group(2).strip()

    tag_match = _TEXT_BETWEEN_TAGS_PATTERN.search(stripped)
    if tag_match:
        return tag_match.group(1).strip()

    if _BUTTON_TEXT_PATTERN.match(stripped):
        return stripped

    return None


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

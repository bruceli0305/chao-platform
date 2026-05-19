import json
import re
from typing import Any

DEFAULT_CONTEXT_LIMIT = 6000
SECRET_REPLACEMENT = "<redacted-secret>"

SECRET_PATTERNS = [
    re.compile(
        r"-----BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----.*?-----END .*?PRIVATE KEY-----",
        re.DOTALL,
    ),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(api_key|apikey|secret|token|password)\s*=\s*['\"][^'\"]{8,}['\"]"),
]


def redact_sensitive_text(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub(SECRET_REPLACEMENT, redacted)
    return redacted


def build_llm_task_prompt(
    task: dict[str, Any],
    user_prompt: str,
    *,
    context_limit: int = DEFAULT_CONTEXT_LIMIT,
) -> str:
    context = build_llm_task_context(task, context_limit=context_limit)
    redacted_prompt = redact_sensitive_text(user_prompt)

    return (
        "You are assisting with a Chao task. Use the task context below when answering.\n"
        "Do not infer or reveal secrets. If context is insufficient, say what is missing.\n\n"
        "## Task Context\n"
        f"{context}\n\n"
        "## User Request\n"
        f"{redacted_prompt}"
    )


def build_llm_task_context(
    task: dict[str, Any],
    *,
    context_limit: int = DEFAULT_CONTEXT_LIMIT,
) -> str:
    sections = [
        _format_basic_task(task),
        _format_route(task.get("route_result") or {}),
        _format_records("Events", task.get("events") or [], _format_event, limit=8),
        _format_records("Artifacts", task.get("artifacts") or [], _format_artifact, limit=8),
        _format_records("Data Assets", task.get("data_assets") or [], _format_data_asset, limit=8),
        _format_records(
            "Gate Results", task.get("gate_results") or [], _format_gate_result, limit=8
        ),
        _format_records(
            "GitHub Links", task.get("github_links") or [], _format_github_link, limit=8
        ),
        _format_records(
            "Historian Records",
            task.get("historian_records") or [],
            _format_historian_record,
            limit=5,
        ),
    ]
    context = "\n\n".join(section for section in sections if section)
    context = redact_sensitive_text(context)

    if len(context) <= context_limit:
        return context

    return context[: context_limit - 32].rstrip() + "\n[context truncated]"


def _format_basic_task(task: dict[str, Any]) -> str:
    fields = [
        ("task_code", task.get("task_code")),
        ("title", task.get("title")),
        ("task_level", task.get("task_level")),
        ("status", task.get("status")),
        ("owner", task.get("owner")),
        ("raw_request", task.get("raw_request")),
    ]
    lines = ["### Basic"]
    for key, value in fields:
        if value is not None:
            lines.append(f"- {key}: {_stringify(value)}")
    return "\n".join(lines)


def _format_route(route_result: dict[str, Any]) -> str:
    if not route_result:
        return ""

    allowed_keys = [
        "task_level",
        "risk_level",
        "required_confirmation",
        "required_roles",
        "required_gates",
        "required_skills",
        "reason",
    ]
    lines = ["### Route"]
    for key in allowed_keys:
        if key in route_result:
            lines.append(f"- {key}: {_stringify(route_result[key])}")
    return "\n".join(lines)


def _format_records(
    title: str,
    records: list[dict[str, Any]],
    formatter: Any,
    *,
    limit: int,
) -> str:
    if not records:
        return ""

    lines = [f"### {title}"]
    for record in records[:limit]:
        lines.append(f"- {formatter(record)}")
    if len(records) > limit:
        lines.append(f"- ... {len(records) - limit} more")
    return "\n".join(lines)


def _format_event(record: dict[str, Any]) -> str:
    return (
        f"{record.get('event_type', '')}: "
        f"{record.get('from_status', '')} -> {record.get('to_status', '')}; "
        f"{record.get('summary', '')}"
    )


def _format_artifact(record: dict[str, Any]) -> str:
    return (
        f"{record.get('artifact_type', '')}: "
        f"{record.get('artifact_uri', '')}; access={record.get('access_level', '')}"
    )


def _format_data_asset(record: dict[str, Any]) -> str:
    return (
        f"{record.get('asset_type', '')}: "
        f"class={record.get('classification', '')}; "
        f"owner={record.get('owner', '')}; storage={record.get('primary_storage', '')}"
    )


def _format_gate_result(record: dict[str, Any]) -> str:
    return (
        f"{record.get('gate_name', '')}: "
        f"{record.get('status', '')}; command={record.get('command', '')}"
    )


def _format_github_link(record: dict[str, Any]) -> str:
    return (
        f"{record.get('link_type', '')}: "
        f"{record.get('external_id', '')}; status={record.get('status', '')}; "
        f"url={record.get('url', '')}"
    )


def _format_historian_record(record: dict[str, Any]) -> str:
    return (
        f"{record.get('record_type', '')}: "
        f"{record.get('content', '')}; source={record.get('source', '')}"
    )


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)

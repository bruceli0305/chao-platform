import json
from typing import Any, TypedDict

from app.chao.llm_context import build_llm_task_prompt, redact_sensitive_text
from app.chao.runner_policy import normalize_repo_path, require_change_scope_allowed


class SelfUpgradePatchOperation(TypedDict):
    path: str
    old_text: str
    new_text: str


class SelfUpgradePlan(TypedDict):
    summary: str
    operations: list[SelfUpgradePatchOperation]
    validation_gates: list[str]
    commit_message: str


SELF_UPGRADE_SYSTEM_PROMPT = """You are the Chao self-upgrade planner.
Return JSON only. Do not wrap the JSON in markdown.
The JSON object must contain:
- summary: short implementation summary
- operations: array of controlled text replacements with path, old_text, new_text
- validation_gates: executable gates from lint, test, compile, build, typecheck,
  data_boundary_check, schema_check
- commit_message: concise git commit message

Rules:
- Use repository-relative paths only.
- old_text must be exact text that appears once in the target file.
- Do not include secrets, tokens, private keys, or production data.
- Do not modify forbidden paths such as .env, data/, logs/, .venv/, or __pycache__/.
- Prefer the smallest safe patch that satisfies the task.
"""

EXECUTABLE_SELF_UPGRADE_GATES = {
    "build",
    "compile",
    "data_boundary_check",
    "lint",
    "schema_check",
    "test",
    "typecheck",
}

DEFAULT_SELF_UPGRADE_GATES = ["lint", "test"]

SELF_UPGRADE_REPOSITORY_HINTS = """Repository patch hints:
- The Web Console homepage is built in app/chao/web_console.py by build_console_index_html().
- This repository does not use app/templates/index.html or a top-level templates/ directory.
- For homepage title or header text changes, use app/chao/web_console.py.
- The old_text must be exact text from that file.
"""


def build_self_upgrade_prompt(task: dict[str, Any], user_request: str) -> str:
    request = user_request.strip() or str(task.get("raw_request") or "")
    plan_contract = (
        "Produce a controlled patch plan for this task.\n"
        "Return only JSON with this exact shape:\n"
        "{\n"
        '  "summary": "what will change",\n'
        '  "operations": [\n'
        '    {"path": "app/example.py", "old_text": "exact old text", "new_text": "replacement"}\n'
        "  ],\n"
        '  "validation_gates": ["lint", "test"],\n'
        '  "commit_message": "type: concise summary"\n'
        "}\n"
        "If the task cannot be changed safely with exact text replacements, return operations "
        "as an empty array and explain why in summary."
    )
    return build_llm_task_prompt(
        task,
        f"{request}\n\n{SELF_UPGRADE_REPOSITORY_HINTS}\n{plan_contract}",
    )


def extract_llm_response_text(response: dict[str, Any] | None) -> str:
    if not response:
        raise ValueError("LLM response is empty")

    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            message = first_choice.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
            if isinstance(first_choice.get("text"), str):
                return first_choice["text"]

    content = response.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [
            part.get("text")
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
        if text_parts:
            return "\n".join(text_parts)

    raise ValueError("LLM response does not contain text content")


def parse_self_upgrade_plan(
    text: str,
    *,
    allow_unsupported_validation_gates: bool = False,
) -> SelfUpgradePlan:
    raw_plan = _load_json_object(text)
    summary = _optional_string(raw_plan.get("summary"), "Self-upgrade patch plan.")
    commit_message = _optional_string(
        raw_plan.get("commit_message"),
        "self-upgrade: apply controlled patch",
    )
    operations = _parse_operations(raw_plan.get("operations"))
    validation_gates = _parse_validation_gates(
        raw_plan.get("validation_gates"),
        allow_unsupported=allow_unsupported_validation_gates,
    )

    require_change_scope_allowed([operation["path"] for operation in operations])

    return {
        "summary": summary,
        "operations": operations,
        "validation_gates": validation_gates,
        "commit_message": commit_message,
    }


def _load_json_object(text: str) -> dict[str, Any]:
    candidate = _strip_markdown_fence(text).strip()
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"self-upgrade plan is not valid JSON: {exc.msg}") from exc

    if not isinstance(data, dict):
        raise ValueError("self-upgrade plan must be a JSON object")

    return data


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1])

    return stripped


def _optional_string(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return _reject_sensitive_text(value.strip())

    return fallback


def _parse_operations(value: object) -> list[SelfUpgradePatchOperation]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("self-upgrade operations must be a list")

    operations: list[SelfUpgradePatchOperation] = []
    for index, operation in enumerate(value, start=1):
        if not isinstance(operation, dict):
            raise ValueError(f"self-upgrade operation {index} must be an object")

        path = operation.get("path")
        old_text = operation.get("old_text")
        new_text = operation.get("new_text")

        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"self-upgrade operation {index} requires path")
        if not isinstance(old_text, str) or not old_text:
            raise ValueError(f"self-upgrade operation {index} requires old_text")
        if not isinstance(new_text, str):
            raise ValueError(f"self-upgrade operation {index} requires new_text")

        operations.append(
            {
                "path": normalize_repo_path(path),
                "old_text": _reject_sensitive_text(old_text),
                "new_text": _reject_sensitive_text(new_text),
            }
        )

    return operations


def _parse_validation_gates(
    value: object,
    *,
    allow_unsupported: bool = False,
) -> list[str]:
    if value is None:
        return list(DEFAULT_SELF_UPGRADE_GATES)
    if not isinstance(value, list):
        raise ValueError("self-upgrade validation_gates must be a list")

    gates: list[str] = []
    for gate in value:
        if not isinstance(gate, str) or not gate.strip():
            raise ValueError("self-upgrade validation_gates must contain strings")
        normalized_gate = gate.strip()
        if normalized_gate not in EXECUTABLE_SELF_UPGRADE_GATES:
            if allow_unsupported:
                continue
            raise ValueError(f"unsupported self-upgrade validation gate: {normalized_gate}")
        if normalized_gate not in gates:
            gates.append(normalized_gate)

    return gates or list(DEFAULT_SELF_UPGRADE_GATES)


def _reject_sensitive_text(value: str) -> str:
    if redact_sensitive_text(value) != value:
        raise ValueError("self-upgrade plan contains sensitive text")

    return value

from app.chao.llm_context import (
    build_llm_task_context,
    build_llm_task_prompt,
    redact_sensitive_text,
)


def test_build_llm_task_prompt_includes_task_context():
    task = {
        "task_code": "TASK-1",
        "title": "Add dashboard filters",
        "raw_request": "Filter console tasks by level and status.",
        "task_level": "L2",
        "status": "DELIVERED",
        "owner": "shangshu",
        "route_result": {
            "required_confirmation": "B",
            "required_gates": ["pytest"],
            "required_skills": ["frontend-feature"],
        },
        "events": [
            {
                "event_type": "task_created",
                "from_status": "RAW",
                "to_status": "DELIVERED",
                "summary": "Task delivered",
            }
        ],
    }

    prompt = build_llm_task_prompt(task, "summarize this task")

    assert "Add dashboard filters" in prompt
    assert "Filter console tasks by level and status." in prompt
    assert "summarize this task" in prompt
    assert "required_gates" in prompt


def test_build_llm_task_context_redacts_secret_like_values():
    secret_key = "api" + "_key"
    secret_value = "1234567890" + "abcdef"
    token_key = "to" + "ken"
    task = {
        "task_code": "TASK-1",
        "title": "Secret handling",
        "raw_request": f'{secret_key}="{secret_value}"',
        "historian_records": [
            {
                "record_type": "note",
                "content": f"{token_key}='{secret_value}'",
                "source": "test",
            }
        ],
    }

    context = build_llm_task_context(task)

    assert secret_value not in context
    assert "<redacted-secret>" in context


def test_redact_sensitive_text_handles_common_tokens():
    text = "github_pat_" + "a" * 24

    assert redact_sensitive_text(text) == "<redacted-secret>"


def test_build_llm_task_context_truncates_to_limit():
    task = {
        "task_code": "TASK-1",
        "title": "Long task",
        "raw_request": "x" * 1000,
    }

    context = build_llm_task_context(task, context_limit=120)

    assert len(context) <= 120
    assert "[context truncated]" in context

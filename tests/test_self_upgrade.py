import json

import pytest

from app.chao.self_upgrade import (
    build_self_upgrade_prompt,
    extract_llm_response_text,
    parse_self_upgrade_plan,
)


def test_parse_self_upgrade_plan_accepts_controlled_patch():
    plan = parse_self_upgrade_plan(
        json.dumps(
            {
                "summary": "Rename console heading.",
                "operations": [
                    {
                        "path": ".\\app\\chao\\demo.py",
                        "old_text": "old heading",
                        "new_text": "new heading",
                    }
                ],
                "validation_gates": ["lint", "test", "lint"],
                "commit_message": "self-upgrade: rename console heading",
            }
        )
    )

    assert plan == {
        "summary": "Rename console heading.",
        "operations": [
            {
                "path": "app/chao/demo.py",
                "old_text": "old heading",
                "new_text": "new heading",
            }
        ],
        "validation_gates": ["lint", "test"],
        "commit_message": "self-upgrade: rename console heading",
    }


def test_parse_self_upgrade_plan_rejects_forbidden_paths():
    with pytest.raises(PermissionError):
        parse_self_upgrade_plan(
            json.dumps(
                {
                    "operations": [
                        {
                            "path": ".env",
                            "old_text": "old",
                            "new_text": "new",
                        }
                    ],
                    "validation_gates": ["lint"],
                }
            )
        )


def test_parse_self_upgrade_plan_filters_manual_gate():
    plan = parse_self_upgrade_plan(
        json.dumps(
            {
                "operations": [],
                "validation_gates": ["manual_validation"],
            }
        )
    )

    assert plan["validation_gates"] == ["lint", "test"]


def test_parse_self_upgrade_plan_can_ignore_manual_gate_when_validation_is_skipped():
    plan = parse_self_upgrade_plan(
        json.dumps(
            {
                "operations": [],
                "validation_gates": ["manual_validation", "lint"],
            }
        ),
        allow_unsupported_validation_gates=True,
    )

    assert plan["validation_gates"] == ["lint"]


def test_extract_llm_response_text_supports_openai_compatible_shape():
    assert (
        extract_llm_response_text(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '{"operations": []}',
                        }
                    }
                ]
            }
        )
        == '{"operations": []}'
    )


def test_build_self_upgrade_prompt_redacts_user_request_secret():
    sensitive_request = "use " + "api" + "_" + "key" + "=" + repr("super-secret-value")

    prompt = build_self_upgrade_prompt(
        {
            "task_code": "TASK-1",
            "title": "Patch",
            "task_level": "L1",
            "status": "NEW",
            "raw_request": "Patch demo",
        },
        sensitive_request,
    )

    assert "super-secret-value" not in prompt
    assert "<redacted-secret>" in prompt


def test_build_self_upgrade_prompt_includes_repository_patch_hints():
    prompt = build_self_upgrade_prompt(
        {
            "task_code": "TASK-1",
            "title": "Patch homepage",
            "task_level": "L1",
            "status": "NEW",
            "raw_request": "把首页标题从系统管理改成项目管理",
        },
        "",
    )

    assert "app/chao/web_console.py" in prompt
    assert "build_console_index_html" in prompt
    assert "does not use app/templates/index.html" in prompt

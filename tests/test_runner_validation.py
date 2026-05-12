import pytest

from app.chao.runner_validation import (
    build_runner_validation_plan,
    build_runner_validation_result,
    require_runner_validation_success,
)


def test_build_runner_validation_plan_maps_known_gates_to_commands():
    plan = build_runner_validation_plan(["lint", "test", "manual_validation"])

    assert plan == [
        {
            "gate": "lint",
            "command": "uv run ruff check app tests main.py",
            "required": True,
        },
        {
            "gate": "test",
            "command": "uv run pytest -q",
            "required": True,
        },
        {
            "gate": "manual_validation",
            "command": "manual validation evidence required",
            "required": True,
        },
    ]


def test_runner_validation_result_is_deliverable_when_all_commands_pass():
    result = build_runner_validation_result(["lint", "test"])

    assert result["deliverable"] is True
    assert result["quality"] == "可交付"
    assert [item["exit_code"] for item in result["command_results"]] == [0, 0]


def test_runner_validation_result_blocks_failed_commands():
    result = build_runner_validation_result(
        ["lint", "test"],
        command_results=[
            {
                "gate": "lint",
                "command": "uv run ruff check app tests main.py",
                "status": "failed",
                "exit_code": 1,
                "output_summary": "lint failed",
            },
            {
                "gate": "test",
                "command": "uv run pytest -q",
                "status": "passed",
                "exit_code": 0,
                "output_summary": "tests passed",
            },
        ],
    )

    assert result["deliverable"] is False
    assert result["quality"] == "验证失败"

    with pytest.raises(PermissionError, match="lint"):
        require_runner_validation_success(result)

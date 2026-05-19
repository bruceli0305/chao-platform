from typer.testing import CliRunner

from app.chao import cli


def test_llm_chat_dry_run_records_tool_call(monkeypatch):
    calls = []
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "task_level": "L2",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "B"},
    }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(cli, "record_tool_call", lambda **kwargs: calls.append(kwargs))

    result = CliRunner().invoke(
        cli.app,
        [
            "llm-chat",
            "TASK-1",
            "summarize the task",
        ],
    )

    assert result.exit_code == 0
    assert calls[0]["tool_name"] == "llm.chat_completion"
    assert calls[0]["permission_policy"] == "llm-provider-chat-completion"
    assert calls[0]["result_status"] == "success"
    assert "summarize the task" not in calls[0]["arguments_summary"]


def test_llm_chat_denies_unapproved_role(monkeypatch):
    calls = []
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "task_level": "L2",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "B"},
    }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(cli, "record_tool_call", lambda **kwargs: calls.append(kwargs))

    result = CliRunner().invoke(
        cli.app,
        [
            "llm-chat",
            "TASK-1",
            "summarize the task",
            "--by",
            "gongbu",
        ],
    )

    assert result.exit_code == 1
    assert calls == []


def test_llm_chat_requires_existing_task(monkeypatch):
    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: None)

    result = CliRunner().invoke(
        cli.app,
        [
            "llm-chat",
            "TASK-404",
            "summarize the task",
        ],
    )

    assert result.exit_code == 1
    assert "Task not found" in result.output

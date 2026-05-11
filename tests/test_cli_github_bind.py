from typer.testing import CliRunner

from app.chao import cli


def test_bind_github_records_link_event_and_tool_call(monkeypatch):
    calls = {
        "links": [],
        "events": [],
        "tool_calls": [],
    }
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "task_level": "L2",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "B"},
        "github_links": [],
    }

    def fake_get_task_detail(task_code):
        assert task_code == "TASK-1"
        return task

    monkeypatch.setattr(cli, "get_task_detail", fake_get_task_detail)
    monkeypatch.setattr(
        cli,
        "record_github_link",
        lambda **kwargs: calls["links"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "record_task_event",
        lambda **kwargs: calls["events"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "record_tool_call",
        lambda **kwargs: calls["tool_calls"].append(kwargs),
    )

    result = CliRunner().invoke(
        cli.app,
        [
            "bind-github",
            "TASK-1",
            "pr",
            "42",
            "https://github.com/example/repo/pull/42",
            "--title",
            "Bind task",
            "--status",
            "open",
            "--by",
            "lee",
        ],
    )

    assert result.exit_code == 0
    assert calls["links"][0]["link_type"] == "pull_request"
    assert calls["links"][0]["external_id"] == "42"
    assert calls["events"][0]["event_type"] == "github_link_bound"
    assert calls["tool_calls"][0]["tool_name"] == "cli.bind_github"
    assert calls["tool_calls"][0]["permission_policy"] == "local-cli-github-link-bind"


def test_bind_github_rejects_missing_task(monkeypatch):
    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: None)

    result = CliRunner().invoke(
        cli.app,
        [
            "bind-github",
            "TASK-MISSING",
            "issue",
            "7",
            "https://github.com/example/repo/issues/7",
        ],
    )

    assert result.exit_code == 1
    assert "Task not found" in result.output

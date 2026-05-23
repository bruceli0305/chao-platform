import json

from typer.testing import CliRunner

from app.chao import cli
from app.chao.repositories import RepositoryConfig


def _task():
    return {
        "id": "task-1",
        "task_code": "TASK-1",
        "title": "Self upgrade demo",
        "raw_request": "Rename a heading.",
        "task_level": "L1",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "none"},
    }


def _repository_config():
    return RepositoryConfig(
        name="chao-platform",
        git_url="git@github.com:example/repo.git",
        default_branch="main",
        workspace_path=".",
        sandbox_root=".chao/sandboxes",
        branch_prefix="codex/",
        enabled=True,
    )


def _llm_result(*, dry_run: bool, response: dict | None = None):
    class Result:
        status = "dry_run" if dry_run else "success"
        error = None

        def __init__(self):
            self.dry_run = dry_run

        def to_safe_dict(self):
            return {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "status": self.status,
                "dry_run": self.dry_run,
                "request": {},
                "response": response,
                "error": None,
            }

    return Result()


def _plan_response():
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "summary": "Patch demo heading.",
                            "operations": [
                                {
                                    "path": "app/chao/demo.py",
                                    "old_text": "old",
                                    "new_text": "new",
                                }
                            ],
                            "validation_gates": ["lint"],
                            "commit_message": "self-upgrade: patch demo heading",
                        }
                    ),
                }
            }
        ]
    }


def test_self_upgrade_dry_run_records_llm_tool_call(monkeypatch):
    calls = []
    prompts = []

    def fake_execute(_config, prompt, **kwargs):
        prompts.append((prompt, kwargs))
        return _llm_result(dry_run=kwargs["dry_run"])

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: _task())
    monkeypatch.setattr(cli, "execute_llm_chat_completion", fake_execute)
    monkeypatch.setattr(cli, "record_tool_call", lambda **kwargs: calls.append(kwargs))

    result = CliRunner().invoke(cli.app, ["self-upgrade", "TASK-1", "rename title"])

    assert result.exit_code == 0
    assert calls[0]["tool_name"] == "llm.chat_completion"
    assert calls[0]["result_status"] == "success"
    assert "rename title" in prompts[0][0]
    assert prompts[0][1]["dry_run"] is True
    assert '"status": "dry_run"' in result.output


def test_self_upgrade_execute_plans_patch_without_applying(monkeypatch):
    calls = {"tool_calls": [], "events": [], "patches": []}

    def fake_patch(operations, **kwargs):
        calls["patches"].append((operations, kwargs))
        return {
            "summary": "Validated 1 controlled text patch operation(s).",
            "changed_files": ["app/chao/demo.py"],
            "operations": [],
            "applied": False,
            "dry_run": True,
        }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: _task())
    monkeypatch.setattr(cli, "get_repository_config", lambda _name=None: _repository_config())
    monkeypatch.setattr(
        cli,
        "execute_llm_chat_completion",
        lambda *_args, **_kwargs: _llm_result(dry_run=False, response=_plan_response()),
    )
    monkeypatch.setattr(cli, "apply_text_patch_operations", fake_patch)
    monkeypatch.setattr(
        cli,
        "record_tool_call",
        lambda **kwargs: calls["tool_calls"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "record_task_event",
        lambda **kwargs: calls["events"].append(kwargs),
    )

    result = CliRunner().invoke(cli.app, ["self-upgrade", "TASK-1", "--execute"])

    assert result.exit_code == 0
    assert [call["tool_name"] for call in calls["tool_calls"]] == [
        "llm.chat_completion",
        "cli.runner_patch",
    ]
    assert calls["events"][0]["event_type"] == "self_upgrade_patch_planned"
    assert calls["patches"][0][1]["dry_run"] is True
    assert '"status": "planned"' in result.output


def test_self_upgrade_apply_runs_preflight_and_validation(monkeypatch):
    calls = {
        "preflight": [],
        "tool_calls": [],
        "events": [],
        "validations": [],
    }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: _task())
    monkeypatch.setattr(cli, "get_repository_config", lambda _name=None: _repository_config())
    monkeypatch.setattr(
        cli,
        "execute_llm_chat_completion",
        lambda *_args, **_kwargs: _llm_result(dry_run=False, response=_plan_response()),
    )
    monkeypatch.setattr(
        cli,
        "_require_runner_repository_preflight",
        lambda *args, **kwargs: calls["preflight"].append((args, kwargs)),
    )
    monkeypatch.setattr(
        cli,
        "apply_text_patch_operations",
        lambda *_args, **kwargs: {
            "summary": "Applied 1 controlled text patch operation(s).",
            "changed_files": ["app/chao/demo.py"],
            "operations": [],
            "applied": not kwargs["dry_run"],
            "dry_run": kwargs["dry_run"],
        },
    )
    monkeypatch.setattr(
        cli,
        "execute_runner_validation_commands",
        lambda gates, **kwargs: (
            calls["validations"].append((gates, kwargs))
            or {
                "quality": "deliverable",
                "checks": gates,
                "plan": [],
                "command_results": [],
                "deliverable": True,
                "note": "passed",
            }
        ),
    )
    monkeypatch.setattr(
        cli,
        "record_tool_call",
        lambda **kwargs: calls["tool_calls"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "record_task_event",
        lambda **kwargs: calls["events"].append(kwargs),
    )

    result = CliRunner().invoke(
        cli.app,
        ["self-upgrade", "TASK-1", "--execute", "--apply"],
    )

    assert result.exit_code == 0
    assert calls["preflight"][0][0][2] == ["lint"]
    assert calls["validations"][0][0] == ["lint"]
    assert [call["tool_name"] for call in calls["tool_calls"]] == [
        "llm.chat_completion",
        "cli.runner_patch",
        "cli.runner_validate",
    ]
    assert '"status": "applied"' in result.output

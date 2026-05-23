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


def test_self_upgrade_branch_creates_runner_branch_before_patch(monkeypatch):
    calls = {
        "preflight": [],
        "branch_plans": [],
        "branch_results": [],
        "tool_calls": [],
        "events": [],
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

    def fake_create_runner_branch(branch_plan, **kwargs):
        calls["branch_plans"].append(branch_plan)
        result = {
            "branch_required": True,
            "branch_name": branch_plan["branch_name"],
            "base_ref": branch_plan["base_ref"],
            "create_command": branch_plan["create_command"],
            "current_branch": "main",
            "branch_exists": False,
            "created": True,
            "dry_run": kwargs["dry_run"],
            "errors": [],
        }
        calls["branch_results"].append(result)
        return result

    monkeypatch.setattr(cli, "create_runner_branch", fake_create_runner_branch)
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
        lambda gates, **_kwargs: {
            "quality": "deliverable",
            "checks": gates,
            "plan": [],
            "command_results": [],
            "deliverable": True,
            "note": "passed",
        },
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
        ["self-upgrade", "TASK-1", "--execute", "--apply", "--branch", "--base-ref", "main"],
    )

    assert result.exit_code == 0
    assert calls["preflight"][0][0][2] == ["lint"]
    assert calls["branch_plans"][0]["base_ref"] == "main"
    assert calls["branch_results"][0]["dry_run"] is False
    assert [call["tool_name"] for call in calls["tool_calls"]] == [
        "llm.chat_completion",
        "cli.runner_branch",
        "cli.runner_patch",
        "cli.runner_validate",
    ]
    assert calls["events"][0]["event_type"] == "self_upgrade_branch_created"
    assert '"branch_result"' in result.output


def test_self_upgrade_commit_records_delivery(monkeypatch):
    calls = {
        "preflight": [],
        "tool_calls": [],
        "events": [],
        "deliveries": [],
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
        lambda gates, **_kwargs: {
            "quality": "deliverable",
            "checks": gates,
            "plan": [],
            "command_results": [],
            "deliverable": True,
            "note": "passed",
        },
    )

    def fake_delivery(repository, **kwargs):
        calls["deliveries"].append((repository, kwargs))
        return {
            "repository": repository.name,
            "workspace_path": repository.workspace_path,
            "changed_files": kwargs["changed_files"],
            "commit_message": kwargs["commit_message"],
            "status_lines": [" M app/chao/demo.py"],
            "dry_run": kwargs["dry_run"],
            "committed": True,
            "pushed": kwargs["push"],
            "commit_sha": "abc123",
            "commands": [],
            "errors": [],
        }

    monkeypatch.setattr(cli, "execute_self_upgrade_delivery", fake_delivery)
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
        ["self-upgrade", "TASK-1", "--execute", "--apply", "--commit", "--push"],
    )

    assert result.exit_code == 0
    assert calls["deliveries"][0][1]["push"] is True
    assert calls["deliveries"][0][1]["dry_run"] is False
    assert [call["tool_name"] for call in calls["tool_calls"]] == [
        "llm.chat_completion",
        "cli.runner_patch",
        "cli.runner_validate",
        "cli.self_upgrade_delivery",
    ]
    assert calls["events"][-1]["event_type"] == "self_upgrade_delivered"
    assert '"status": "delivered"' in result.output


def test_self_upgrade_create_pr_records_github_link(monkeypatch):
    calls = {
        "preflight": [],
        "tool_calls": [],
        "events": [],
        "deliveries": [],
        "prs": [],
        "github_links": [],
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
        lambda gates, **_kwargs: {
            "quality": "deliverable",
            "checks": gates,
            "plan": [],
            "command_results": [],
            "deliverable": True,
            "note": "passed",
        },
    )
    monkeypatch.setattr(
        cli,
        "execute_self_upgrade_delivery",
        lambda repository, **kwargs: (
            calls["deliveries"].append((repository, kwargs))
            or {
                "repository": repository.name,
                "workspace_path": repository.workspace_path,
                "changed_files": kwargs["changed_files"],
                "commit_message": kwargs["commit_message"],
                "status_lines": [" M app/chao/demo.py"],
                "dry_run": kwargs["dry_run"],
                "committed": True,
                "pushed": kwargs["push"],
                "commit_sha": "abc123",
                "commands": [],
                "errors": [],
            }
        ),
    )

    def fake_pr(repository, **kwargs):
        calls["prs"].append((repository, kwargs))
        return {
            "repository": repository.name,
            "workspace_path": repository.workspace_path,
            "title": kwargs["title"],
            "body": kwargs["body"],
            "base_ref": kwargs["base_ref"],
            "head_ref": "codex/task-1-demo",
            "dry_run": kwargs["dry_run"],
            "created": True,
            "url": "https://github.com/example/repo/pull/42",
            "external_id": "42",
            "commands": [],
            "errors": [],
        }

    monkeypatch.setattr(cli, "execute_github_pr_create", fake_pr)
    monkeypatch.setattr(
        cli,
        "record_github_link",
        lambda **kwargs: calls["github_links"].append(kwargs),
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
        [
            "self-upgrade",
            "TASK-1",
            "--execute",
            "--apply",
            "--commit",
            "--push",
            "--create-pr",
        ],
    )

    assert result.exit_code == 0
    assert "Task Code: TASK-1" in calls["prs"][0][1]["body"]
    assert calls["github_links"][0]["link_type"] == "pull_request"
    assert calls["github_links"][0]["external_id"] == "42"
    assert [call["tool_name"] for call in calls["tool_calls"]] == [
        "llm.chat_completion",
        "cli.runner_patch",
        "cli.runner_validate",
        "cli.self_upgrade_delivery",
        "cli.create_github_pr",
    ]
    assert calls["events"][-1]["event_type"] == "self_upgrade_pr_created"
    assert '"status": "pr_created"' in result.output


def test_self_upgrade_check_ci_records_ci_links(monkeypatch):
    calls = {
        "preflight": [],
        "tool_calls": [],
        "events": [],
        "deliveries": [],
        "prs": [],
        "github_links": [],
        "ci": [],
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
        lambda gates, **_kwargs: {
            "quality": "deliverable",
            "checks": gates,
            "plan": [],
            "command_results": [],
            "deliverable": True,
            "note": "passed",
        },
    )
    monkeypatch.setattr(
        cli,
        "execute_self_upgrade_delivery",
        lambda repository, **kwargs: {
            "repository": repository.name,
            "workspace_path": repository.workspace_path,
            "changed_files": kwargs["changed_files"],
            "commit_message": kwargs["commit_message"],
            "status_lines": [" M app/chao/demo.py"],
            "dry_run": kwargs["dry_run"],
            "committed": True,
            "pushed": kwargs["push"],
            "commit_sha": "abc123",
            "commands": [],
            "errors": [],
        },
    )
    monkeypatch.setattr(
        cli,
        "execute_github_pr_create",
        lambda repository, **kwargs: {
            "repository": repository.name,
            "workspace_path": repository.workspace_path,
            "title": kwargs["title"],
            "body": kwargs["body"],
            "base_ref": kwargs["base_ref"],
            "head_ref": "codex/task-1-demo",
            "dry_run": kwargs["dry_run"],
            "created": True,
            "url": "https://github.com/example/repo/pull/42",
            "external_id": "42",
            "commands": [],
            "errors": [],
        },
    )
    monkeypatch.setattr(
        cli,
        "execute_github_pr_checks",
        lambda repository, **kwargs: (
            calls["ci"].append((repository, kwargs))
            or {
                "repository": repository.name,
                "workspace_path": repository.workspace_path,
                "pr_ref": kwargs["pr_ref"],
                "status": "passed",
                "deliverable": True,
                "dry_run": kwargs["dry_run"],
                "checks": [
                    {
                        "name": "pytest",
                        "state": "SUCCESS",
                        "link": "https://github.com/example/repo/actions/runs/99",
                        "workflow": "CI",
                        "bucket": "pass",
                    }
                ],
                "commands": [],
                "errors": [],
            }
        ),
    )
    monkeypatch.setattr(
        cli,
        "record_github_link",
        lambda **kwargs: calls["github_links"].append(kwargs),
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
        [
            "self-upgrade",
            "TASK-1",
            "--execute",
            "--apply",
            "--commit",
            "--push",
            "--create-pr",
            "--check-ci",
        ],
    )

    assert result.exit_code == 0
    assert calls["ci"][0][1]["pr_ref"] == "https://github.com/example/repo/pull/42"
    assert calls["github_links"][1]["link_type"] == "ci_run"
    assert calls["github_links"][1]["status"] == "success"
    assert calls["tool_calls"][-1]["tool_name"] == "cli.github_ci_check"
    assert calls["events"][-1]["event_type"] == "self_upgrade_ci_passed"
    assert '"status": "ci_passed"' in result.output

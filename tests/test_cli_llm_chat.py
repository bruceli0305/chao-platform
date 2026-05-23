from typer.testing import CliRunner

from app.chao import cli


def test_llm_chat_dry_run_records_tool_call(monkeypatch):
    calls = []
    prompts = []
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "title": "Console summary",
        "raw_request": "Summarize console delivery.",
        "task_level": "L2",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "B"},
    }

    def fake_execute(_config, prompt, **_kwargs):
        prompts.append(prompt)

        class Result:
            status = "dry_run"
            dry_run = True
            error = None

            def to_safe_dict(self):
                return {
                    "provider": "deepseek",
                    "model": "deepseek-chat",
                    "status": "dry_run",
                    "dry_run": True,
                    "request": {},
                    "response": None,
                    "error": None,
                }

        return Result()

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(cli, "execute_llm_chat_completion", fake_execute)
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
    assert "Summarize console delivery." in prompts[0]
    assert "summarize the task" in prompts[0]


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


def test_llm_chat_execute_denies_sensitive_data_classification(monkeypatch):
    calls = []
    executed = []
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "title": "Sensitive summary",
        "raw_request": "Summarize sensitive deployment data.",
        "task_level": "L2",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "B"},
    }

    def fake_execute(*_args, **_kwargs):
        executed.append(True)
        raise AssertionError("external provider should not be called")

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(cli, "execute_llm_chat_completion", fake_execute)
    monkeypatch.setattr(cli, "record_tool_call", lambda **kwargs: calls.append(kwargs))

    result = CliRunner().invoke(
        cli.app,
        [
            "llm-chat",
            "TASK-1",
            "summarize the task",
            "--data-classification",
            "D2",
            "--execute",
        ],
    )

    assert result.exit_code == 1
    assert executed == []
    assert calls[0]["result_status"] == "denied"
    assert calls[0]["permission_decision"]["egress_policy"]["allowed"] is False
    assert "D2 data cannot be sent" in result.output


def test_llm_chat_execute_denies_l3_task(monkeypatch):
    calls = []
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "title": "Governed task",
        "raw_request": "Summarize governed task.",
        "task_level": "L3",
        "status": "DESIGNING",
        "route_result": {"required_confirmation": "A"},
    }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(cli, "record_tool_call", lambda **kwargs: calls.append(kwargs))

    result = CliRunner().invoke(
        cli.app,
        [
            "llm-chat",
            "TASK-1",
            "summarize the task",
            "--execute",
        ],
    )

    assert result.exit_code == 1
    assert calls[0]["result_status"] == "denied"
    assert calls[0]["permission_decision"]["egress_policy"]["task_level"] == "L3"
    assert "L3 tasks cannot call external LLM providers" in result.output


def test_llm_chat_execute_allows_l3_with_governed_approval(monkeypatch):
    calls = []
    prompts = []
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "title": "Governed task",
        "raw_request": "Summarize governed task.",
        "task_level": "L3",
        "status": "DESIGNING",
        "route_result": {"required_confirmation": "A"},
        "confirmations": [
            {
                "confirmation_level": "A",
                "status": "APPROVED",
                "confirmed_by": "emperor",
            }
        ],
        "llm_egress_authorizations": [
            {
                "provider": "deepseek",
                "model": "deepseek-v4-pro",
                "data_classification": "D1",
                "status": "APPROVED",
                "active": True,
            }
        ],
    }

    def fake_execute(_config, prompt, **_kwargs):
        prompts.append(prompt)

        class Result:
            status = "success"
            dry_run = False
            error = None

            def to_safe_dict(self):
                return {
                    "provider": "deepseek",
                    "model": "deepseek-v4-pro",
                    "status": "success",
                    "dry_run": False,
                    "request": {},
                    "response": {"choices": []},
                    "error": None,
                }

        return Result()

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(cli, "execute_llm_chat_completion", fake_execute)
    monkeypatch.setattr(cli, "record_tool_call", lambda **kwargs: calls.append(kwargs))

    result = CliRunner().invoke(
        cli.app,
        [
            "llm-chat",
            "TASK-1",
            "summarize the task",
            "--execute",
            "--allow-governed-egress",
        ],
    )

    assert result.exit_code == 0
    assert "Summarize governed task." in prompts[0]
    assert calls[0]["result_status"] == "success"
    assert calls[0]["permission_decision"]["egress_policy"]["task_level"] == "L3"
    assert calls[0]["permission_decision"]["egress_policy"]["governed_egress_approved"] is True


def test_llm_chat_execute_denies_l3_without_active_authorization_even_with_flag(monkeypatch):
    calls = []
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "title": "Governed task",
        "raw_request": "Summarize governed task.",
        "task_level": "L3",
        "status": "DESIGNING",
        "route_result": {"required_confirmation": "A"},
        "confirmations": [{"confirmation_level": "A", "status": "APPROVED"}],
        "llm_egress_authorizations": [],
    }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(cli, "record_tool_call", lambda **kwargs: calls.append(kwargs))

    result = CliRunner().invoke(
        cli.app,
        [
            "llm-chat",
            "TASK-1",
            "summarize the task",
            "--execute",
            "--allow-governed-egress",
        ],
    )

    assert result.exit_code == 1
    assert calls[0]["result_status"] == "denied"
    assert calls[0]["permission_decision"]["egress_policy"]["governed_egress_approved"] is False


def test_authorize_llm_egress_records_time_limited_authorization(monkeypatch):
    calls = {"events": [], "tools": [], "authorizations": []}
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "title": "Governed task",
        "raw_request": "Summarize governed task.",
        "task_level": "L3",
        "status": "DESIGNING",
        "route_result": {"required_confirmation": "A"},
        "confirmations": [{"confirmation_level": "A", "status": "APPROVED"}],
    }

    def fake_record_authorization(**kwargs):
        calls["authorizations"].append(kwargs)
        return {
            "id": "auth-1",
            **kwargs,
            "status": "APPROVED",
            "expires_at": "2026-05-21T00:00:00+00:00",
        }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(cli, "record_llm_egress_authorization", fake_record_authorization)
    monkeypatch.setattr(cli, "record_task_event", lambda **kwargs: calls["events"].append(kwargs))
    monkeypatch.setattr(cli, "record_tool_call", lambda **kwargs: calls["tools"].append(kwargs))

    result = CliRunner().invoke(
        cli.app,
        [
            "authorize-llm-egress",
            "TASK-1",
            "--provider",
            "deepseek",
            "--model",
            "deepseek-v4-pro",
            "--ttl-hours",
            "2",
        ],
    )

    assert result.exit_code == 0
    assert calls["authorizations"][0]["ttl_hours"] == 2
    assert calls["events"][0]["event_type"] == "llm_egress_authorized"
    assert calls["tools"][0]["tool_name"] == "cli.authorize_llm_egress"
    assert calls["tools"][0]["permission_policy"] == "governed-llm-egress-authorization"


def test_authorize_llm_egress_requires_a_approval(monkeypatch):
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "task_level": "L3",
        "status": "DESIGNING",
        "route_result": {"required_confirmation": "A"},
        "confirmations": [],
    }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)

    result = CliRunner().invoke(cli.app, ["authorize-llm-egress", "TASK-1"])

    assert result.exit_code == 1
    assert "A-level APPROVED confirmation is required" in result.output


def test_audit_llm_egress_authorizations_marks_expired_rows(monkeypatch):
    calls = {"events": [], "tools": [], "marked": []}
    authorizations = [
        {
            "id": "auth-1",
            "task_id": "task-1",
            "task_code": "TASK-1",
            "task_level": "L3",
            "task_status": "DESIGNING",
            "required_confirmation": "A",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "data_classification": "D1",
            "status": "APPROVED",
            "authorized_by": "emperor",
            "reason": "test",
            "expires_at": "2026-05-20 00:00:00+00",
            "created_at": "2026-05-19 00:00:00+00",
        }
    ]

    monkeypatch.setattr(
        cli,
        "list_expired_llm_egress_authorizations",
        lambda **_kwargs: authorizations,
    )
    monkeypatch.setattr(
        cli,
        "mark_llm_egress_authorizations_expired",
        lambda authorization_ids: calls["marked"].append(authorization_ids),
    )
    monkeypatch.setattr(cli, "record_task_event", lambda **kwargs: calls["events"].append(kwargs))
    monkeypatch.setattr(cli, "record_tool_call", lambda **kwargs: calls["tools"].append(kwargs))

    result = CliRunner().invoke(cli.app, ["audit-llm-egress-authorizations", "--apply"])

    assert result.exit_code == 0
    assert calls["marked"] == [["auth-1"]]
    assert calls["events"][0]["event_type"] == "llm_egress_authorization_expired"
    assert calls["tools"][0]["tool_name"] == "cli.audit_llm_egress_authorizations"
    assert calls["tools"][0]["permission_policy"] == "governed-llm-egress-expiry-audit"
    assert calls["tools"][0]["result_status"] == "success"
    assert '"expired_count": 1' in result.output


def test_audit_llm_egress_authorizations_checks_permission_before_marking(monkeypatch):
    calls = {"marked": []}
    authorizations = [
        {
            "id": "auth-1",
            "task_id": "task-1",
            "task_code": "TASK-1",
            "task_level": "L3",
            "task_status": "DESIGNING",
            "required_confirmation": "A",
            "provider": "deepseek",
            "model": "deepseek-chat",
            "data_classification": "D1",
            "status": "APPROVED",
            "authorized_by": "emperor",
            "reason": "test",
            "expires_at": "2026-05-20 00:00:00+00",
            "created_at": "2026-05-19 00:00:00+00",
        }
    ]

    monkeypatch.setattr(
        cli,
        "list_expired_llm_egress_authorizations",
        lambda **_kwargs: authorizations,
    )
    monkeypatch.setattr(
        cli,
        "mark_llm_egress_authorizations_expired",
        lambda authorization_ids: calls["marked"].append(authorization_ids),
    )

    result = CliRunner().invoke(
        cli.app,
        ["audit-llm-egress-authorizations", "--apply", "--by", "hubu"],
    )

    assert result.exit_code == 1
    assert calls["marked"] == []


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

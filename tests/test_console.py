from typer.testing import CliRunner

from app.chao import cli
from app.chao.services import console


def test_rows_to_counts():
    assert console._rows_to_counts([("DELIVERED", 2), ("NEED_CONFIRMATION", 1)]) == {
        "DELIVERED": 2,
        "NEED_CONFIRMATION": 1,
    }


def test_get_console_overview_returns_dashboard_shape(monkeypatch):
    queries = []
    rows = [
        [("DELIVERED", 2), ("NEED_CONFIRMATION", 1)],
        [("L1", 1), ("L3", 2)],
        [(1,)],
        [(3,)],
        [(4,)],
        [(2,)],
        [(0,)],
        [
            (
                "TASK-TEST",
                "修复文案",
                "L1",
                "DELIVERED",
                "shangshu",
                "2026-05-14 00:00:00",
            )
        ],
    ]

    class FakeCursor:
        def __init__(self):
            self.index = -1

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, params=None):
            queries.append((query, params))
            self.index += 1

        def fetchall(self):
            return rows[self.index]

        def fetchone(self):
            return rows[self.index][0]

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(console.psycopg, "connect", lambda _url: FakeConnection())

    overview = console.get_console_overview(limit=1)

    assert overview["task_status_counts"] == {
        "DELIVERED": 2,
        "NEED_CONFIRMATION": 1,
    }
    assert overview["task_level_counts"] == {"L1": 1, "L3": 2}
    assert overview["approved_confirmations"] == 1
    assert overview["artifact_count"] == 3
    assert overview["data_asset_count"] == 4
    assert overview["active_llm_egress_authorization_count"] == 2
    assert overview["failed_tool_call_count"] == 0
    assert overview["recent_tasks"][0]["task_code"] == "TASK-TEST"
    assert queries[-1][1] == (1,)


def test_get_console_approval_queue_returns_pending_tasks(monkeypatch):
    queries = []
    rows = [
        [
            (
                "TASK-L3",
                "Database migration",
                "L3",
                "NEED_CONFIRMATION",
                "shangshu",
                "2026-05-14 00:00:00",
                {
                    "required_confirmation": "A",
                    "required_skills": ["database-migration"],
                    "required_skill_paths": [".ai-agents/skills/database-migration/SKILL.md"],
                },
            )
        ]
    ]

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, params=None):
            queries.append((query, params))

        def fetchall(self):
            return rows[0]

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(console.psycopg, "connect", lambda _url: FakeConnection())

    approvals = console.get_console_approval_queue(limit=5)

    assert approvals == [
        {
            "task_code": "TASK-L3",
            "title": "Database migration",
            "task_level": "L3",
            "status": "NEED_CONFIRMATION",
            "owner": "shangshu",
            "created_at": "2026-05-14 00:00:00",
            "required_confirmation": "A",
            "required_skills": ["database-migration"],
            "required_skill_paths": [".ai-agents/skills/database-migration/SKILL.md"],
        }
    ]
    assert queries[0][1] == (5,)


def test_get_console_audit_returns_recent_records(monkeypatch):
    queries = []
    rows = [
        [
            (
                "TASK-1",
                "task_created",
                "RAW",
                "DELIVERED",
                "created",
                "shangshu",
                "2026-05-14 00:00:00",
            )
        ],
        [
            (
                "TASK-1",
                "shangshu",
                "cli.new",
                "local-cli-task-create",
                "success",
                "low",
                "2026-05-14 00:00:01",
            )
        ],
        [
            (
                "TASK-1",
                "runner_patch",
                ".ai-agents/records/patches/TASK-1-patch.md",
                "internal",
                365,
                "2026-05-14 00:00:02",
            )
        ],
        [
            (
                "TASK-1",
                ".ai-agents/records/patches/TASK-1-patch.md",
                "runner_patch",
                "D1",
                "gongbu",
                "2026-05-14 00:00:03",
            )
        ],
        [
            (
                "TASK-1",
                "pull_request",
                "42",
                "https://github.com/example/repo/pull/42",
                "open",
                "ci",
                "2026-05-14 00:00:04",
            )
        ],
        [
            (
                "TASK-1",
                "deepseek",
                "deepseek-chat",
                "D1",
                "APPROVED",
                "emperor",
                "2026-05-15 00:00:00",
                True,
                "2026-05-14 00:00:05",
            )
        ],
    ]

    class FakeCursor:
        def __init__(self):
            self.index = -1

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, params=None):
            queries.append((query, params))
            self.index += 1

        def fetchall(self):
            return rows[self.index]

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(console.psycopg, "connect", lambda _url: FakeConnection())

    audit = console.get_console_audit(limit=3)

    assert audit["events"][0]["event_type"] == "task_created"
    assert audit["tool_calls"][0]["tool_name"] == "cli.new"
    assert audit["artifacts"][0]["artifact_type"] == "runner_patch"
    assert audit["data_assets"][0]["classification"] == "D1"
    assert audit["github_links"][0]["external_id"] == "42"
    assert audit["llm_egress_authorizations"][0]["active"] is True
    assert queries[-1][1] == (3,)


def test_get_console_github_sync_returns_sync_summary(monkeypatch):
    queries = []
    rows = [
        [(5,)],
        [(2,)],
        [(3,)],
        [(1,)],
        [(1,)],
        [("ci_run", 2), ("pull_request", 3)],
        [("failed", 1), ("success", 4)],
        [
            (
                "TASK-PR",
                "GitHub sync task",
                "pull_request",
                "42",
                "https://github.com/example/repo/pull/42",
                "open",
                "github-actions",
                "2026-05-20 00:00:00",
            )
        ],
        [
            (
                "TASK-PR",
                "GitHub delivery context recorded for TASK-PR: 3 link(s).",
                "github-actions",
                "2026-05-20 00:00:01",
            )
        ],
        [
            (
                "TASK-CI",
                "CI task",
                "ci_run",
                "99",
                "https://github.com/example/repo/actions/runs/99",
                "failed",
                "2026-05-20 00:00:02",
            )
        ],
        [
            (
                "TASK-UNLINKED",
                "Delivered without GitHub link",
                "L2",
                "DELIVERED",
                "shangshu",
                "2026-05-20 00:00:03",
            )
        ],
    ]

    class FakeCursor:
        def __init__(self):
            self.index = -1

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, params=None):
            queries.append((query, params))
            self.index += 1

        def fetchall(self):
            return rows[self.index]

        def fetchone(self):
            return rows[self.index][0]

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(console.psycopg, "connect", lambda _url: FakeConnection())

    github_sync = console.get_console_github_sync(limit=5)

    assert github_sync["summary"] == {
        "github_link_count": 5,
        "linked_task_count": 2,
        "github_delivery_event_count": 3,
        "failed_github_link_count": 1,
        "unlinked_delivered_task_count": 1,
    }
    assert github_sync["link_type_counts"] == {"ci_run": 2, "pull_request": 3}
    assert github_sync["status_counts"] == {"failed": 1, "success": 4}
    assert github_sync["recent_links"][0]["external_id"] == "42"
    assert github_sync["recent_delivery_events"][0]["task_code"] == "TASK-PR"
    assert github_sync["failed_links"][0]["status"] == "failed"
    assert github_sync["recent_unlinked_delivered_tasks"][0]["task_code"] == "TASK-UNLINKED"
    assert queries[-1][1] == (5,)


def test_get_console_gates_returns_audit_summary(monkeypatch):
    queries = []
    rows = [
        [("pass", 2), ("fail", 1)],
        [("TASK-1", "pytest", "pass", "uv run pytest -q", "2026-05-14 00:00:00")],
        [(0,)],
        [(0,)],
        [(1,)],
        [(2,)],
        [(1,)],
        [(3,)],
        [(0,)],
        [(0,)],
        [(0,)],
    ]

    class FakeCursor:
        def __init__(self):
            self.index = -1

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, params=None):
            queries.append((query, params))
            self.index += 1

        def fetchall(self):
            return rows[self.index]

        def fetchone(self):
            return rows[self.index][0]

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(console.psycopg, "connect", lambda _url: FakeConnection())

    gates = console.get_console_gates(limit=7)

    assert gates["gate_status_counts"] == {"pass": 2, "fail": 1}
    assert gates["recent_gate_results"][0]["gate_name"] == "pytest"
    assert gates["tool_permission_audit"] == {
        "missing_policy_count": 0,
        "empty_decision_count": 0,
        "failed_tool_call_count": 1,
        "pending_tool_call_count": 2,
        "stale_tool_call_count": 1,
    }
    assert gates["data_boundary_audit"] == {
        "storage_policy_count": 3,
        "invalid_data_asset_classification_count": 0,
        "invalid_context_classification_count": 0,
        "unredacted_ingest_allowed_count": 0,
    }
    assert queries[1][1] == (7,)


def test_get_console_risks_returns_risk_summary(monkeypatch):
    queries = []
    rows = [
        [
            (
                "TASK-BLOCKED",
                "Needs approval",
                "L3",
                "NEED_CONFIRMATION",
                "shangshu",
                "2026-05-14 00:00:00",
            )
        ],
        [("TASK-FAIL", "pytest", "failed", "uv run pytest -q", "2026-05-14 00:00:01")],
        [
            (
                "TASK-RUNNER-FAIL",
                "runner_failure_feedback",
                ".ai-agents/records/failures/TASK-RUNNER-FAIL-failure-feedback.md",
                "2026-05-14 00:00:02",
            )
        ],
        [
            (
                "TASK-PREFLIGHT",
                "Runner preflight blocked: demo; errors=repository is not runner ready",
                "gongbu",
                "2026-05-14 00:00:02",
            )
        ],
        [
            (
                "TASK-TOOL",
                "shangshu",
                "cli.new",
                "",
                "failed",
                "high",
                "2026-05-14 00:00:02",
            )
        ],
        [
            (
                "TASK-PENDING",
                "xingbu",
                "data_boundary_check",
                "data-boundary-validation",
                "started",
                "2026-05-14 00:00:03",
            )
        ],
        [
            (
                "TASK-STALE",
                "xingbu",
                "schema_check",
                "schema-read-validation",
                "started",
                "2026-05-14 00:00:00",
                30,
            )
        ],
        [(1,)],
        [(2,)],
        [(3,)],
        [
            (
                "TASK-PR",
                "ci_run",
                "123",
                "https://github.com/example/repo/actions/runs/123",
                "failed",
                "2026-05-14 00:00:03",
            )
        ],
        [
            (
                "TASK-L3",
                "deepseek",
                "deepseek-chat",
                "D1",
                "APPROVED",
                "2026-05-13 00:00:00",
                "emperor",
            )
        ],
    ]

    class FakeCursor:
        def __init__(self):
            self.index = -1

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, params=None):
            queries.append((query, params))
            self.index += 1

        def fetchall(self):
            return rows[self.index]

        def fetchone(self):
            return rows[self.index][0]

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(console.psycopg, "connect", lambda _url: FakeConnection())

    risks = console.get_console_risks(limit=4)

    assert risks["blocked_tasks"][0]["task_code"] == "TASK-BLOCKED"
    assert risks["failed_gates"][0]["gate_name"] == "pytest"
    assert risks["runner_failures"][0]["artifact_type"] == "runner_failure_feedback"
    assert risks["runner_preflight_blocks"][0]["task_code"] == "TASK-PREFLIGHT"
    assert risks["tool_risks"][0]["tool_name"] == "cli.new"
    assert risks["pending_tool_calls"][0]["task_code"] == "TASK-PENDING"
    assert risks["stale_tool_calls"][0]["task_code"] == "TASK-STALE"
    assert risks["data_boundary_risks"] == {
        "invalid_data_asset_classification_count": 1,
        "invalid_context_classification_count": 2,
        "unredacted_ingest_allowed_count": 3,
    }
    assert risks["github_risks"][0]["status"] == "failed"
    assert risks["expired_llm_egress_authorizations"][0]["task_code"] == "TASK-L3"
    assert risks["summary"] == {
        "blocked_task_count": 1,
        "failed_gate_count": 1,
        "runner_failure_count": 1,
        "runner_preflight_block_count": 1,
        "tool_risk_count": 1,
        "pending_tool_call_count": 1,
        "stale_tool_call_count": 1,
        "data_boundary_risk_count": 6,
        "github_risk_count": 1,
        "expired_llm_egress_authorization_count": 1,
    }
    assert queries[0][1] == (4,)
    assert queries[-1][1] == (4,)


def test_console_task_renders_task_detail(monkeypatch):
    task = {
        "task_code": "TASK-TEST",
        "title": "Fix title",
        "task_level": "L1",
        "status": "DELIVERED",
        "owner": "shangshu",
        "created_at": "2026-05-14 00:00:00",
        "updated_at": "2026-05-14 00:01:00",
        "events": [
            {
                "event_type": "task_created",
                "from_status": "RAW",
                "to_status": "DELIVERED",
                "created_by": "shangshu",
            }
        ],
        "tool_calls": [
            {
                "agent_name": "shangshu",
                "tool_name": "cli.new",
                "permission_policy": "local-cli-task-create",
                "result_status": "success",
            }
        ],
        "artifacts": [
            {
                "artifact_type": "runner_patch",
                "artifact_uri": ".ai-agents/records/patches/TASK-TEST-patch.md",
                "access_level": "internal",
            }
        ],
        "data_assets": [
            {
                "asset_type": "runner_patch",
                "classification": "D1",
                "owner": "gongbu",
                "primary_storage": "Git / Markdown",
            }
        ],
        "skill_usage": [
            {
                "name": "bugfix",
                "path": ".ai-agents/skills/bugfix/SKILL.md",
                "status": "loaded",
                "content_sha256": "a" * 64,
            }
        ],
        "skill_execution_plan": {
            "status": "ready",
            "skills": [
                {
                    "name": "bugfix",
                    "path": ".ai-agents/skills/bugfix/SKILL.md",
                    "status": "loaded",
                    "content_sha256": "a" * 64,
                    "default_gates": ["lint", "test", "manual_validation"],
                }
            ],
            "combined_gates": ["manual_validation", "lint", "test"],
        },
        "llm_egress_authorizations": [
            {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "data_classification": "D1",
                "status": "APPROVED",
                "active": True,
            }
        ],
        "github_links": [],
        "historian_records": [],
        "gate_results": [],
    }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: task)

    result = CliRunner().invoke(cli.app, ["console-task", "TASK-TEST"])

    assert result.exit_code == 0
    assert "Task Detail" in result.output
    assert "TASK-TEST" in result.output
    assert "runner_patch" in result.output
    assert "Skill Execution Plan" in result.output
    assert "bugfix" in result.output
    assert "deepseek-chat" in result.output


def test_console_task_rejects_missing_task(monkeypatch):
    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: None)

    result = CliRunner().invoke(cli.app, ["console-task", "TASK-MISSING"])

    assert result.exit_code == 1
    assert "Task not found" in result.output


def test_console_approvals_renders_pending_tasks(monkeypatch):
    approvals = [
        {
            "task_code": "TASK-L3",
            "title": "Database migration",
            "task_level": "L3",
            "required_confirmation": "A",
            "owner": "shangshu",
            "created_at": "2026-05-14 00:00:00",
        }
    ]

    monkeypatch.setattr(cli, "get_console_approval_queue", lambda limit=20: approvals)

    result = CliRunner().invoke(cli.app, ["console-approvals"])

    assert result.exit_code == 0
    assert "Pending Approvals" in result.output
    assert "TASK-L3" in result.output
    assert "A" in result.output


def test_console_audit_renders_recent_records(monkeypatch):
    audit = {
        "events": [
            {
                "task_code": "TASK-1",
                "event_type": "task_created",
                "from_status": "RAW",
                "to_status": "DELIVERED",
                "created_by": "shangshu",
            }
        ],
        "tool_calls": [
            {
                "task_code": "TASK-1",
                "agent_name": "shangshu",
                "tool_name": "cli.new",
                "permission_policy": "local-cli-task-create",
                "result_status": "success",
            }
        ],
        "artifacts": [
            {
                "task_code": "TASK-1",
                "artifact_type": "runner_patch",
                "artifact_uri": ".ai-agents/records/patches/TASK-1-patch.md",
                "access_level": "internal",
            }
        ],
        "data_assets": [
            {
                "task_code": "TASK-1",
                "asset_type": "runner_patch",
                "classification": "D1",
                "owner": "gongbu",
            }
        ],
        "github_links": [
            {
                "task_code": "TASK-1",
                "link_type": "pull_request",
                "external_id": "42",
                "status": "open",
            }
        ],
        "llm_egress_authorizations": [
            {
                "task_code": "TASK-1",
                "provider": "deepseek",
                "model": "deepseek-chat",
                "data_classification": "D1",
                "active": True,
            }
        ],
    }

    monkeypatch.setattr(cli, "get_console_audit", lambda limit=20: audit)

    result = CliRunner().invoke(cli.app, ["console-audit"])

    assert result.exit_code == 0
    assert "Recent Events" in result.output
    assert "cli.new" in result.output
    assert "runner_patch" in result.output
    assert "pull_request" in result.output
    assert "deepseek-chat" in result.output


def test_console_github_sync_renders_sync_summary(monkeypatch):
    github_sync = {
        "summary": {
            "github_link_count": 2,
            "linked_task_count": 1,
            "github_delivery_event_count": 1,
            "failed_github_link_count": 1,
            "unlinked_delivered_task_count": 1,
        },
        "link_type_counts": {"pull_request": 1, "ci_run": 1},
        "status_counts": {"open": 1, "failed": 1},
        "recent_links": [
            {
                "task_code": "TASK-PR",
                "link_type": "pull_request",
                "external_id": "42",
                "status": "open",
                "created_by": "github-actions",
            }
        ],
        "recent_delivery_events": [
            {
                "task_code": "TASK-PR",
                "summary": "GitHub delivery context recorded for TASK-PR: 2 link(s).",
                "created_by": "github-actions",
                "created_at": "2026-05-20 00:00:00",
            }
        ],
        "failed_links": [
            {
                "task_code": "TASK-CI",
                "link_type": "ci_run",
                "external_id": "99",
                "status": "failed",
            }
        ],
        "recent_unlinked_delivered_tasks": [
            {
                "task_code": "TASK-UNLINKED",
                "title": "Delivered without GitHub link",
                "task_level": "L2",
                "owner": "shangshu",
            }
        ],
        "failed_statuses": ["failure", "failed", "error", "cancelled"],
    }

    monkeypatch.setattr(cli, "get_console_github_sync", lambda limit=20: github_sync)

    result = CliRunner().invoke(cli.app, ["console-github-sync"])

    assert result.exit_code == 0
    assert "GitHub Task Sync Summary" in result.output
    assert "Recent GitHub Sync Links" in result.output
    assert "Recent GitHub Delivery Events" in result.output
    assert "Unlinked Delivered Tasks" in result.output
    assert "Failed GitHub Sync Links" in result.output
    assert "TASK-PR" in result.output
    assert "TASK-CI" in result.output
    assert "TASK-UNLINKED" in result.output


def test_console_repositories_renders_workspace_summary(monkeypatch):
    repository_status = {
        "summary": {
            "repositories": 1,
            "ready": 1,
            "dirty": 0,
            "errors": 0,
        },
        "repositories": [
            {
                "name": "chao-platform",
                "workspace_ready": True,
                "current_branch": "main",
                "workspace_path": ".",
                "dirty": False,
                "ahead": 0,
                "behind": 0,
                "errors": "",
            }
        ],
    }

    monkeypatch.setattr(
        cli,
        "build_repository_status_report",
        lambda repositories: repository_status,
    )
    monkeypatch.setattr(cli, "list_repository_configs", lambda: [])

    result = CliRunner().invoke(cli.app, ["console-repositories"])

    assert result.exit_code == 0
    assert "Repository Workspace" in result.output
    assert "Summary" in result.output
    assert "Repository Workspaces" in result.output
    assert "chao-platform" in result.output


def test_console_repositories_outputs_json(monkeypatch):
    monkeypatch.setattr(
        cli,
        "build_repository_status_report",
        lambda repositories: {"summary": {"repositories": 0}, "repositories": []},
    )
    monkeypatch.setattr(cli, "list_repository_configs", lambda: [])

    result = CliRunner().invoke(cli.app, ["console-repositories", "--json"])

    assert result.exit_code == 0
    assert '"repositories": []' in result.output


def test_tool_gateway_tools_renders_policy_metadata(monkeypatch):
    monkeypatch.setattr(
        cli,
        "list_tool_handlers",
        lambda: [
            {
                "tool_name": "data_boundary_check",
                "description": "Run data boundary check.",
                "category": "filesystem.read",
                "risk": "medium",
                "permission_policy": "data-boundary-validation",
                "allowed_roles": ["hubu", "menxia", "xingbu"],
            }
        ],
    )

    result = CliRunner().invoke(cli.app, ["tool-gateway-tools"])

    assert result.exit_code == 0
    assert "Tool Gateway Tools" in result.output


def test_tool_gateway_tools_outputs_json(monkeypatch):
    monkeypatch.setattr(
        cli,
        "list_tool_handlers",
        lambda: [
            {
                "tool_name": "schema_check",
                "description": "Run schema check.",
                "category": "postgres.read",
                "risk": "medium",
                "permission_policy": "schema-read-validation",
                "allowed_roles": ["menxia", "xingbu"],
            }
        ],
    )

    result = CliRunner().invoke(cli.app, ["tool-gateway-tools", "--json"])

    assert result.exit_code == 0
    assert "schema_check" in result.output
    assert "postgres.read" in result.output
    assert "medium" in result.output
    assert "schema-read-validation" in result.output
    assert "menxia" in result.output


def test_console_gates_renders_gate_summary(monkeypatch):
    gates = {
        "gate_status_counts": {"pass": 2},
        "recent_gate_results": [
            {
                "task_code": "TASK-1",
                "gate_name": "pytest",
                "status": "pass",
                "command": "uv run pytest -q",
            }
        ],
        "tool_permission_audit": {
            "missing_policy_count": 0,
            "empty_decision_count": 0,
            "failed_tool_call_count": 1,
            "pending_tool_call_count": 2,
            "stale_tool_call_count": 1,
        },
        "data_boundary_audit": {
            "storage_policy_count": 3,
            "invalid_data_asset_classification_count": 0,
            "invalid_context_classification_count": 0,
            "unredacted_ingest_allowed_count": 0,
        },
    }

    monkeypatch.setattr(cli, "get_console_gates", lambda limit=20: gates)

    result = CliRunner().invoke(cli.app, ["console-gates"])

    assert result.exit_code == 0
    assert "Gate Status" in result.output
    assert "Tool Permission Audit" in result.output
    assert "Data Boundary Audit" in result.output
    assert "pytest" in result.output


def test_console_risks_renders_risk_summary(monkeypatch):
    risks = {
        "blocked_tasks": [
            {
                "task_code": "TASK-BLOCKED",
                "title": "Needs approval",
                "task_level": "L3",
                "status": "NEED_CONFIRMATION",
            }
        ],
        "failed_gates": [
            {
                "task_code": "TASK-FAIL",
                "gate_name": "pytest",
                "status": "failed",
                "command": "uv run pytest -q",
            }
        ],
        "runner_failures": [
            {
                "task_code": "TASK-RUNNER-FAIL",
                "artifact_type": "runner_failure_feedback",
                "artifact_uri": ".ai-agents/records/failures/TASK-RUNNER-FAIL-failure-feedback.md",
            }
        ],
        "runner_preflight_blocks": [
            {
                "task_code": "TASK-PREFLIGHT",
                "summary": "Runner preflight blocked: demo",
                "created_by": "gongbu",
            }
        ],
        "tool_risks": [
            {
                "task_code": "TASK-TOOL",
                "agent_name": "shangshu",
                "tool_name": "cli.new",
                "result_status": "failed",
            }
        ],
        "pending_tool_calls": [
            {
                "task_code": "TASK-PENDING",
                "agent_name": "xingbu",
                "tool_name": "data_boundary_check",
                "started_at": "2026-05-14 00:00:03",
            }
        ],
        "stale_tool_calls": [
            {
                "task_code": "TASK-STALE",
                "agent_name": "xingbu",
                "tool_name": "schema_check",
                "age_minutes": 30,
            }
        ],
        "data_boundary_risks": {
            "invalid_data_asset_classification_count": 0,
            "invalid_context_classification_count": 0,
            "unredacted_ingest_allowed_count": 0,
        },
        "github_risks": [
            {
                "task_code": "TASK-PR",
                "link_type": "ci_run",
                "external_id": "123",
                "status": "failed",
            }
        ],
        "expired_llm_egress_authorizations": [
            {
                "task_code": "TASK-L3",
                "provider": "deepseek",
                "model": "deepseek-chat",
                "expires_at": "2026-05-13 00:00:00",
            }
        ],
        "summary": {
            "blocked_task_count": 1,
            "failed_gate_count": 1,
            "runner_failure_count": 1,
            "runner_preflight_block_count": 1,
            "tool_risk_count": 1,
            "pending_tool_call_count": 1,
            "stale_tool_call_count": 1,
            "data_boundary_risk_count": 0,
            "github_risk_count": 1,
            "expired_llm_egress_authorization_count": 1,
        },
    }

    monkeypatch.setattr(cli, "get_console_risks", lambda limit=20: risks)

    result = CliRunner().invoke(cli.app, ["console-risks"])

    assert result.exit_code == 0
    assert "Risk Summary" in result.output
    assert "Blocked Tasks" in result.output
    assert "TASK-BLOCKED" in result.output
    assert "runner_failure_feedback" in result.output
    assert "Runner Preflight Blocks" in result.output
    assert "TASK-PREFLIGHT" in result.output
    assert "pytest" in result.output
    assert "Stale Tool Calls" in result.output
    assert "schema_check" in result.output
    assert "Pending Tool Calls" in result.output
    assert "data_boundary_check" in result.output
    assert "ci_run" in result.output
    assert "Expired LLM Egress Authorizations" in result.output

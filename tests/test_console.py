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
    assert overview["failed_tool_call_count"] == 0
    assert overview["recent_tasks"][0]["task_code"] == "TASK-TEST"
    assert queries[-1][1] == (1,)


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


def test_console_task_rejects_missing_task(monkeypatch):
    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: None)

    result = CliRunner().invoke(cli.app, ["console-task", "TASK-MISSING"])

    assert result.exit_code == 1
    assert "Task not found" in result.output

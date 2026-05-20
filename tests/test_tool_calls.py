from psycopg.types.json import Jsonb

from app.chao.services import tool_calls


def test_record_tool_call_writes_permission_decision(monkeypatch):
    executed = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, params=None):
            executed.append((query, params))

    class FakeConnection:
        committed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            self.committed = True

    connection = FakeConnection()
    monkeypatch.setattr(tool_calls.psycopg, "connect", lambda _url: connection)

    tool_calls.record_tool_call(
        task_id="task-1",
        agent_name="shangshu",
        tool_name="cli.new",
        arguments_summary="title=test",
        permission_policy="local-cli-task-create",
        result_status="success",
        permission_decision={
            "allowed": True,
            "permission_policy": "local-cli-task-create",
        },
    )

    query, params = executed[0]

    assert "permission_decision" in query
    assert isinstance(params[6], Jsonb)
    assert connection.committed is True


def test_start_tool_call_writes_started_record(monkeypatch):
    executed = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, params=None):
            executed.append((query, params))

    class FakeConnection:
        committed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            self.committed = True

    connection = FakeConnection()
    monkeypatch.setattr(tool_calls.psycopg, "connect", lambda _url: connection)

    tool_call_id = tool_calls.start_tool_call(
        task_id="task-1",
        agent_name="xingbu",
        tool_name="data_boundary_check",
        arguments_summary="gate=data_boundary_check",
        permission_policy="data-boundary-validation",
        permission_decision={"allowed": True},
    )

    query, params = executed[0]

    assert tool_call_id
    assert "result_status" in query
    assert "'started'" in query
    assert params[1] == "task-1"
    assert isinstance(params[6], Jsonb)
    assert connection.committed is True


def test_finish_tool_call_updates_result(monkeypatch):
    executed = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, params=None):
            executed.append((query, params))

    class FakeConnection:
        committed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            self.committed = True

    connection = FakeConnection()
    monkeypatch.setattr(tool_calls.psycopg, "connect", lambda _url: connection)

    tool_calls.finish_tool_call(
        "tool-call-1",
        result_status="success",
        output_summary="ok",
        permission_decision={"allowed": True},
        risk_flag=None,
    )

    query, params = executed[0]

    assert "update tool_calls" in query
    assert params[0] == "success"
    assert params[1]
    assert isinstance(params[2], Jsonb)
    assert params[4] == "tool-call-1"
    assert connection.committed is True


def test_list_stale_pending_tool_calls_returns_audit_rows(monkeypatch):
    rows = [
        (
            "tool-call-1",
            "task-1",
            "TASK-1",
            "xingbu",
            "schema_check",
            "schema-read-validation",
            "started",
            "medium",
            "2026-05-14 00:00:00",
            31,
        )
    ]
    executed = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, params=None):
            executed.append((query, params))

        def fetchall(self):
            return rows

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(tool_calls.psycopg, "connect", lambda _url: FakeConnection())

    stale = tool_calls.list_stale_pending_tool_calls(max_age_minutes=15, limit=10)

    query, params = executed[0]
    assert "result_status" in query
    assert "started_at < now()" in query
    assert params == (15, 10)
    assert stale == [
        {
            "id": "tool-call-1",
            "task_id": "task-1",
            "task_code": "TASK-1",
            "agent_name": "xingbu",
            "tool_name": "schema_check",
            "permission_policy": "schema-read-validation",
            "result_status": "started",
            "risk_flag": "medium",
            "started_at": "2026-05-14 00:00:00",
            "age_minutes": 31,
        }
    ]


def test_mark_stale_pending_tool_calls_timed_out_updates_rows(monkeypatch):
    rows = [
        (
            "tool-call-1",
            "task-1",
            "TASK-1",
            "xingbu",
            "schema_check",
            "schema-read-validation",
            "timed_out",
            "high",
            "2026-05-14 00:00:00",
            31,
        )
    ]
    executed = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, params=None):
            executed.append((query, params))

        def fetchall(self):
            return rows

    class FakeConnection:
        committed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            self.committed = True

    connection = FakeConnection()
    monkeypatch.setattr(tool_calls.psycopg, "connect", lambda _url: connection)

    stale = tool_calls.mark_stale_pending_tool_calls_timed_out(
        max_age_minutes=15,
        limit=10,
    )

    query, params = executed[0]
    assert "update tool_calls" in query
    assert "result_status = 'timed_out'" in query
    assert params[0] == 15
    assert params[1] == 10
    assert params[2]
    assert stale[0]["result_status"] == "timed_out"
    assert stale[0]["risk_flag"] == "high"
    assert connection.committed is True

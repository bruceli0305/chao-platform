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

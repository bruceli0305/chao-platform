from app.chao.services import historian_records


def test_record_historian_record_inserts_row(monkeypatch):
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
    monkeypatch.setattr(historian_records.psycopg, "connect", lambda _url: connection)

    historian_records.record_historian_record(
        task_id="task-1",
        record_type="github_delivery",
        content="Recorded",
        source="github-actions",
        created_by="ci",
    )

    query, params = executed[0]

    assert "insert into historian_records" in query
    assert params[2] == "github_delivery"
    assert connection.committed is True

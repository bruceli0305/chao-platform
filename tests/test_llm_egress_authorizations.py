from app.chao.services import llm_egress_authorizations


def test_record_llm_egress_authorization_writes_approval(monkeypatch):
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
    monkeypatch.setattr(llm_egress_authorizations.psycopg, "connect", lambda _url: connection)

    authorization = llm_egress_authorizations.record_llm_egress_authorization(
        task_id="task-1",
        provider="deepseek",
        model="deepseek-chat",
        data_classification="D1",
        authorized_by="emperor",
        ttl_hours=2,
    )

    query, params = executed[0]

    assert "llm_egress_authorizations" in query
    assert params[5] == "APPROVED"
    assert authorization["status"] == "APPROVED"
    assert connection.committed is True


def test_list_task_llm_egress_authorizations_returns_active_flag(monkeypatch):
    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, _query, _params=None):
            return None

        def fetchall(self):
            return [
                (
                    "deepseek",
                    "deepseek-chat",
                    "D1",
                    "APPROVED",
                    "emperor",
                    "test",
                    "2026-05-21 00:00:00+00",
                    "2026-05-20 00:00:00+00",
                    True,
                )
            ]

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(llm_egress_authorizations.psycopg, "connect", lambda _url: FakeConnection())

    authorizations = llm_egress_authorizations.list_task_llm_egress_authorizations("task-1")

    assert authorizations == [
        {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "data_classification": "D1",
            "status": "APPROVED",
            "authorized_by": "emperor",
            "reason": "test",
            "expires_at": "2026-05-21 00:00:00+00",
            "created_at": "2026-05-20 00:00:00+00",
            "active": True,
        }
    ]


def test_list_expired_llm_egress_authorizations_returns_task_context(monkeypatch):
    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, _query, _params=None):
            return None

        def fetchall(self):
            return [
                (
                    "auth-1",
                    "task-1",
                    "TASK-1",
                    "L3",
                    "DESIGNING",
                    "A",
                    "deepseek",
                    "deepseek-chat",
                    "D1",
                    "APPROVED",
                    "emperor",
                    "test",
                    "2026-05-20 00:00:00+00",
                    "2026-05-19 00:00:00+00",
                )
            ]

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(llm_egress_authorizations.psycopg, "connect", lambda _url: FakeConnection())

    authorizations = llm_egress_authorizations.list_expired_llm_egress_authorizations(limit=5)

    assert authorizations == [
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


def test_expire_llm_egress_authorizations_marks_pending_rows(monkeypatch):
    executed = []
    connections = []

    class SelectCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, params=None):
            executed.append((query, params))

        def fetchall(self):
            return [
                (
                    "auth-1",
                    "task-1",
                    "TASK-1",
                    "L3",
                    "DESIGNING",
                    "A",
                    "deepseek",
                    "deepseek-chat",
                    "D1",
                    "APPROVED",
                    "emperor",
                    "test",
                    "2026-05-20 00:00:00+00",
                    "2026-05-19 00:00:00+00",
                )
            ]

    class UpdateCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, params=None):
            executed.append((query, params))

    class FakeConnection:
        def __init__(self, cursor):
            self._cursor = cursor
            self.committed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return self._cursor

        def commit(self):
            self.committed = True

    def fake_connect(_url):
        connection = (
            FakeConnection(SelectCursor()) if not connections else FakeConnection(UpdateCursor())
        )
        connections.append(connection)
        return connection

    monkeypatch.setattr(llm_egress_authorizations.psycopg, "connect", fake_connect)

    result = llm_egress_authorizations.expire_llm_egress_authorizations(
        limit=5,
        dry_run=False,
    )

    assert result["dry_run"] is False
    assert result["expired_count"] == 1
    assert result["authorizations"][0]["status"] == "EXPIRED"
    assert "update llm_egress_authorizations" in executed[1][0]
    assert executed[1][1] == ("auth-1",)
    assert connections[1].committed is True

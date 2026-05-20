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

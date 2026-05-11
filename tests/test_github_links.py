from psycopg.types.json import Jsonb

from app.chao.services import github_links
from app.chao.services.github_links import normalize_github_link_type


def test_normalize_github_link_type_accepts_aliases():
    assert normalize_github_link_type("issue") == "issue"
    assert normalize_github_link_type("pr") == "pull_request"
    assert normalize_github_link_type("pull-request") == "pull_request"
    assert normalize_github_link_type("ci") == "ci_run"


def test_normalize_github_link_type_rejects_unknown_type():
    try:
        normalize_github_link_type("release")
    except ValueError as exc:
        assert "Unsupported GitHub link type" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_record_github_link_upserts_metadata(monkeypatch):
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
    monkeypatch.setattr(github_links.psycopg, "connect", lambda _url: connection)

    github_links.record_github_link(
        task_id="task-1",
        link_type="pull_request",
        external_id="42",
        url="https://github.com/example/repo/pull/42",
        title="Add task binding",
        status="open",
        metadata={"head": "feature/task-binding"},
        created_by="ci",
    )

    query, params = executed[0]

    assert "insert into github_links" in query
    assert params[2] == "pull_request"
    assert params[3] == "42"
    assert isinstance(params[7], Jsonb)
    assert connection.committed is True


def test_list_task_github_links(monkeypatch):
    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, params=None):
            self.query = query
            self.params = params

        def fetchall(self):
            return [
                (
                    "issue",
                    "7",
                    "https://github.com/example/repo/issues/7",
                    "Track task",
                    "open",
                    {"labels": ["task"]},
                    "ci",
                    "2026-05-11 10:00:00+00",
                    "2026-05-11 10:00:00+00",
                )
            ]

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(github_links.psycopg, "connect", lambda _url: FakeConnection())

    assert github_links.list_task_github_links("task-1") == [
        {
            "link_type": "issue",
            "external_id": "7",
            "url": "https://github.com/example/repo/issues/7",
            "title": "Track task",
            "status": "open",
            "metadata": {"labels": ["task"]},
            "created_by": "ci",
            "created_at": "2026-05-11 10:00:00+00",
            "updated_at": "2026-05-11 10:00:00+00",
        }
    ]

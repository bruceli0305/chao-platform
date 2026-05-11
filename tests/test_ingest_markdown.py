from scripts import ingest_markdown
from scripts.ingest_markdown import (
    build_data_asset_record,
    build_dry_run_report,
    build_report,
    classify_source,
    collect_candidates,
    extract_task_code,
    summarize_candidate,
    write_ingest_results,
)


def test_classify_source():
    assert classify_source("README.md") == ("documentation", "D0", False)
    assert classify_source("AGENTS.md") == ("agent_rule", "D1", True)
    assert classify_source(".ai-agents/router/task-router.md") == ("agent_rule", "D1", True)
    assert classify_source(".ai-agents/records/tasks/TASK-1.md") == (
        "historian_summary",
        "D1",
        True,
    )
    assert classify_source("docs/11-data-storage-boundary-v3.md") == (
        "documentation",
        "D1",
        True,
    )


def test_build_dry_run_report_filters_and_hashes_candidates(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / ".ai-agents" / "router").mkdir(parents=True)

    (tmp_path / "README.md").write_text("Project overview", encoding="utf-8")
    (tmp_path / "docs" / "policy.md").write_text("Policy", encoding="utf-8")
    (tmp_path / ".ai-agents" / "router" / "task-router.md").write_text(
        "Router",
        encoding="utf-8",
    )
    (tmp_path / "data" / "leak.md").write_text("forbidden", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('ignored')", encoding="utf-8")

    report = build_dry_run_report(
        tmp_path,
        [
            "README.md",
            "docs/policy.md",
            ".ai-agents/router/task-router.md",
            "data/leak.md",
            "app.py",
        ],
    )

    assert report["mode"] == "dry_run"
    assert report["candidate_count"] == 3
    assert report["rejected_count"] == 1
    assert report["rejected"] == [{"source_uri": "data/leak.md", "reason": "forbidden_path"}]
    assert [candidate["source_uri"] for candidate in report["candidates"]] == [
        "README.md",
        "docs/policy.md",
        ".ai-agents/router/task-router.md",
    ]
    assert all(candidate["source_hash"] for candidate in report["candidates"])
    assert all("content" not in candidate for candidate in report["candidates"])


def test_collect_candidates_keeps_content_for_write(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "policy.md").write_text("Policy", encoding="utf-8")

    candidates, rejected = collect_candidates(tmp_path, ["docs/policy.md"])

    assert rejected == []
    assert candidates[0]["source_uri"] == "docs/policy.md"
    assert candidates[0]["content"] == "Policy"


def test_extract_task_code_from_task_record_path():
    assert (
        extract_task_code(".ai-agents/records/tasks/TASK-20260510-110040-840984.md")
        == "TASK-20260510-110040-840984"
    )
    assert extract_task_code("docs/TASK-20260510-110040-840984.md") is None


def test_build_data_asset_record():
    candidate = {
        "source_path": "docs/11-data-storage-boundary-v3.md",
        "source_hash": "abc123",
        "source_type": "documentation",
        "data_classification": "D1",
        "ingest_allowed": True,
        "redacted": True,
    }

    assert build_data_asset_record(candidate, task_id=None) == {
        "task_id": None,
        "asset_name": "docs/11-data-storage-boundary-v3.md",
        "asset_type": "context_chunk_source",
        "classification": "D1",
        "primary_storage": "Git / Markdown",
        "allowed_copies": ["PostgreSQL", "pgvector"],
        "forbidden_storages": ["Secret Manager", "logs", "unapproved artifact"],
        "allow_vectorization": True,
        "desensitized": True,
        "retention_days": 3650,
        "owner": "historian",
        "notes": "source_hash=abc123; source_type=documentation",
    }


def test_write_ingest_results_skips_task_record_without_task(monkeypatch):
    executed = []

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, query, params=None):
            executed.append((query, params))

        def fetchone(self):
            return None

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
    monkeypatch.setattr(ingest_markdown, "get_database_url", lambda: "postgresql://test")
    monkeypatch.setattr(ingest_markdown.psycopg, "connect", lambda _url: connection)

    result = write_ingest_results(
        [
            {
                "source_path": ".ai-agents/records/tasks/TASK-20260510-110040-840984.md",
                "source_hash": "abc123",
                "source_type": "historian_summary",
                "data_classification": "D1",
                "redacted": True,
                "ingest_allowed": True,
                "retention_policy": "project_default",
                "created_by": "ingest_markdown",
                "content": "summary",
            }
        ]
    )

    assert result == (0, 0, 1)
    assert connection.committed is True
    assert not any("insert into context_chunks" in query for query, _params in executed)


def test_summarize_candidate_removes_content():
    candidate = {
        "source_uri": "README.md",
        "content": "full content",
        "source_hash": "abc123",
    }

    assert summarize_candidate(candidate) == {
        "source_uri": "README.md",
        "source_hash": "abc123",
    }


def test_build_report_omits_candidate_content():
    report = build_report(
        "dry_run",
        [{"source_uri": "README.md", "content": "full content"}],
        [],
    )

    assert report == {
        "mode": "dry_run",
        "candidate_count": 1,
        "rejected_count": 0,
        "candidates": [{"source_uri": "README.md"}],
        "rejected": [],
    }

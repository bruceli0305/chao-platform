from scripts.search_context import map_context_row


def test_map_context_row():
    row = (
        "docs/11-data-storage-boundary-v3.md",
        "documentation",
        "D1",
        "abc123",
        True,
        True,
        "project_default",
        "ingest_markdown",
        "2026-05-11 12:00:00+08",
        "数据边界摘要",
    )

    assert map_context_row(row) == {
        "source_path": "docs/11-data-storage-boundary-v3.md",
        "source_type": "documentation",
        "data_classification": "D1",
        "source_hash": "abc123",
        "redacted": True,
        "ingest_allowed": True,
        "retention_policy": "project_default",
        "created_by": "ingest_markdown",
        "created_at": "2026-05-11 12:00:00+08",
        "content_preview": "数据边界摘要",
    }

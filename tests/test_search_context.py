from scripts.search_context import map_context_row, search_context


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
        "context preview",
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
        "content_preview": "context preview",
    }


def test_map_context_row_includes_vector_distance():
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
        "context preview",
        0.123,
    )

    assert map_context_row(row)["vector_distance"] == 0.123


def test_search_context_rejects_unknown_mode():
    try:
        search_context("data-boundary", mode="unknown")
    except ValueError as exc:
        assert str(exc) == "unsupported search mode: unknown"
    else:
        raise AssertionError("expected unsupported mode to raise ValueError")

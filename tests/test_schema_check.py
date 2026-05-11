from scripts.schema_check import REQUIRED_COLUMNS


def test_context_chunks_metadata_columns_are_required():
    assert REQUIRED_COLUMNS["context_chunks"] == [
        "source_type",
        "source_hash",
        "data_classification",
        "redacted",
        "ingest_allowed",
        "retention_policy",
        "created_by",
    ]

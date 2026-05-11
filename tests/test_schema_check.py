from scripts.schema_check import REQUIRED_COLUMNS, should_check_storage_policies


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


def test_storage_policy_check_requires_storage_policies_table():
    assert should_check_storage_policies({"tasks", "context_chunks"}) is False
    assert should_check_storage_policies({"tasks", "context_chunks", "storage_policies"}) is True

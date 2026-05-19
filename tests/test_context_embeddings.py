from scripts.context_embeddings import (
    EMBEDDING_DIMENSIONS,
    build_local_embedding,
    format_pgvector,
    tokenize_embedding_text,
)


def test_tokenize_embedding_text_normalizes_words():
    assert tokenize_embedding_text("Data Boundary 数据边界") == [
        "data",
        "boundary",
        "数据边界",
    ]


def test_build_local_embedding_is_deterministic_and_normalized():
    embedding = build_local_embedding("数据边界 data boundary")

    assert embedding == build_local_embedding("数据边界 data boundary")
    assert len(embedding) == EMBEDDING_DIMENSIONS
    assert any(value != 0 for value in embedding)


def test_build_local_embedding_handles_empty_text():
    embedding = build_local_embedding("")

    assert len(embedding) == EMBEDDING_DIMENSIONS
    assert any(value != 0 for value in embedding)


def test_format_pgvector_uses_pgvector_literal_shape():
    assert format_pgvector([0.0, 1.25, -0.5]) == "[0.000000,1.250000,-0.500000]"

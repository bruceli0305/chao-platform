import hashlib
import math
import re

EMBEDDING_DIMENSIONS = 1536
EMBEDDING_MODEL = "local-hash-v1"

TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


def tokenize_embedding_text(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def build_local_embedding(
    text: str,
    dimensions: int = EMBEDDING_DIMENSIONS,
) -> list[float]:
    if dimensions <= 0:
        raise ValueError("dimensions must be positive")

    vector = [0.0] * dimensions
    tokens = tokenize_embedding_text(text)

    if not tokens:
        tokens = [hashlib.sha256(text.encode("utf-8")).hexdigest() or "__empty__"]

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector

    return [round(value / norm, 6) for value in vector]


def format_pgvector(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"

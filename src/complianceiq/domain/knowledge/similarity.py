"""Pure vector/text similarity helpers.

Kept in the domain (stdlib-only, no numpy) so every layer can use them without a
dependency: the in-memory vector store ranks by cosine similarity, the lexical
reranker and MMR diversity use token-set overlap. For corpus-scale in-memory
search this pure-Python math is more than fast enough; the pgvector adapter
delegates the same cosine distance to the database index.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two vectors, in ``[-1, 1]`` (1 = identical direction).

    Cosine compares *direction*, not magnitude, which is what we want for meaning:
    two texts about the same topic point the same way regardless of length.

    Raises:
        ValueError: If the vectors have different lengths — a dimension mismatch
            is never a silent zero; it is a bug to surface.
    """
    if len(a) != len(b):
        raise ValueError(f"vector dimension mismatch: {len(a)} != {len(b)}")
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def tokenize(text: str) -> list[str]:
    """Split text into lowercased alphanumeric tokens (order preserved)."""
    return _tokenize(text)


def token_set(text: str) -> set[str]:
    """Lowercased alphanumeric token set of ``text`` (for lexical similarity)."""
    return set(_tokenize(text))


def jaccard_similarity(a: str, b: str) -> float:
    """Jaccard overlap of two texts' token sets, in ``[0, 1]``."""
    set_a, set_b = token_set(a), token_set(b)
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def _tokenize(text: str) -> list[str]:
    """Split text into lowercased alphanumeric tokens."""
    token = []
    tokens = []
    for char in text.lower():
        if char.isalnum():
            token.append(char)
        elif token:
            tokens.append("".join(token))
            token = []
    if token:
        tokens.append("".join(token))
    return tokens

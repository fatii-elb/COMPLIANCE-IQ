"""Chunks and embedded chunks — the atoms of retrieval.

A **chunk** is a small, self-contained piece of the corpus (in our
structure-aware scheme, roughly *one control = one chunk*, so a retrieved chunk
maps cleanly to a citable rule). An **embedded chunk** is a chunk plus the vector
that represents its meaning, *plus the identity of the model that produced that
vector* — the anti-mismatch guard.

Chunks are content-addressed: the ``content_hash`` makes re-ingestion idempotent
(the same content yields the same id, so we never store duplicates).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from complianceiq.domain._base import FrozenModel
from complianceiq.domain.knowledge.metadata import ChunkMetadata
from complianceiq.domain.llm.models import ProviderName
from complianceiq.domain.value_objects.identifiers import NonEmptyStr


class Chunk(FrozenModel):
    """A retrievable unit of corpus text with its metadata.

    Attributes:
        id: Deterministic identifier derived from content + control (idempotency).
        content: The text that gets embedded and shown as context.
        metadata: Provenance and filtering attributes.
        content_hash: SHA-256 of the content, for dedup and change detection.
    """

    id: NonEmptyStr
    content: NonEmptyStr
    metadata: ChunkMetadata
    content_hash: NonEmptyStr


class EmbeddedChunk(FrozenModel):
    """A chunk paired with its embedding and the producing model's identity.

    ``embedding_model`` + ``embedding_provider`` are not decoration: query and
    document vectors are only comparable when produced by the *same* model. The
    vector store refuses to compare a query embedded with model A against chunks
    embedded with model B — turning a silent, catastrophic bug into a loud error.

    Attributes:
        chunk: The underlying chunk.
        vector: The embedding vector.
        embedding_model: The model id that produced the vector.
        embedding_provider: The provider that produced the vector.
    """

    chunk: Chunk
    vector: list[float] = Field(min_length=1)
    embedding_model: NonEmptyStr
    embedding_provider: ProviderName


class RetrievalSource(StrEnum):
    """Which retrieval path produced a scored chunk (for observability)."""

    SEMANTIC = "semantic"  # vector similarity
    LEXICAL = "lexical"  # keyword/BM25-style
    HYBRID = "hybrid"  # fused semantic + lexical
    RERANK = "rerank"  # after cross-encoder/lexical reranking


class ScoredChunk(FrozenModel):
    """A chunk with a relevance score and the path that produced it.

    Attributes:
        chunk: The retrieved chunk.
        score: Relevance score (higher = more relevant). Scale depends on
            ``retriever`` and is only meaningful for ordering within one path.
        retriever: Which retrieval path assigned this score.
    """

    chunk: Chunk
    score: float
    retriever: RetrievalSource

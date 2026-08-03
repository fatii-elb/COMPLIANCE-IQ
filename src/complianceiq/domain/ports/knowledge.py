"""Ports for the knowledge base and retrieval pipeline.

Four abstractions the RAG use cases depend on:

- :class:`Embedder` — turns text into vectors (fulfilled via the AI gateway's
  embedding model).
- :class:`VectorStore` — stores embedded chunks and answers semantic
  (similarity) searches with metadata pre-filtering.
- :class:`KeywordIndex` — answers lexical (keyword) searches, the other half of
  hybrid retrieval.
- :class:`Reranker` — re-orders candidate chunks by deep relevance to the query
  (a cross-encoder in production; a deterministic lexical reranker offline).

Each is a port so the pipeline is testable offline (in-memory adapters) and so the
production pgvector-backed store swaps in without changing use cases.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from complianceiq.domain.knowledge.chunks import Chunk, EmbeddedChunk, ScoredChunk
from complianceiq.domain.knowledge.metadata import MetadataFilter
from complianceiq.domain.llm.responses import EmbeddingResult


class Embedder(ABC):
    """Produces embedding vectors for texts (records the producing model)."""

    @abstractmethod
    async def embed(self, texts: Sequence[str]) -> list[EmbeddingResult]:
        """Embed a batch of texts. Each result records its model identity."""
        raise NotImplementedError


class VectorStore(ABC):
    """Stores embedded chunks and performs metadata-filtered similarity search."""

    @abstractmethod
    async def upsert(self, chunks: Sequence[EmbeddedChunk]) -> int:
        """Insert or replace embedded chunks (by chunk id). Returns the count."""
        raise NotImplementedError

    @abstractmethod
    async def search(
        self,
        *,
        embedding: Sequence[float],
        embedding_model: str,
        top_k: int,
        metadata_filter: MetadataFilter,
    ) -> list[ScoredChunk]:
        """Return the ``top_k`` most similar chunks matching the filter.

        Implementations MUST reject a query whose ``embedding_model`` differs from
        the stored chunks' model (raising ``EmbeddingModelMismatchError``): vectors
        from different models are not comparable, and comparing them silently
        returns nonsense.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_by_corpus_version(self, corpus_version: str) -> int:
        """Delete all chunks of a corpus version (for clean re-indexing)."""
        raise NotImplementedError

    @abstractmethod
    async def count(self) -> int:
        """Return the number of stored chunks."""
        raise NotImplementedError


class KeywordIndex(ABC):
    """A lexical index for keyword/BM25-style search (hybrid retrieval)."""

    @abstractmethod
    async def index(self, chunks: Sequence[Chunk]) -> int:
        """Add chunks to the lexical index. Returns the count."""
        raise NotImplementedError

    @abstractmethod
    async def search(
        self, *, text: str, top_k: int, metadata_filter: MetadataFilter
    ) -> list[ScoredChunk]:
        """Return the ``top_k`` best lexical matches for ``text``."""
        raise NotImplementedError

    @abstractmethod
    async def delete_by_corpus_version(self, corpus_version: str) -> int:
        """Delete all indexed chunks of a corpus version."""
        raise NotImplementedError

    @abstractmethod
    async def count(self) -> int:
        """Return the number of indexed chunks."""
        raise NotImplementedError


class Reranker(ABC):
    """Re-orders candidate chunks by deep relevance to the query."""

    @abstractmethod
    async def rerank(
        self, *, query: str, candidates: Sequence[ScoredChunk], top_k: int
    ) -> list[ScoredChunk]:
        """Return up to ``top_k`` candidates, re-scored and re-ordered."""
        raise NotImplementedError

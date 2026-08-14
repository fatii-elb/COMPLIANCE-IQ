"""In-memory vector store (default, offline).

Implements the :class:`VectorStore` port with a plain dict and pure-Python cosine
similarity. It is the default so the whole RAG pipeline runs and is tested without
a database. The production backend is PostgreSQL + pgvector, which implements the
same port (see ADR-0005); switching is a composition change, not a code change.

It enforces the **embedding-model-identity guard**: all stored chunks must share
one embedding model, and a query embedded with a different model is rejected with
``EmbeddingModelMismatchError`` rather than silently returning garbage.
"""

from __future__ import annotations

from collections.abc import Sequence

from complianceiq.domain.exceptions import EmbeddingModelMismatchError
from complianceiq.domain.knowledge.chunks import EmbeddedChunk, RetrievalSource, ScoredChunk
from complianceiq.domain.knowledge.metadata import MetadataFilter
from complianceiq.domain.knowledge.similarity import cosine_similarity
from complianceiq.domain.ports.knowledge import VectorStore


class InMemoryVectorStore(VectorStore):
    """A dict-backed vector store with cosine similarity search."""

    def __init__(self) -> None:
        self._chunks: dict[str, EmbeddedChunk] = {}
        self._embedding_model: str | None = None

    async def upsert(self, chunks: Sequence[EmbeddedChunk]) -> int:
        for embedded in chunks:
            # Enforce a single embedding model across the whole store.
            if self._embedding_model is None:
                self._embedding_model = embedded.embedding_model
            elif embedded.embedding_model != self._embedding_model:
                raise EmbeddingModelMismatchError(
                    "cannot mix embedding models in one store",
                    details={
                        "store_model": self._embedding_model,
                        "chunk_model": embedded.embedding_model,
                    },
                )
            self._chunks[embedded.chunk.id] = embedded
        return len(chunks)

    async def search(
        self,
        *,
        embedding: Sequence[float],
        embedding_model: str,
        top_k: int,
        metadata_filter: MetadataFilter,
    ) -> list[ScoredChunk]:
        if self._embedding_model is not None and embedding_model != self._embedding_model:
            raise EmbeddingModelMismatchError(
                "query embedding model does not match the stored corpus",
                details={"store_model": self._embedding_model, "query_model": embedding_model},
            )

        scored: list[ScoredChunk] = []
        for embedded in self._chunks.values():
            if not metadata_filter.matches(embedded.chunk.metadata):
                continue
            similarity = cosine_similarity(embedding, embedded.vector)
            scored.append(
                ScoredChunk(
                    chunk=embedded.chunk,
                    score=similarity,
                    retriever=RetrievalSource.SEMANTIC,
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    async def delete_by_corpus_version(self, corpus_version: str) -> int:
        to_delete = [
            cid
            for cid, embedded in self._chunks.items()
            if embedded.chunk.metadata.corpus_version == corpus_version
        ]
        for cid in to_delete:
            del self._chunks[cid]
        if not self._chunks:
            self._embedding_model = None
        return len(to_delete)

    async def count(self) -> int:
        return len(self._chunks)
